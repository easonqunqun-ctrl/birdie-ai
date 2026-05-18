/**
 * P-01 / Q-B2：并排对比两份历史报告（综合分与摘要；完整报告仍从列表进详情）。
 */

import { FC, useEffect, useState } from 'react'
import { View, Text, Button, ScrollView } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { analysisService } from '@/services/analysisService'
import { describePageLoadFailure } from '@/services/request'
import { CLUB_TYPE_LABEL } from '@/types/analysis'
import type { AnalysisReportResponse } from '@/types/analysis'
import './compare.scss'

const ComparePage: FC = () => {
  const router = useRouter()
  const { left = '', right = '' } = router.params as { left?: string; right?: string }
  const idL = (left || '').trim()
  const idR = (right || '').trim()

  const [a, setA] = useState<AnalysisReportResponse | null>(null)
  const [b, setB] = useState<AnalysisReportResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!idL || !idR || idL === idR) {
      setError('请选择两篇不同的分析报告')
      setLoading(false)
      return
    }
    Promise.all([analysisService.getReport(idL), analysisService.getReport(idR)])
      .then(([ra, rb]) => {
        setA(ra)
        setB(rb)
        setLoading(false)
      })
      .catch((e: unknown) => {
        setError(describePageLoadFailure(e))
        setLoading(false)
      })
  }, [idL, idR])

  if (loading) {
    return (
      <View className='compare'>
        <Text>加载对比数据…</Text>
      </View>
    )
  }

  if (error || !a || !b) {
    return (
      <View className='compare'>
        <Text className='compare__hint'>{error || '无法加载报告'}</Text>
        <View className='compare__actions'>
          <Button
            onClick={() => Taro.navigateBack().catch(() => undefined)}
          >
            返回
          </Button>
        </View>
      </View>
    )
  }

  const delta = (a.overall_score ?? 0) - (b.overall_score ?? 0)
  const deltaLabel =
    delta === 0
      ? '两次综合分相同。'
      : delta > 0
        ? `左侧比右侧高 ${delta} 分。`
        : `右侧比左侧高 ${Math.abs(delta)} 分。`

  return (
    <ScrollView scrollY className='compare'>
      <View className='compare__head'>
        <Text className='compare__title'>历史报告对比</Text>
        <Text className='compare__hint'>对比两次正式分析的综合分与基础信息</Text>
      </View>

      <View className='compare__row'>
        <View className='compare__col'>
          <Text className='compare__col-label'>
            {CLUB_TYPE_LABEL[a.club_type] ?? '挥杆'} · 较早条目
          </Text>
          <Text className='compare__score'>{a.overall_score ?? '—'}</Text>
          <Text className='compare__meta'>
            {(a.analyzed_at || a.created_at || '').slice(0, 16)}
          </Text>
        </View>
        <View className='compare__col'>
          <Text className='compare__col-label'>
            {CLUB_TYPE_LABEL[b.club_type] ?? '挥杆'} · 较晚条目
          </Text>
          <Text className='compare__score'>{b.overall_score ?? '—'}</Text>
          <Text className='compare__meta'>
            {(b.analyzed_at || b.created_at || '').slice(0, 16)}
          </Text>
        </View>
      </View>

      <View className='compare__delta'>
        <Text>{deltaLabel}</Text>
      </View>

      <View className='compare__actions'>
        <Button
          onClick={() =>
            Taro.navigateTo({ url: `/pages/analysis/report?id=${encodeURIComponent(idL)}` })
          }
        >
          打开左侧完整报告
        </Button>
        <Button
          onClick={() =>
            Taro.navigateTo({ url: `/pages/analysis/report?id=${encodeURIComponent(idR)}` })
          }
        >
          打开右侧完整报告
        </Button>
        <Button onClick={() => Taro.navigateBack().catch(() => undefined)}>返回</Button>
      </View>
    </ScrollView>
  )
}

export default ComparePage
