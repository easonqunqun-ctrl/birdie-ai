/**
 * P2-M10-03 · 个人 yardage book（列表 + 页内自填码数）
 */

import { FC, useCallback, useEffect, useMemo, useState } from 'react'
import { View, Text, Button, ScrollView, Input } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { CLUB_TYPE_LABEL } from '@/types/analysis'
import {
  yardageBookService,
  type YardageBookClubItem,
} from '@/services/yardageBookService'
import { PHASE2_YARDAGE_BOOK_ENABLED_FLAG } from '@/constants/flags'
import './index.scss'

function parseYardageInput(raw: string): number | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const n = Number.parseInt(trimmed, 10)
  if (!Number.isFinite(n) || n < 1 || n > 400) return null
  return n
}

const YardageBookPage: FC = () => {
  const [loading, setLoading] = useState(true)
  const [clubs, setClubs] = useState<YardageBookClubItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    if (!PHASE2_YARDAGE_BOOK_ENABLED_FLAG) {
      setError('功能尚未开放')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const resp = await yardageBookService.getMine()
      const list = resp.clubs || []
      setClubs(list)
      const nextDrafts: Record<string, string> = {}
      for (const club of list) {
        if (club.my_yards != null) {
          nextDrafts[club.club_id] = String(club.my_yards)
        }
      }
      setDrafts(nextDrafts)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const dirtyClubIds = useMemo(() => {
    const dirty: string[] = []
    for (const club of clubs) {
      const draft = drafts[club.club_id] ?? ''
      const parsed = parseYardageInput(draft)
      const current = club.my_yards ?? null
      if (parsed !== current) {
        dirty.push(club.club_id)
      }
    }
    return dirty
  }, [clubs, drafts])

  const handleDraftChange = (clubId: string, value: string) => {
    setDrafts((prev) => ({ ...prev, [clubId]: value.replace(/[^\d]/g, '') }))
  }

  const handleSave = async () => {
    if (saving || dirtyClubIds.length === 0) return
    const payload = dirtyClubIds.map((clubId) => {
      const parsed = parseYardageInput(drafts[clubId] ?? '')
      return { club_id: clubId, self_yardage_m: parsed }
    })
    const invalid = payload.find((p) => p.self_yardage_m === null && (drafts[p.club_id] ?? '').trim())
    if (invalid) {
      Taro.showToast({ title: '码数请填 1–400 的整数', icon: 'none' })
      return
    }
    setSaving(true)
    try {
      Taro.showLoading({ title: '保存中' })
      const resp = await yardageBookService.updateMine(payload)
      Taro.hideLoading()
      setClubs(resp.clubs || [])
      const nextDrafts: Record<string, string> = {}
      for (const club of resp.clubs || []) {
        if (club.my_yards != null) {
          nextDrafts[club.club_id] = String(club.my_yards)
        }
      }
      setDrafts(nextDrafts)
      Taro.showToast({ title: '已保存', icon: 'success' })
    } catch (e) {
      Taro.hideLoading()
      Taro.showToast({
        title: e instanceof Error ? e.message : '保存失败',
        icon: 'none',
      })
    } finally {
      setSaving(false)
    }
  }

  const handleManageClubs = () => {
    Taro.navigateTo({ url: '/pages/profile/clubs' })
  }

  return (
    <View className='yardage-book'>
      <View className='yardage-book__intro'>
        <Text className='yardage-book__intro-text'>
          记录每根杆能打多远；未自填时，分析历史满 5 次可自动反推。可直接在下方填写码数。
        </Text>
      </View>

      {loading && <Text className='yardage-book__hint'>加载中…</Text>}
      {error && <Text className='yardage-book__error'>{error}</Text>}

      <ScrollView scrollY className='yardage-book__list'>
        {clubs.map((club) => {
          const label =
            CLUB_TYPE_LABEL[club.club_type as keyof typeof CLUB_TYPE_LABEL] || club.club_type
          const draft = drafts[club.club_id] ?? ''
          const inferredHint =
            club.source === 'inferred'
              ? `反推 · 样本 ${club.sample_count} · ±${club.std_yards ?? '—'}`
              : club.source === 'none'
                ? `采样不足 (${club.sample_count}/5)`
                : '自填'
          return (
            <View key={club.club_id} className='yardage-book__row'>
              <View className='yardage-book__row-main'>
                <Text className='yardage-book__club'>{club.nickname || label}</Text>
                <View className='yardage-book__input-wrap'>
                  <Input
                    className='yardage-book__input'
                    type='number'
                    placeholder='码数'
                    value={draft}
                    onInput={(e) => handleDraftChange(club.club_id, e.detail.value)}
                  />
                  <Text className='yardage-book__unit'>码</Text>
                </View>
              </View>
              <View className='yardage-book__row-meta'>
                <Text className='yardage-book__meta'>{inferredHint}</Text>
              </View>
            </View>
          )
        })}
        {!loading && !error && clubs.length === 0 && (
          <Text className='yardage-book__hint'>请先在「我的装备」添加球杆</Text>
        )}
      </ScrollView>

      <View className='yardage-book__footer'>
        <Button
          className='yardage-book__save-btn'
          disabled={saving || dirtyClubIds.length === 0}
          loading={saving}
          onClick={handleSave}
        >
          {saving ? '保存中…' : dirtyClubIds.length > 0 ? `保存 ${dirtyClubIds.length} 项` : '已是最新'}
        </Button>
        <Button className='yardage-book__link-btn' size='mini' onClick={handleManageClubs}>
          管理装备
        </Button>
      </View>
    </View>
  )
}

export default YardageBookPage
