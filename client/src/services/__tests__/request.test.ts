/**
 * request.ts 单测：
 *  - 成功路径：解包 body.data
 *  - 401（含 40104 微信登录码失效语义不清 token）
 *  - 5xx（带业务信封时按 business 抛）
 *  - body 结构异常 → bad_response
 *  - 业务码非 0 → business
 *  - 网络异常 → network + friendlyNetworkMessage 文案
 *  - URL 拼接：相对路径走 baseURL；绝对 https 不拼
 *  - JWT 自动注入；noAuth 不注入
 *  - 401 触发 reLaunch；business 不触发
 */

import Taro from '@tarojs/taro'
import {
  request,
  http,
  RequestError,
  isRequestError,
  describeIntermittentRequestFailure,
  describePageLoadFailure,
} from '@/services/request'
import { storage } from '@/utils/storage'

const T = Taro as unknown as Record<string, jest.Mock>

const okResponse = (data: unknown, status = 200) => ({
  statusCode: status,
  data: { code: 0, message: 'ok', data },
  header: { 'x-request-id': 'rid-test' },
})

beforeEach(() => {
  ;(Taro as any).clearStorageSync()
  T.request.mockReset()
  T.showToast.mockClear()
  T.reLaunch.mockClear()
})

describe('request · 成功路径', () => {
  test('200 + code=0 → resolve(data)', async () => {
    T.request.mockResolvedValueOnce(okResponse({ id: 42 }))
    const result = await request<{ id: number }>({ url: '/users/me' })
    expect(result).toEqual({ id: 42 })
  })

  test('http.get / post / patch / put / del 分别走对应 method', async () => {
    T.request.mockResolvedValue(okResponse(null))
    await http.get('/g')
    await http.post('/p', { a: 1 })
    await http.patch('/pt', { a: 2 })
    await http.put('/pu', { a: 3 })
    await http.del('/d')
    const calls = T.request.mock.calls.map((c) => c[0])
    expect(calls.map((c) => c.method)).toEqual(['GET', 'POST', 'PATCH', 'PUT', 'DELETE'])
  })
})

describe('request · URL 拼接', () => {
  test('相对路径拼 baseURL', async () => {
    T.request.mockResolvedValueOnce(okResponse(null))
    await request({ url: '/foo' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.url).toBe('http://localhost:8000/v1/foo')
  })

  test('绝对 https URL 原样透传', async () => {
    T.request.mockResolvedValueOnce(okResponse(null))
    await request({ url: 'https://other.example.com/x' })
    expect(T.request.mock.calls[0][0].url).toBe('https://other.example.com/x')
  })
})

describe('request · JWT 注入', () => {
  test('有 token → Authorization: Bearer <token>', async () => {
    storage.setToken('abc.def')
    T.request.mockResolvedValueOnce(okResponse(null))
    await request({ url: '/me' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.header.Authorization).toBe('Bearer abc.def')
  })

  test('noAuth=true → 不注入 Authorization', async () => {
    storage.setToken('abc.def')
    T.request.mockResolvedValueOnce(okResponse(null))
    await request({ url: '/public', noAuth: true })
    const sent = T.request.mock.calls[0][0]
    expect(sent.header.Authorization).toBeUndefined()
  })
})

describe('request · 401 处理', () => {
  test('普通 401 → http_unauthorized + 清 token + reLaunch', async () => {
    storage.setToken('expired_token')
    T.request.mockResolvedValueOnce({
      statusCode: 401,
      data: { code: 401, message: 'token expired' },
    })
    await expect(request({ url: '/me' })).rejects.toMatchObject({
      kind: 'http_unauthorized',
      status: 401,
    })
    expect(storage.getToken()).toBe('')
    expect(T.reLaunch).toHaveBeenCalledWith({ url: '/pages/login/index' })
  })

  test('401 + bizCode=40104 → business（不清 token，不跳登录）', async () => {
    storage.setToken('valid_jwt')
    T.request.mockResolvedValueOnce({
      statusCode: 401,
      data: { code: 40104, message: '微信 code 已失效' },
    })
    await expect(request({ url: '/auth/wechat/login' })).rejects.toMatchObject({
      kind: 'business',
      code: 40104,
    })
    expect(storage.getToken()).toBe('valid_jwt') // 仍保留
    expect(T.reLaunch).not.toHaveBeenCalled()
  })
})

describe('request · 5xx 处理', () => {
  test('500 + 业务 code≠0 → business（保留 50106 文案）', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 502,
      data: { code: 50106, message: 'AI 引擎暂时不可用', detail: 'upstream timeout' },
      header: { 'x-request-id': 'rid-50106' },
    })
    await expect(request({ url: '/chat/messages' })).rejects.toMatchObject({
      kind: 'business',
      code: 50106,
      detail: 'upstream timeout',
      requestId: 'rid-50106',
    })
  })

  test('500 + 非 JSON body → http_server_error', async () => {
    T.request.mockResolvedValueOnce({ statusCode: 502, data: '<html>...</html>' })
    await expect(request({ url: '/x' })).rejects.toMatchObject({
      kind: 'http_server_error',
      status: 502,
    })
  })
})

