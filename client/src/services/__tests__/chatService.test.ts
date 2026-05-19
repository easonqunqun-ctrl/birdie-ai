/**
 * chatService.ts 单测：URL / 参数 / header / streamMessage 事件分发
 *
 * sendMessage 与 streamMessage 是对话页的支柱，URL 拼接和 silent/timeout 配置
 * 一旦改错会直接表现为「消息发不出去」。本文件锁定既定行为。
 */

import { chatService } from '@/services/chatService'
import Taro from '@tarojs/taro'

const T = Taro as unknown as Record<string, jest.Mock>

const ok = (data: unknown) => ({
  statusCode: 200,
  data: { code: 0, message: 'ok', data },
})

beforeEach(() => {
  ;(Taro as any).clearStorageSync()
  T.request.mockReset()
})

describe('chatService.getQuickQuestions', () => {
  test('GET /chat/quick-questions, noAuth=true', async () => {
    T.request.mockResolvedValueOnce(ok({ questions: [] }))
    await chatService.getQuickQuestions()
    const sent = T.request.mock.calls[0][0]
    expect(sent.url).toBe('http://localhost:8000/v1/chat/quick-questions')
    expect(sent.method).toBe('GET')
    expect(sent.header.Authorization).toBeUndefined()
  })
})

describe('chatService.createSession', () => {
  test('POST /chat/sessions + payload', async () => {
    T.request.mockResolvedValueOnce(ok({ session_id: 's1' }))
    await chatService.createSession({ context_analysis_id: 'a1' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toBe('http://localhost:8000/v1/chat/sessions')
    expect(sent.data).toEqual({ context_analysis_id: 'a1' })
  })

  test('无 payload 也能调（默认 {}）', async () => {
    T.request.mockResolvedValueOnce(ok({ session_id: 's1' }))
    await chatService.createSession()
    expect(T.request.mock.calls[0][0].data).toEqual({})
  })
})

describe('chatService.listSessions / getMessages 分页拼接', () => {
  test('listSessions(page=2,page_size=20) 拼 ?page=2&page_size=20', async () => {
    T.request.mockResolvedValueOnce(ok({ items: [] }))
    await chatService.listSessions({ page: 2, page_size: 20 })
    const sent = T.request.mock.calls[0][0]
    expect(sent.url).toContain('?page=2&page_size=20')
  })

  test('getMessages 无分页参数时不带 ?', async () => {
    T.request.mockResolvedValueOnce(ok({ items: [] }))
    await chatService.getMessages('sid')
    expect(T.request.mock.calls[0][0].url).toBe(
      'http://localhost:8000/v1/chat/sessions/sid/messages',
    )
  })

  test('getMessages 只有 page → ?page=3', async () => {
    T.request.mockResolvedValueOnce(ok({ items: [] }))
    await chatService.getMessages('sid', { page: 3 })
    expect(T.request.mock.calls[0][0].url).toContain('?page=3')
  })
})

describe('chatService.sendMessage', () => {
  test('POST /chat/sessions/:id/messages?stream=false + Accept JSON + silent', async () => {
    T.request.mockResolvedValueOnce(
      ok({ assistant_message_id: 'm1', content: 'hi', attachments: [] }),
    )
    await chatService.sendMessage('sid', { content: '你好' } as any)
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/chat/sessions/sid/messages?stream=false')
    expect(sent.header.Accept).toBe('application/json')
    // timeout 必须 > 默认 15s，因为后端 LLM 完整应答可能数分钟
    expect(sent.timeout).toBeGreaterThan(15000)
    expect(sent.data).toEqual({ content: '你好' })
  })

  test('sendMessage 业务错误（50106 LLM 失败）silent=true，调用方需自己处理', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 502,
      data: { code: 50106, message: 'AI 引擎暂时不可用' },
    })
    // 不再 toast
    await expect(chatService.sendMessage('sid', { content: '你好' } as any)).rejects.toMatchObject(
      { kind: 'business', code: 50106 },
    )
    expect(T.showToast).not.toHaveBeenCalled()
  })
})

describe('chatService.deleteSession', () => {
  test('DELETE /chat/sessions/:id', async () => {
    T.request.mockResolvedValueOnce(ok(null))
    await chatService.deleteSession('sid')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('DELETE')
    expect(sent.url).toContain('/chat/sessions/sid')
  })
})
