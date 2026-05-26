/**
 * P2-M9-02：我的装备清单页（列表 + 添加 / 删除）。
 *
 * 简化版（W21 后端 API 就绪即可用），W22 PR 追加编辑页 `club-edit.tsx`
 * 与品牌/型号/loft 等扩展字段；本页负责完成 AC-1/AC-2：
 *
 * - 列表展示已添加球杆，按 sort_order 排
 * - 14 支上限：达到时禁用"添加"按钮 + Toast 提示
 * - 增 / 删（PUT 编辑由 club-edit.tsx W22 接入）
 *
 * 灰度：`PHASE2_PROFILE_V2_ENABLED_FLAG`（constants/flags.ts）；
 *      未启用时此页面应通过 `app.config.ts` 不注册或在 onShow 重定向。
 *      本 PR 不动 app.config.ts；W22 灰度时再注册。
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Picker, ScrollView } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { CLUB_TYPE_GROUPS, CLUB_TYPE_LABEL } from '@/types/analysis'
import type { ClubType } from '@/types/api'
import {
  userClubsService,
  type UserClub,
  type UserClubListResponse,
} from '@/services/userClubs'
import './clubs.scss'

const FLAT_CLUB_TYPES: ClubType[] = CLUB_TYPE_GROUPS.flatMap((g) => g.items)
const FLAT_CLUB_LABELS: string[] = FLAT_CLUB_TYPES.map((t) => CLUB_TYPE_LABEL[t])

const MyClubsPage: FC = () => {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<UserClubListResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pickerIndex, setPickerIndex] = useState(6) // 默认 7 号铁

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await userClubsService.list()
      setData(resp)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '加载失败'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleAdd = async () => {
    if (!data || data.remaining <= 0) {
      Taro.showToast({ title: `已达 ${data?.max_clubs ?? 14} 支上限`, icon: 'none' })
      return
    }
    const clubType = FLAT_CLUB_TYPES[pickerIndex]
    try {
      await userClubsService.create({
        club_type: clubType,
        sort_order: data.total,
        is_active: true,
      })
      Taro.showToast({ title: '已添加', icon: 'success' })
      await load()
    } catch (e) {
      const msg = e instanceof Error ? e.message : '添加失败'
      Taro.showToast({ title: msg, icon: 'none' })
    }
  }

  const handleDelete = async (club: UserClub) => {
    const res = await Taro.showModal({
      title: '确认删除',
      content: `删除「${CLUB_TYPE_LABEL[club.club_type]}」？历史挥杆记录不受影响。`,
    })
    if (!res.confirm) return
    try {
      await userClubsService.remove(club.id)
      Taro.showToast({ title: '已删除', icon: 'success' })
      await load()
    } catch (e) {
      const msg = e instanceof Error ? e.message : '删除失败'
      Taro.showToast({ title: msg, icon: 'none' })
    }
  }

  if (loading) {
    return (
      <View className='my-clubs my-clubs--empty'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error) {
    return (
      <View className='my-clubs my-clubs--empty'>
        <Text className='my-clubs__error'>{error}</Text>
        <View className='my-clubs__retry' onClick={() => void load()}>
          <Text>重试</Text>
        </View>
      </View>
    )
  }

  const total = data?.total ?? 0
  const max = data?.max_clubs ?? 14
  const remaining = data?.remaining ?? 14

  return (
    <View className='my-clubs'>
      <View className='my-clubs__header'>
        <Text className='my-clubs__title'>我的装备</Text>
        <Text className='my-clubs__count'>
          {total} / {max} 支
        </Text>
      </View>

      <ScrollView scrollY className='my-clubs__list'>
        {data?.items.length === 0 && (
          <View className='my-clubs__empty-hint'>
            <Text>暂无装备，添加你的常用球杆 →</Text>
          </View>
        )}
        {data?.items.map((club) => (
          <View key={club.id} className='my-clubs__item'>
            <View className='my-clubs__item-main'>
              <Text className='my-clubs__item-type'>
                {CLUB_TYPE_LABEL[club.club_type] ?? club.club_type}
              </Text>
              {club.nickname && (
                <Text className='my-clubs__item-nickname'>「{club.nickname}」</Text>
              )}
              <Text className='my-clubs__item-yardage'>
                {club.self_yardage_m != null ? `${club.self_yardage_m}m` : '未填码数'}
              </Text>
            </View>
            <View
              className='my-clubs__item-delete'
              onClick={() => void handleDelete(club)}
            >
              <Text>删除</Text>
            </View>
          </View>
        ))}
      </ScrollView>

      <View className='my-clubs__add-bar'>
        <Picker
          mode='selector'
          range={FLAT_CLUB_LABELS}
          value={pickerIndex}
          onChange={(e) => setPickerIndex(Number(e.detail.value))}
        >
          <View className='my-clubs__picker'>
            <Text>{FLAT_CLUB_LABELS[pickerIndex]}</Text>
            <Text className='my-clubs__picker-arrow'>▾</Text>
          </View>
        </Picker>
        <View
          className={`my-clubs__add-btn ${
            remaining <= 0 ? 'my-clubs__add-btn--disabled' : ''
          }`}
          onClick={() => void handleAdd()}
        >
          <Text>添加</Text>
        </View>
      </View>
    </View>
  )
}

export default MyClubsPage
