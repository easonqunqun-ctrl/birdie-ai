/**
 * Tab 页到期弹窗：进入时拉 membership 再交给 `useMembershipExpiringSoonModal`。
 *
 * 用于首页 / 训练 / 教练 Tab（Q-B1 余量 · v1.0.4+）；会员页仍自行维护 memInfo state。
 */

import { useCallback, useEffect, useState } from 'react'
import { useDidShow } from '@tarojs/taro'
import { paymentService } from '@/services/paymentService'
import type { MembershipInfo } from '@/types/payment'
import { useMembershipExpiringSoonModal } from './useMembershipExpiringSoonModal'

/** 供单测：拉会员信息，失败返回 null（与 membership 页静默策略一致） */
export async function fetchMembershipForExpiringModal(): Promise<MembershipInfo | null> {
  try {
    return await paymentService.getMembership()
  } catch {
    return null
  }
}

/**
 * @param enabled 通常为 `!!token`；未登录不请求
 */
export function useMembershipExpiringSoonModalOnShow(enabled: boolean): void {
  const [memInfo, setMemInfo] = useState<MembershipInfo | null>(null)

  const refresh = useCallback(async () => {
    if (!enabled) {
      setMemInfo(null)
      return
    }
    const m = await fetchMembershipForExpiringModal()
    setMemInfo(m)
  }, [enabled])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useDidShow(() => {
    void refresh()
  })

  useMembershipExpiringSoonModal(memInfo)
}