describe('request · 业务错误', () => {
  test('200 + code≠0 → business + toast', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 40301, message: '配额已用完' },
    })
    await expect(request({ url: '/foo' })).rejects.toMatchObject({
      kind: 'business',
      code: 40301,
    })
    expect(T.showToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: '配额已用完', icon: 'none' }),
    )
  })

  test('silent=true → 不 toast', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 40301, message: '配额已用完' },
    })
    await expect(request({ url: '/foo', silent: true })).rejects.toThrow()
    expect(T.showToast).not.toHaveBeenCalled()
  })

  test('body 没 code → bad_response', async () => {
    T.request.mockResolvedValueOnce({ statusCode: 200, data: { hello: 'world' } })
    await expect(request({ url: '/foo' })).rejects.toMatchObject({ kind: 'bad_response' })
  })
})

describe('request · 网络异常文案映射', () => {
  test('TLS 证书失败（-207） → 友好提示', async () => {
    T.request.mockRejectedValueOnce({ errMsg: 'request:fail errcode:-207 ...' })
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect(isRequestError(e)).toBe(true)
      expect((e as RequestError).message).toContain('HTTPS 证书')
    }
  })

  test('超时 → 「请求超时」', async () => {
    T.request.mockRejectedValueOnce({ errMsg: 'request:fail timeout' })
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect((e as RequestError).message).toMatch(/超时/)
    }
  })

  test('合法域名未配置 → 走 formatWxDomainComplianceError 信道（含「合法域名」三字）', async () => {
    T.request.mockRejectedValueOnce({
      errMsg: 'request:fail url not in domain list',
    })
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect((e as RequestError).message).toMatch(/域名|domain/i)
    }
  })

  test('空错误 → 「网络异常，请稍后重试」', async () => {
    T.request.mockRejectedValueOnce(undefined)
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect((e as RequestError).message).toBe('网络异常，请稍后重试')
    }
  })

  // P2-W17-A · 错码扩展（微信真机 errcode + iOS CFNetwork）
  test('errcode:-100（代理拒绝）→ 提示关闭代理/VPN', async () => {
    T.request.mockRejectedValueOnce({
      errMsg: 'request:fail errcode:-100 proxy connection failed',
    })
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect((e as RequestError).message).toMatch(/代理|VPN/)
    }
  })

  test('errcode:-99（TCP 连接被拒）→ 提示关闭代理/VPN', async () => {
    T.request.mockRejectedValueOnce({ errMsg: 'request:fail errcode:-99' })
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect((e as RequestError).message).toMatch(/代理|VPN/)
    }
  })

  test('errcode:-2（HTTP 协议错误）→ 「响应不规范」', async () => {
    T.request.mockRejectedValueOnce({ errMsg: 'request:fail errcode:-2' })
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect((e as RequestError).message).toMatch(/响应不规范|联系运维/)
    }
  })

  test('iOS CFNetwork errno=-1003（cannot find host）→ 「找不到服务器地址」', async () => {
    T.request.mockRejectedValueOnce({
      errMsg: 'request:fail CFURLErrorDomain errno=-1003 cannot find host',
    })
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect((e as RequestError).message).toMatch(/找不到服务器/)
    }
  })

  test('iOS errno=-1009（无网络）→ 「当前没有网络连接」', async () => {
    T.request.mockRejectedValueOnce({
      errMsg: 'request:fail errno=-1009 not connected to internet',
    })
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect((e as RequestError).message).toMatch(/没有网络连接/)
    }
  })
})

