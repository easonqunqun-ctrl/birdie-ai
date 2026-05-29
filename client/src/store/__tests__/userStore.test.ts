/**
 * userStore.ts 单测：登录态生命周期
 *
 * 关键不变式：
 *  - bootstrap 拿不到 token → initialized=true，user=null
 *  - bootstrap 拿到 token，cachedUser 存在 → 立即 initialized=true（避免冷启动闪登录页）
 *  - bootstrap getMe 5xx → 保留 token + cachedUser（弱网不踢人）
 *  - bootstrap getMe 401 → 清 token + reLaunch（由 request.ts 兜底）
 *  - logout → 走 clearAuthSession，不动协议同意
 */

import { storage, CURRENT_TERMS_VERSION } from '@/utils/storage'
import { RequestError } from '@/services/request'

// 必须在 import store 之前 mock 这些依赖
jest.mock('@/services/userService', () => ({
  userService: {
    getMe: jest.fn(),
    wechatLogin: jest.fn(),
    roleSwitch: jest.fn(),
  },
}))
jest.mock('@/utils/tabBarRole', () => ({
  applyTabBarRole: jest.fn(),
}))
jest.mock('@/adapters/login', () => ({
  nativeLogin: jest.fn(),
}))

// 引入后才会有 mock 句柄
import { userService } from '@/services/userService'
import { applyTabBarRole } from '@/utils/tabBarRole'
import { nativeLogin } from '@/adapters/login'
import { useUserStore } from '@/store/userStore'

const mockedGetMe = userService.getMe as jest.Mock
const mockedWechatLogin = userService.wechatLogin as jest.Mock
const mockedRoleSwitch = userService.roleSwitch as jest.Mock
const mockedNativeLogin = nativeLogin as jest.Mock
const mockedApplyTabBarRole = applyTabBarRole as jest.Mock

function resetStore() {
  useUserStore.setState({
    token: '',
    user: null,
    currentRole: 'user',
    loading: false,
    initialized: false,
  })
}

beforeEach(() => {
  storage.clearAll()
  resetStore()
  mockedGetMe.mockReset()
  mockedWechatLogin.mockReset()
  mockedRoleSwitch.mockReset()
  mockedNativeLogin.mockReset()
  mockedApplyTabBarRole.mockReset()
})

describe('userStore.bootstrap', () => {
  test('无 token → initialized=true，不调 getMe', async () => {
    await useUserStore.getState().bootstrap()
    const s = useUserStore.getState()
    expect(s.initialized).toBe(true)
    expect(s.token).toBe('')
    expect(s.user).toBeNull()
    expect(mockedGetMe).not.toHaveBeenCalled()
  })

  test('有 token + cachedUser → 立即填充，再异步刷新', async () => {
    storage.setToken('jwt')
    storage.setUser({ id: 1, nickname: '小鸟' })
    mockedGetMe.mockResolvedValueOnce({ id: 1, nickname: '小鸟 v2' })

    await useUserStore.getState().bootstrap()

    const s = useUserStore.getState()
    expect(s.token).toBe('jwt')
    expect(s.initialized).toBe(true)
    expect(s.user).toEqual({ id: 1, nickname: '小鸟 v2' })
    expect(s.loading).toBe(false)
  })

  test('有 token，但 getMe 5xx → 保留 token + cachedUser（弱网容忍）', async () => {
    storage.setToken('jwt')
    storage.setUser({ id: 1, nickname: '缓存' })
    mockedGetMe.mockRejectedValueOnce(
      new RequestError('http_server_error', 'HTTP 502', { status: 502 }),
    )

    await useUserStore.getState().bootstrap()

    const s = useUserStore.getState()
    expect(s.token).toBe('jwt')
    expect(s.user).toEqual({ id: 1, nickname: '缓存' })
    expect(storage.getToken()).toBe('jwt')
    expect(s.initialized).toBe(true)
  })

  test('有 token，但 getMe 401 → 清 token + user=null', async () => {
    storage.setToken('jwt')
    storage.setUser({ id: 1 })
    mockedGetMe.mockRejectedValueOnce(
      new RequestError('http_unauthorized', '未登录或登录已过期', { status: 401 }),
    )

    await useUserStore.getState().bootstrap()

    const s = useUserStore.getState()
    expect(s.token).toBe('')
    expect(s.user).toBeNull()
    expect(storage.getToken()).toBe('')
    expect(s.initialized).toBe(true)
  })

  test('有 token，无 cachedUser → 拉取成功后填充', async () => {
    storage.setToken('jwt')
    mockedGetMe.mockResolvedValueOnce({ id: 7, nickname: 'fresh' })

    await useUserStore.getState().bootstrap()

    const s = useUserStore.getState()
    expect(s.user).toEqual({ id: 7, nickname: 'fresh' })
    expect(s.initialized).toBe(true)
  })
})

