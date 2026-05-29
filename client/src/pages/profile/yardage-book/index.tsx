/**
 * P2-M10-03 · 个人 yardage book
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Button, ScrollView } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { CLUB_TYPE_LABEL } from '@/types/analysis'
import {
  yardageBookService,
  type YardageBookClubItem,
} from '@/services/yardageBookService'
import { PHASE2_YARDAGE_BOOK_ENABLED_FLAG } from '@/constants/flags'
import './yardage-book.scss'

const YardageBookPage: FC = () => {
  const [loading, setLoading] = useState(true)
  const [clubs, setClubs] = useState<YardageBookClubItem[]>([])
  const [error, setError] = useState<string | null>(null)

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
      setClubs(resp.clubs || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleEdit = () => {
    Taro.navigateTo({ url: '/pages/profile/clubs' })
  }

  return (
    <View className='yardage-book'>
      <View className='yardage-book__intro'>
        <Text className='yardage-book__intro-text'>
          记录每根杆能打多远；未自填时，分析历史满 5 次可自动反推。
        </Text>
      </View>

      {loading && <Text className='yardage-book__hint'>加载中…</Text>}
      {error && <Text className='yardage-book__error'>{error}</Text>}

      <ScrollView scrollY className='yardage-book__list'>
        {clubs.map((club) => {
          const label =
            CLUB_TYPE_LABEL[club.club_type as keyof typeof CLUB_TYPE_LABEL] || club.club_type
          const yardsText =
            club.my_yards != null
              ? `${club.my_yards} 码`
              : club.source === 'none'
                ? `采样不足 (${club.sample_count}/5)`
                : '—'
          const stdText =
            club.std_yards != null ? `±${club.std_yards}` : club.source === 'self' ? '自填' : '—'
          return (
            <View key={club.club_id} className='yardage-book__row'>
              <View className='yardage-book__row-main'>
                <Text className='yardage-book__club'>{club.nickname || label}</Text>
                <Text className='yardage-book__yards'>{yardsText}</Text>
              </View>
              <View className='yardage-book__row-meta'>
                <Text className='yardage-book__meta'>
                  {club.source === 'inferred' ? `反推 · 样本 ${club.sample_count}` : stdText}
                </Text>
                <Button
                  className='yardage-book__edit-btn'
                  size='mini'
                  onClick={handleEdit}
                >
                  去装备编辑
                </Button>
              </View>
            </View>
          )
        })}
        {!loading && !error && clubs.length === 0 && (
          <Text className='yardage-book__hint'>请先在「我的装备」添加球杆</Text>
        )}
      </ScrollView>
    </View>
  )
}

export default YardageBookPage