describe('request · HTTP 429 速率限制', () => {
  test('HTTP 429 + 空 body → toast 「请求过于频繁」+ http_server_error kind', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 429,
      data: null,
      header: { 'x-request-id': 'rid-429' },
    })
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect(isRequestError(e)).toBe(true)
      expect((e as RequestError).kind).toBe('http_server_error')
      expect((e as RequestError).status).toBe(429)
      expect((e as RequestError).message).toMatch(/频繁|稍后/)
    }
    expect(T.showToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: expect.stringMatching(/频繁|稍后/) }),
    )
  })

  test('HTTP 429 + silent → 不 toast', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 429,
      data: null,
      header: {},
    })
    try {
      await request({ url: '/x', silent: true })
      fail('should throw')
    } catch (e) {
      expect((e as RequestError).status).toBe(429)
    }
    expect(T.showToast).not.toHaveBeenCalled()
  })
})

describe('describeIntermittentRequestFailure / describePageLoadFailure', () => {
  test('business 错误：文案优先用 message', () => {
    const e = new RequestError('business', '余额不足', { code: 1, status: 200 })
    const { fatalMessage, toastTitle } = describeIntermittentRequestFailure(e)
    expect(fatalMessage).toBe('余额不足')
    expect(toastTitle).toBe('余额不足')
  })

  test('http_server_error：默认轮询暂停提示', () => {
    const e = new RequestError('http_server_error', 'HTTP 502', { status: 502 })
    const { fatalMessage, toastTitle } = describeIntermittentRequestFailure(e)
    expect(fatalMessage).toContain('暂停自动刷新')
    expect(toastTitle).toBe('服务暂时不可用')
  })

  test('describePageLoadFailure 去掉「，已暂停自动刷新」尾缀', () => {
    const e = new RequestError('http_server_error', 'HTTP 502', { status: 502 })
    const page = describePageLoadFailure(e)
    expect(page).not.toContain('暂停')
  })

  test('未知错误 → 通用提示', () => {
    const { fatalMessage, toastTitle } = describeIntermittentRequestFailure(
      new Error('oops'),
    )
    expect(fatalMessage).toContain('网络似乎不太稳定')
    expect(toastTitle).toBe('网络异常，请稍后重试')
  })

  test('business 40007 → 配额文案', () => {
    const e = new RequestError('business', '今日对话次数已用完', { code: 40007 })
    expect(describeIntermittentRequestFailure(e).toastTitle).toBe('今日对话次数已用完')
  })

  test('business 40009 → 限流文案', () => {
    const e = new RequestError('business', 'too fast', { code: 40009 })
    expect(describeIntermittentRequestFailure(e).toastTitle).toBe('发送太频繁，请稍后再试')
  })

  test('network DNS 失败 → 解析提示', async () => {
    T.request.mockRejectedValueOnce({ errMsg: 'request:fail getaddrinfo ENOTFOUND api.example.com' })
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect((e as RequestError).message).toMatch(/解析/)
    }
  })

  test('network 连接中断 → 中断提示', async () => {
    T.request.mockRejectedValueOnce({ errMsg: 'request:fail connection reset by peer' })
    try {
      await request({ url: '/x' })
      fail('should throw')
    } catch (e) {
      expect((e as RequestError).message).toMatch(/中断/)
    }
  })
})