describe('userStore.loginWithWechat', () => {
  test('成功 → 写入 token & user，返回 isNewUser', async () => {
    mockedNativeLogin.mockResolvedValueOnce({ code: 'wxcode' })
    mockedWechatLogin.mockResolvedValueOnce({
      token: 'new_jwt',
      user: { id: 9, nickname: '新用户' },
      is_new_user: true,
    })

    const r = await useUserStore.getState().loginWithWechat('INVITE')

    expect(mockedWechatLogin).toHaveBeenCalledWith({
      code: 'wxcode',
      invite_code: 'INVITE',
    })
    expect(r.isNewUser).toBe(true)
    expect(storage.getToken()).toBe('new_jwt')
    expect(useUserStore.getState().token).toBe('new_jwt')
    expect(useUserStore.getState().user).toEqual({ id: 9, nickname: '新用户' })
    expect(useUserStore.getState().loading).toBe(false)
  })

  test('失败 → loading 复位，抛错', async () => {
    mockedNativeLogin.mockResolvedValueOnce({ code: 'wxcode' })
    mockedWechatLogin.mockRejectedValueOnce(new Error('boom'))

    await expect(
      useUserStore.getState().loginWithWechat(),
    ).rejects.toThrow('boom')
    expect(useUserStore.getState().loading).toBe(false)
    expect(useUserStore.getState().token).toBe('')
  })
})

describe('userStore.fetchMe', () => {
  test('无 token → no-op', async () => {
    await useUserStore.getState().fetchMe()
    expect(mockedGetMe).not.toHaveBeenCalled()
  })

  test('有 token + 成功 → 更新 user 与 storage', async () => {
    useUserStore.setState({ token: 'jwt', user: null, initialized: true })
    storage.setToken('jwt')
    mockedGetMe.mockResolvedValueOnce({ id: 1, nickname: 'fresh' })

    await useUserStore.getState().fetchMe()

    expect(useUserStore.getState().user).toEqual({ id: 1, nickname: 'fresh' })
    expect(storage.getUser()).toEqual({ id: 1, nickname: 'fresh' })
  })

  test('401 → 清 token + user', async () => {
    useUserStore.setState({ token: 'jwt', user: { id: 1 } as any })
    storage.setToken('jwt')
    mockedGetMe.mockRejectedValueOnce(
      new RequestError('http_unauthorized', '未登录或登录已过期', { status: 401 }),
    )

    await useUserStore.getState().fetchMe()

    expect(useUserStore.getState().token).toBe('')
    expect(useUserStore.getState().user).toBeNull()
  })

  test('5xx → 保留上一快照（不打断 tab 静默刷新）', async () => {
    useUserStore.setState({ token: 'jwt', user: { id: 1, nickname: 'old' } as any })
    mockedGetMe.mockRejectedValueOnce(
      new RequestError('http_server_error', 'HTTP 502', { status: 502 }),
    )

    await useUserStore.getState().fetchMe()

    const s = useUserStore.getState()
    expect(s.token).toBe('jwt')
    expect(s.user).toEqual({ id: 1, nickname: 'old' })
  })
})

describe('userStore.setRole', () => {
  test('成功 → 更新 token/role/storage + TabBar', async () => {
    mockedRoleSwitch.mockResolvedValueOnce({
      token: 'coach_jwt',
      expires_in: 7200,
      role: 'coach',
    })

    await useUserStore.getState().setRole('coach')

    expect(mockedRoleSwitch).toHaveBeenCalledWith('coach')
    expect(storage.getToken()).toBe('coach_jwt')
    expect(storage.getRole()).toBe('coach')
    expect(useUserStore.getState().currentRole).toBe('coach')
    expect(mockedApplyTabBarRole).toHaveBeenCalledWith('coach')
  })
})

describe('userStore.bootstrap · coach role 降级', () => {
  test('cached coach 但用户不再 active → 重置为 user', async () => {
    storage.setToken('jwt')
    storage.setRole('coach')
    storage.setUser({ id: 1, is_active_coach: false })
    mockedGetMe.mockResolvedValueOnce({ id: 1, is_active_coach: false })

    await useUserStore.getState().bootstrap()

    expect(useUserStore.getState().currentRole).toBe('user')
    expect(storage.getRole()).toBe('user')
    expect(mockedApplyTabBarRole).toHaveBeenCalledWith('user')
  })
})

describe('userStore.logout · 不动协议同意', () => {
  test('logout 只清账号身份，保留 agreed_terms 与 analysis_guide_seen', () => {
    storage.setToken('jwt')
    storage.setUser({ id: 1 })
    storage.setAgreedTerms(CURRENT_TERMS_VERSION)
    storage.markAnalysisGuideSeen()
    useUserStore.setState({ token: 'jwt', user: { id: 1 } as any })

    useUserStore.getState().logout()

    expect(useUserStore.getState().token).toBe('')
    expect(useUserStore.getState().user).toBeNull()
    expect(useUserStore.getState().currentRole).toBe('user')
    expect(storage.getToken()).toBe('')
    expect(storage.hasAgreedCurrentTerms()).toBe(true)
    expect(storage.hasSeenAnalysisGuide()).toBe(true)
  })
})
