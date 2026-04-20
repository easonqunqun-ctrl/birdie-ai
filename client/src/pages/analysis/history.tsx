/**
 * 我的分析报告 · 历史列表页
 *
 * 核心能力：
 *   1. 分页拉取（page_size = 20）；首屏 loading + 列表 loading-more
 *   2. 下拉刷新（小程序原生 `usePullDownRefresh` + `stopPullDownRefresh`）
 *   3. 上拉加载更多（`useReachBottom`，总条数没到就继续拉）
 *   4. 空态 / 错误态 / 完成态三种状态区分
 *   5. 卡片点击 → 进入报告页
 *
 * 设计说明：
 *   - 不存 list 到 zustand；历史列表属于"消费型数据"，进入页拉即可，退出页回收
 *   - 失败不做重试，直接显示"重新加载"按钮给用户兜底
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Image, Button, ScrollView } from '@tarojs/components'
import Taro, { usePullDownRefresh, useReachBottom } from '@tarojs/taro'
import { analysisService } from '@/services/analysisService'
import { SCORE_LEVEL_META, scoreLevelFromScore } from '@/constants/scoreLevel'
import { CLUB_TYPE_LABEL } from '@/types/analysis'
import type { AnalysisListItem } from '@/types/analysis'
import './history.scss'

const PAGE_SIZE = 20

const HistoryPage: FC = () => {
  const [items, setItems] = useState<AnalysisListItem[]>([])
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true) // 首屏 loading
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const hasMore = items.length < total

  const fetchPage = useCallback(
    async (nextPage: number, mode: 'init' | 'refresh' | 'more') => {
      try {
        const res = await analysisService.listAnalyses({
          page: nextPage,
          page_size: PAGE_SIZE,
        })
        setItems((prev) => (mode === 'more' ? [...prev, ...res.items] : res.items))
        setTotal(res.total)
        setPage(nextPage)
        setError(null)
      } catch (e) {
        if (mode === 'init') setError((e as Error).message || '加载失败')
        else Taro.showToast({ title: '加载失败', icon: 'none' })
      } finally {
        if (mode === 'init') setLoading(false)
        if (mode === 'refresh') Taro.stopPullDownRefresh()
        if (mode === 'more') setLoadingMore(false)
      }
    },
    [],
  )

  useEffect(() => {
    fetchPage(1, 'init')
  }, [fetchPage])

  usePullDownRefresh(() => {
    fetchPage(1, 'refresh')
  })

  useReachBottom(() => {
    if (loadingMore || !hasMore || loading) return
    setLoadingMore(true)
    fetchPage(page + 1, 'more')
  })

  const goReport = (id: string) => {
    Taro.navigateTo({ url: `/pages/analysis/report?id=${id}` })
  }

  const goCapture = () => {
    Taro.reLaunch({ url: '/pages/analysis/capture' })
  }

  const handleRetry = () => {
    setLoading(true)
    setError(null)
    fetchPage(1, 'init')
  }

  // -------- 渲染 --------
  if (loading) {
    return (
      <View className='history history--loading'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error) {
    return (
      <View className='history history--error'>
        <Text className='history__error-icon'>😣</Text>
        <Text className='history__error-msg'>{error}</Text>
        <Button className='history__btn' onClick={handleRetry}>重新加载</Button>
      </View>
    )
  }

  if (items.length === 0) {
    return (
      <View className='history history--empty'>
        <Text className='history__empty-icon'>⛳️</Text>
        <Text className='history__empty-title'>还没有分析记录</Text>
        <Text className='history__empty-desc'>
          拍一段挥杆视频，AI 会给你完整的动作诊断与训练建议。
        </Text>
        <Button className='history__btn history__btn--primary' onClick={goCapture}>
          开始分析
        </Button>
      </View>
    )
  }

  return (
    <ScrollView scrollY className='history'>
      <View className='history__summary'>
        <Text className='history__summary-value'>{total}</Text>
        <Text className='history__summary-label'>条分析记录</Text>
      </View>

      {items.map((it) => {
        const level = it.score_level ?? scoreLevelFromScore(it.overall_score)
        const meta = level ? SCORE_LEVEL_META[level] : null
        const date = formatDate(it.analyzed_at || it.created_at)
        return (
          <View key={it.id} className='history__card' onClick={() => goReport(it.id)}>
            <View className='history__thumb'>
              {it.thumbnail_url ? (
                <Image mode='aspectFill' src={it.thumbnail_url} className='history__thumb-img' />
              ) : (
                <Text className='history__thumb-emoji'>{meta?.emoji || '🏌️'}</Text>
              )}
            </View>
            <View className='history__info'>
              <View className='history__info-head'>
                <Text className='history__club'>{CLUB_TYPE_LABEL[it.club_type]}</Text>
                {it.status !== 'completed' && (
                  <Text className='history__status-tag'>
                    {it.status === 'failed' ? '失败' : '分析中'}
                  </Text>
                )}
              </View>
              <Text className='history__date'>{date}</Text>
              {typeof it.score_change === 'number' && it.score_change !== 0 && (
                <Text
                  className={[
                    'history__change',
                    it.score_change > 0 ? 'history__change--up' : 'history__change--down',
                  ].join(' ')}
                >
                  {it.score_change > 0 ? '▲' : '▼'} {Math.abs(it.score_change)}
                </Text>
              )}
            </View>
            <View className='history__score'>
              {typeof it.overall_score === 'number' ? (
                <>
                  <Text className='history__score-value' style={{ color: meta?.cssVar }}>
                    {it.overall_score}
                  </Text>
                  <Text className='history__score-level'>{meta?.label || ''}</Text>
                </>
              ) : (
                <Text className='history__score-empty'>—</Text>
              )}
            </View>
          </View>
        )
      })}

      {loadingMore && (
        <View className='history__more'>
          <Text>加载中…</Text>
        </View>
      )}
      {!hasMore && (
        <View className='history__more'>
          <Text className='history__more-end'>— 没有更多了 —</Text>
        </View>
      )}
    </ScrollView>
  )
}

export default HistoryPage

// =====================================================================
// 工具
// =====================================================================
function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  if (sameDay) return `今天 ${hh}:${mi}`
  if (yyyy === now.getFullYear()) return `${mm}-${dd} ${hh}:${mi}`
  return `${yyyy}-${mm}-${dd}`
}
