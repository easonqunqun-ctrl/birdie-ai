/**
 * `useMembershipExpiringSoonModalOnShow` 单测
 */

import { renderHook, waitFor } from '@testing-library/react'
import Taro from '@tarojs/taro'
import {
  fetchMembershipForExpiringModal,
  useMembershipExpiringSoonModalOnShow,
} from '@/hooks/useMembershipExpiringSoonModalOnShow'
import { paymentService } from '@/services/paymentService'
import type { MembershipInfo } from '@/types/payment'

jest.mock('@/services/paymentService', () => ({
  paymentService: {
    getMembership: jest.fn(),
  },
}))

const mockGetMembership = paymentService.getMembership as jest.Mock

const sampleMembership: MembershipInfo = {
  is_member: true,
  membership_type: 'monthly',
  expires_at: '2026-05-25T10:00:00+08:00',
  days_remaining: 3,
  auto_renew: false,
}

describe('fetchMembershipForExpiringModal', () => {
  beforeEach(() => {
    mockGetMembership.mockReset()
  })

  it('成功时返回 membership', async () => {
    mockGetMembership.mockResolvedValueOnce(sampleMembership)
    await expect(fetchMembershipForExpiringModal()).resolves.toEqual(sampleMembership)
  })

  it('失败时返回 null 且不抛错', async () => {
    mockGetMembership.mockRejectedValueOnce(new Error('network'))
    await expect(fetchMembershipForExpiringModal()).resolves.toBeNull()
  })
})

describe('useMembershipExpiringSoonModalOnShow', () => {
  beforeEach(() => {
    mockGetMembership.mockReset()
    ;(Taro.showModal as jest.Mock).mockClear()
  })

  it('enabled=true 时拉取 membership', async () => {
    mockGetMembership.mockResolvedValue(sampleMembership)
    renderHook(() => useMembershipExpiringSoonModalOnShow(true))
    await waitFor(() => {
      expect(mockGetMembership).toHaveBeenCalled()
    })
  })

  it('enabled=false 时不请求', async () => {
    mockGetMembership.mockResolvedValue(sampleMembership)
    renderHook(() => useMembershipExpiringSoonModalOnShow(false))
    await waitFor(() => {
      expect(mockGetMembership).not.toHaveBeenCalled()
    })
  })

  it('请求失败时不抛错', async () => {
    mockGetMembership.mockRejectedValue(new Error('fail'))
    expect(() => {
      renderHook(() => useMembershipExpiringSoonModalOnShow(true))
    }).not.toThrow()
    await waitFor(() => {
      expect(mockGetMembership).toHaveBeenCalled()
    })
  })
})
