import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Button, Image } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import EnvBadge from '@/components/EnvBadge'
import { useUserStore } from '@/store/userStore'
import { switchToCoach, switchToProfile, toastTabNavigationFailure } from '@/utils/tabNav'
import { analysisService } from '@/services/analysisService'
import { deferReLaunch } from '@/utils/deferNavigation'
import { PAYMENT_ENABLED_FLAG } from '@/constants/flags'
import { SCORE_LEVEL_META, scoreLevelFromScore } from '@/constants/scoreLevel'
import { CLUB_TYPE_LABEL } from '@/types/analysis'
import { BRAND_LOGO } from '@/constants/brandAssets'
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

  // 微信审核：不得以「未登录」为由首屏强跳登录页；访客可在首页与 Tab 浏览说明后再主动登录。
  // 已登录但未完成引导 → 跳转引导页
  useEffect(() => {
    if (initialized && token && user && !user.onboarding_completed) {
      deferReLaunch('/pages/onboarding/index')
    }
  }, [initialized, token, user])

  if (!initialized) {
    return (
      <View className='page-loading'>
        <Text>加载中...</Text>
      </View>
    )
  }

  if (!token) {
    const goLogin = () => {
      Taro.navigateTo({ url: '/pages/login/index' })
    }
    const openTerms = () => Taro.navigateTo({ url: '/pages/legal/terms' })
    const openPrivacy = () => Taro.navigateTo({ url: '/pages/legal/privacy' })
    return (
      <View className='home home--guest'>
        <EnvBadge />
        <View className='home__topnav'>
          <View className='home__brand'>
            <View className='home__brand-mark'>
              <Image
                className='home__brand-mark-img'
                src={BRAND_LOGO}
                mode='aspectFill'
              />
            </View>
            <Text className='home__brand-name'>
              领翼<Text className='home__brand-name-em'>golf</Text>
            </Text>
          </View>
          <Text className='home__guest-login-pill' onClick={goLogin}>
            登录
          </Text>
        </View>

        <View className='home__hero home__hero--guest'>
          <View className='home__hero-deco' />
          <Text className='home__hero-eyebrow'>欢迎使用</Text>
          <Text className='home__hero-headline'>可先了解产品与功能</Text>
          <Text className='home__hero-headline'>再选择是否登录</Text>
          <Text className='home__hero-sub'>
            挥杆分析与 AI 对话需微信登录后使用。下方可查看示例报告与协议。
          </Text>
          <Button className='home__hero-cta' onClick={goLogin}>
            登录后开始分析
          </Button>
        </View>

        <View className='home__guest-features'>
          <Text className='home__guest-features-title'>本产品提供</Text>
          <View className='home__guest-feature'>
            <Text className='home__guest-feature-icon'>📹</Text>
            <Text className='home__guest-feature-text'>
              AI 挥杆分析，短视频出报告
            </Text>
          </View>
          <View className='home__guest-feature'>
            <Text className='home__guest-feature-icon'>💬</Text>
            <Text className='home__guest-feature-text'>
              AI 教练在线答疑（生成式内容，仅供参考）
            </Text>
          </View>
          <View className='home__guest-feature'>
            <Text className='home__guest-feature-icon'>📈</Text>
            <Text className='home__guest-feature-text'>
              基于分析的训练计划与打卡
            </Text>
          </View>
        </View>

        <View className='home__quicks'>
          <View className='home__quick home__quick--sample' onClick={() => Taro.navigateTo({ url: '/pages/analysis/report?id=sample' })}>
            <View className='home__quick-icon home__quick-icon--sample'>
              <Text className='home__quick-icon-emoji'>🎬</Text>
            </View>
            <View className='home__quick-text'>
              <Text className='home__quick-title'>先看一份示例报告</Text>
              <Text className='home__quick-desc'>无需登录 · 不消耗次数</Text>
            </View>
            <Text className='home__quick-arrow'>›</Text>
          </View>
          <View className='home__quick' onClick={() => void switchToCoach().catch(toastTabNavigationFailure)}>
            <View className='home__quick-icon home__quick-icon--coach'>
              <Text className='home__quick-icon-emoji'>💬</Text>
            </View>
            <View className='home__quick-text'>
              <Text className='home__quick-title'>AI 教练 · 了解能力</Text>
              <Text className='home__quick-desc'>进入页内说明，对话前需登录</Text>
            </View>
            <Text className='home__quick-arrow'>›</Text>
          </View>
        </View>

        <View className='home__guest-legal'>
          <Text className='home__guest-legal-line'>
            <Text className='home__guest-legal-link' onClick={openTerms}>
              《用户协议》
            </Text>
            <Text> · </Text>
            <Text className='home__guest-legal-link' onClick={openPrivacy}>
              《隐私政策》
            </Text>
          </Text>
        </View>

        <View className='home__section'>
          <View className='home__section-head'>
            <Text className='home__section-title'>最近分析</Text>
          </View>
          <View className='home__empty'>
            <Text className='home__empty-icon'>🔐</Text>
            <Text className='home__empty-text'>登录后保存与查看历史</Text>
            <Text className='home__empty-hint'>浏览示例报告可了解报告形态</Text>
          </View>
        </View>
      </View>
    )
  }

  if (!user) {
    return (
      <View className='page-loading'>
        <Text>加载中...</Text>
      </View>
    )
  }

  const handleStartAnalysis = () => {
    // W7-T2：免费用户本月用完 → 弹开通会员 modal
    // W8-T3：
    //   1. 后端 QUOTA_MODE=unlimited 时返回 analysis_remaining=-1，
    //      该值 < 0 表示"无限"，不应触发耗尽提示。原 `?? 0` 兜底
    //      会把 undefined / null 都当作"已耗尽"，需精确比较。
    //   2. PAYMENT_ENABLED=false（W8 内测期）下不再露"开通会员"按钮，
    //      改为只提示"次数已用完，下月刷新"。
    const remaining = user?.quota?.analysis_remaining
    const exhausted =
      user != null &&
      !user.is_member &&
      typeof remaining === 'number' &&
      remaining === 0
    if (exhausted) {
      if (PAYMENT_ENABLED_FLAG) {
        Taro.showModal({
          title: '本月免费次数已用完',
          content: '下月 1 日自动刷新，或开通会员享受无限分析。',
          confirmText: '开通会员',
          cancelText: '我知道了',
          success: ({ confirm }) => {
            if (confirm) {
              Taro.navigateTo({ url: '/pages/profile/membership' })
            }
          },
        })
      } else {
        Taro.showModal({
          title: '本月次数已用完',
          content: '内测阶段全员可用，下月 1 日自动刷新；如需立即解锁请联系运营。',
          confirmText: '我知道了',
          showCancel: false,
        })
      }
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

  const handleAskCoach = () => {
    // W8-T2：coach 已是 tabBar 页，用 switchTab 而非 navigateTo。
    void switchToCoach().catch(toastTabNavigationFailure)
  }

  const handleOpenProfile = () => {
    void switchToProfile().catch(toastTabNavigationFailure)
  }

  // ====== 首页"主英雄"用最新一次分析的得分作为故事核心 ======
  const latest = recent[0]
  const latestLevel = latest?.score_level ?? scoreLevelFromScore(latest?.overall_score)
  const latestMeta = latestLevel ? SCORE_LEVEL_META[latestLevel] : null
  const hasScore = latest && latest.status === 'completed' && latest.overall_score != null
  const scoreChange = latest?.score_change ?? null

  // ====== 配额文案 ======
  const quotaText = (() => {
    if (!user.quota) return ''
    if (user.is_member) return '会员·分析次数无限'
    if (user.quota.analysis_remaining < 0) return '内测期·次数无限'
    return `本月剩余 ${user.quota.analysis_remaining} / ${user.quota.analysis_total} 次`
  })()

  const chatRemainingText = (() => {
    if (!user.quota) return '聊聊你的挥杆'
    if (user.quota.chat_remaining_today < 0) return '今日无限次问答'
    return `今日剩余 ${user.quota.chat_remaining_today} 次免费问答`
  })()

  // 用户首字母（头像 fallback）：取昵称首字符（中文 1 字、英文 1 字母）
  const avatarInitial = (user.nickname || '球').trim().charAt(0).toUpperCase()

  // ====== 三联统计（来自 user.stats，后端聚合好）======
  const stats = user.stats
  const showSampleCta = recent.length === 0

  return (
    <View className='home'>
      <EnvBadge />

      {/* ============ 1. 顶部品牌 nav ============ */}
      <View className='home__topnav'>
        <View className='home__brand'>
          <View className='home__brand-mark'>
            <Image
              className='home__brand-mark-img'
              src={BRAND_LOGO}
              mode='aspectFill'
            />
          </View>
          <Text className='home__brand-name'>
            领翼<Text className='home__brand-name-em'>golf</Text>
          </Text>
        </View>
        <View className='home__avatar' onClick={handleOpenProfile}>
          {user.avatar_url ? (
            <Image className='home__avatar-img' src={user.avatar_url} mode='aspectFill' />
          ) : (
            <Text className='home__avatar-initial'>{avatarInitial}</Text>
          )}
        </View>
      </View>

      {/* ============ 2. 主英雄：最新得分 / 引导上传 ============ */}
      <View className='home__hero'>
        <View className='home__hero-deco' />
        {hasScore ? (
          <>
            <Text className='home__hero-eyebrow'>最新综合得分</Text>
            <View className='home__hero-score'>
              <Text className='home__hero-score-num'>{latest!.overall_score}</Text>
              <Text className='home__hero-score-unit'>分</Text>
            </View>
            <View className='home__hero-meta'>
              {scoreChange != null && scoreChange !== 0 && (
                <Text
                  className={`home__hero-trend home__hero-trend--${scoreChange > 0 ? 'up' : 'down'}`}
                >
                  {scoreChange > 0 ? '↑' : '↓'} {Math.abs(scoreChange)} 较上次
                </Text>
              )}
              {latestMeta && (
                <Text className='home__hero-level'>
                  {latestMeta.emoji} {latestMeta.label}
                </Text>
              )}
            </View>
          </>
        ) : (
          <>
            <Text className='home__hero-eyebrow'>你好，{user.nickname || '球友'}</Text>
            <Text className='home__hero-headline'>拍一段挥杆</Text>
            <Text className='home__hero-headline'>开启你的 AI 教练之旅</Text>
            <Text className='home__hero-sub'>
              30 秒视频 · 6 维评分 · 个性化训练方案
            </Text>
          </>
        )}

        <Button className='home__hero-cta' onClick={handleStartAnalysis}>
          {hasScore ? '+ 上传新挥杆' : '🎬 开始第一次分析'}
        </Button>
        {quotaText && <Text className='home__hero-quota'>{quotaText}</Text>}
      </View>

      {/* ============ 3. 三联统计 ============ */}
      <View className='home__stats'>
        <View className='home__stat'>
          <Text className='home__stat-val'>{stats?.total_analyses ?? 0}</Text>
          <Text className='home__stat-label'>累计分析</Text>
        </View>
        <View className='home__stat'>
          <Text className='home__stat-val home__stat-val--mint'>
            {stats?.best_score && stats.best_score > 0 ? stats.best_score : '—'}
          </Text>
          <Text className='home__stat-label'>最佳得分</Text>
        </View>
        <View className='home__stat'>
          <Text className='home__stat-val'>{stats?.streak_days ?? 0}</Text>
          <Text className='home__stat-label'>连续天数</Text>
        </View>
      </View>

      {/* ============ 4. 快捷入口（AI 教练 + 示例 banner 兜底）============ */}
      <View className='home__quicks'>
        <View className='home__quick' onClick={handleAskCoach}>
          <View className='home__quick-icon home__quick-icon--coach'>
            <Text className='home__quick-icon-emoji'>💬</Text>
          </View>
          <View className='home__quick-text'>
            <Text className='home__quick-title'>问 AI 教练</Text>
            <Text className='home__quick-desc'>{chatRemainingText}</Text>
          </View>
          <Text className='home__quick-arrow'>›</Text>
        </View>

        {showSampleCta && (
          <View className='home__quick home__quick--sample' onClick={handleTrySample}>
            <View className='home__quick-icon home__quick-icon--sample'>
              <Text className='home__quick-icon-emoji'>🎬</Text>
            </View>
            <View className='home__quick-text'>
              <Text className='home__quick-title'>先看一份示例报告</Text>
              <Text className='home__quick-desc'>了解 AI 能给你什么 · 不消耗次数</Text>
            </View>
            <Text className='home__quick-arrow'>›</Text>
          </View>
        )}
      </View>

      {/* ============ 5. 最近分析列表 ============ */}
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
            <Text className='home__empty-icon'>⛳️</Text>
            <Text className='home__empty-text'>还没有分析记录</Text>
            <Text className='home__empty-hint'>开始第一次，AI 帮你找到挥杆问题</Text>
          </View>
        ) : (
          <View className='home__recent'>
            {recent.map((it) => {
              const level = it.score_level ?? scoreLevelFromScore(it.overall_score)
              const meta = level ? SCORE_LEVEL_META[level] : null
              const change = it.score_change
              const isCompleted = it.status === 'completed'
              return (
                <View
                  key={it.id}
                  className='home__recent-item'
                  onClick={() =>
                    Taro.navigateTo({ url: `/pages/analysis/report?id=${it.id}` })
                  }
                >
                  {it.thumbnail_url ? (
                    <Image
                      className='home__recent-thumb home__recent-thumb--img'
                      src={it.thumbnail_url}
                      mode='aspectFill'
                    />
                  ) : (
                    <View
                      className={`home__recent-thumb home__recent-thumb--${level || 'good'}`}
                    >
                      <Text className='home__recent-thumb-emoji'>
                        {meta?.emoji || '🏌️'}
                      </Text>
                    </View>
                  )}
                  <View className='home__recent-info'>
                    <Text className='home__recent-club'>
                      {CLUB_TYPE_LABEL[it.club_type]}
                    </Text>
                    <Text className='home__recent-date'>{formatDate(it.created_at)}</Text>
                  </View>
                  <View className='home__recent-scorewrap'>
                    {isCompleted ? (
                      <Text
                        className='home__recent-score'
                        style={{ color: meta?.cssVar || 'var(--color-primary)' }}
                      >
                        {it.overall_score ?? '—'}
                      </Text>
                    ) : (
                      <Text className='home__recent-pending'>分析中</Text>
                    )}
                    {change != null && change !== 0 && isCompleted && (
                      <Text
                        className={`home__recent-delta home__recent-delta--${change > 0 ? 'up' : 'down'}`}
                      >
                        {change > 0 ? '↑' : '↓'} {Math.abs(change)}
                      </Text>
                    )}
                  </View>
                </View>
              )
            })}
          </View>
        )}
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
  const sameYear = d.getFullYear() === now.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  if (sameDay) return `今天 ${hh}:${mi}`
  if (sameYear) return `${mm}-${dd} ${hh}:${mi}`
  return `${d.getFullYear()}-${mm}-${dd}`
}
