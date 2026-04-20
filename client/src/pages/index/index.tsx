import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useUserStore } from '@/store/userStore'
import { analysisService } from '@/services/analysisService'
import { SCORE_LEVEL_META, scoreLevelFromScore } from '@/constants/scoreLevel'
import { CLUB_TYPE_LABEL } from '@/types/analysis'
import type { AnalysisListItem } from '@/types/analysis'
import './index.scss'

const HomePage: FC = () => {
  const { user, token, initialized, bootstrap, fetchMe } = useUserStore()
  const [recent, setRecent] = useState<AnalysisListItem[]>([])

  const loadRecent = useCallback(async () => {
    try {
      const res = await analysisService.listAnalyses({ page: 1, page_size: 3 })
      setRecent(res.items)
    } catch {
      // 首页"最近分析"失败不打断用户；悄悄兜底为空态
      setRecent([])
    }
  }, [])

  useEffect(() => {
    if (!initialized) {
      bootstrap()
    }
  }, [initialized, bootstrap])

  useDidShow(() => {
    if (token) {
      fetchMe().catch(() => undefined)
      loadRecent()
    }
  })

  // 未登录 → 跳转登录页
  useEffect(() => {
    if (initialized && !token) {
      Taro.reLaunch({ url: '/pages/login/index' })
    }
    // 已登录但未完成引导 → 跳转引导页
    if (initialized && token && user && !user.onboarding_completed) {
      Taro.reLaunch({ url: '/pages/onboarding/index' })
    }
  }, [initialized, token, user])

  if (!initialized || !user) {
    return (
      <View className='page-loading'>
        <Text>加载中...</Text>
      </View>
    )
  }

  const handleStartAnalysis = () => {
    // 配额为 0：免费用户本月用完 → 提示"去升级"，会员入口由 W7 再上
    const remaining = user?.quota?.analysis_remaining ?? 0
    if (user && remaining <= 0) {
      Taro.showModal({
        title: '本月免费次数已用完',
        content: '你本月的免费分析已用完，下月 1 日自动刷新，或升级会员享受无限分析（即将上线）。',
        showCancel: false,
        confirmText: '我知道了',
      })
      return
    }
    Taro.navigateTo({ url: '/pages/analysis/capture' })
  }

  /**
   * 示例视频体验（MVP §3.6）：直接跳到 report 页用特殊 id=sample 拉固定数据。
   * 不扣配额，不入历史。仅在"从未做过分析"的新用户首页展示，引导他们感受产品价值。
   */
  const handleTrySample = () => {
    Taro.navigateTo({ url: '/pages/analysis/report?id=sample' })
  }

  /**
   * "问 AI 教练"快捷入口（T5）：
   * - 无 analysis_id，后端走通用 system prompt（会拉最近一次分析作背景，由 build_system_prompt 负责）
   * - 首页入口用"次要"样式，和"开始分析"主 CTA 区分
   */
  const handleAskCoach = () => {
    Taro.navigateTo({ url: '/pages/coach/index' })
  }

  const showSampleCta = recent.length === 0

  return (
    <View className='home'>
      <View className='home__hero'>
        <Text className='home__greeting'>
          你好，{user.nickname || '球友'} 👋
        </Text>
        <Text className='home__subtitle'>拍一段挥杆视频，AI 帮你找到问题</Text>

        <View className='home__cta-card'>
          <Button className='home__cta-btn' onClick={handleStartAnalysis}>
            开始分析
          </Button>
          {user.membership_type === 'free' && user.quota && (
            <Text className='home__quota'>
              本月剩余免费次数：{user.quota.analysis_remaining} / {user.quota.analysis_total}
            </Text>
          )}
        </View>

        {showSampleCta && (
          <View className='home__sample' onClick={handleTrySample}>
            <Text className='home__sample-icon'>🎬</Text>
            <View className='home__sample-text'>
              <Text className='home__sample-title'>先看一份示例报告</Text>
              <Text className='home__sample-desc'>了解 AI 能给你什么 · 不消耗次数</Text>
            </View>
            <Text className='home__sample-arrow'>›</Text>
          </View>
        )}

        <View className='home__coach-cta' onClick={handleAskCoach}>
          <Text className='home__coach-cta-icon'>💬</Text>
          <View className='home__coach-cta-text'>
            <Text className='home__coach-cta-title'>问 AI 教练</Text>
            <Text className='home__coach-cta-desc'>
              {user.quota && user.quota.chat_remaining_today >= 0
                ? `今日剩余 ${user.quota.chat_remaining_today} 次免费问答`
                : '会员无限次问答'}
            </Text>
          </View>
          <Text className='home__coach-cta-arrow'>›</Text>
        </View>
      </View>

      <View className='home__section'>
        <View className='home__section-head'>
          <Text className='home__section-title'>最近分析</Text>
          {recent.length > 0 && (
            <Text
              className='home__section-action'
              onClick={() => Taro.navigateTo({ url: '/pages/analysis/history' })}
            >
              查看全部 ›
            </Text>
          )}
        </View>
        {recent.length === 0 ? (
          <View className='home__empty'>
            <Text>暂无分析记录，开始第一次吧</Text>
          </View>
        ) : (
          <View className='home__recent'>
            {recent.map((it) => {
              const level = it.score_level ?? scoreLevelFromScore(it.overall_score)
              const meta = level ? SCORE_LEVEL_META[level] : null
              return (
                <View
                  key={it.id}
                  className='home__recent-item'
                  onClick={() => Taro.navigateTo({ url: `/pages/analysis/report?id=${it.id}` })}
                >
                  <View className='home__recent-thumb'>
                    <Text className='home__recent-emoji'>{meta?.emoji || '🏌️'}</Text>
                  </View>
                  <View className='home__recent-info'>
                    <Text className='home__recent-club'>{CLUB_TYPE_LABEL[it.club_type]}</Text>
                    <Text className='home__recent-date'>{formatDate(it.created_at)}</Text>
                  </View>
                  <Text
                    className='home__recent-score'
                    style={{ color: meta?.cssVar || 'var(--color-primary)' }}
                  >
                    {it.overall_score ?? '—'}
                  </Text>
                </View>
              )
            })}
          </View>
        )}
      </View>

      <View className='home__section'>
        <Text className='home__section-title'>AI 小贴士</Text>
        <View className='home__tip-card'>
          <Text>“练球前的 5 分钟热身，可以让你的挥杆更稳定。”</Text>
        </View>
      </View>
    </View>
  )
}

export default HomePage

function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  if (sameDay) return `今天 ${hh}:${mi}`
  return `${mm}-${dd} ${hh}:${mi}`
}
