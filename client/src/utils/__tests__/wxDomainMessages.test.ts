/**
 * wxDomainMessages.ts 单测：合法域名 errMsg 转用户可读文案
 *
 * 该映射直接关系到「真机上为什么打不开」的引导：错一行 hint，
 * 现场运营/产品会被指着鼻子骂。锁定四类场景。
 */

import { formatWxDomainComplianceError } from '@/utils/wxDomainMessages'

describe('formatWxDomainComplianceError', () => {
  test('空 errMsg → 兜底「网络异常」', () => {
    expect(formatWxDomainComplianceError('request', '')).toContain('网络异常')
    expect(formatWxDomainComplianceError('request', '   ')).toContain('网络异常')
  })

  test('非域名类错误 → 保留原文（过长截断）', () => {
    expect(formatWxDomainComplianceError('request', 'HTTP 500')).toBe('HTTP 500')
    const long = 'a'.repeat(200)
    const out = formatWxDomainComplianceError('request', long)
    expect(out.endsWith('…')).toBe(true)
    expect(out.length).toBeLessThanOrEqual(80)
  })

  test('localhost / 127.0.0.1 → 提示改用 HTTPS 线上域名', () => {
    const out = formatWxDomainComplianceError(
      'request',
      'request:fail url not in domain list',
      'http://localhost:8000/v1/users/me',
    )
    expect(out).toMatch(/localhost|127\.0\.0\.1/)
    expect(out).toMatch(/TARO_APP_API_BASE_URL|HTTPS/)
  })

  test('合法 https 域名 → 指引去公众平台添加该 host', () => {
    const out = formatWxDomainComplianceError(
      'request',
      'request:fail url not in domain list',
      'https://api.birdie.golf/v1/users/me',
    )
    expect(out).toContain('https://api.birdie.golf')
    expect(out).toContain('request 合法域名')
    expect(out).toContain('服务器域名')
  })

  test('uploadFile / downloadFile 用对应 portal 名', () => {
    const u = formatWxDomainComplianceError(
      'uploadFile',
      'uploadFile:fail url not in domain list',
      'https://cdn.birdie.golf/x.mp4',
    )
    expect(u).toContain('uploadFile 合法域名')
    expect(u).toContain('https://cdn.birdie.golf')

    const d = formatWxDomainComplianceError(
      'downloadFile',
      'downloadFile:fail url not in domain list',
      'https://cdn.birdie.golf/x.mp4',
    )
    expect(d).toContain('downloadFile 合法域名')
  })

  test('attemptedUrl 不可解析 → 退回通用提示', () => {
    const out = formatWxDomainComplianceError(
      'request',
      'request:fail not in domain list',
      'not-a-url',
    )
    expect(out).toMatch(/请在公众平台/)
    // 没有 host 时不暴露错误 URL
    expect(out).not.toContain('not-a-url')
  })

  test('中文「合法域名」字样也识别为域名错误', () => {
    const out = formatWxDomainComplianceError(
      'request',
      '小程序未配置合法域名，无法访问',
      'https://api.birdie.golf/v1/x',
    )
    expect(out).toContain('https://api.birdie.golf')
  })
})
