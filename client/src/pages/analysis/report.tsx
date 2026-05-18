/**
 * 分析报告页（MVP §4.3 完整 UI）
 *
 * 6 个区域（对应 docs/12 T5 范围）：
 *   1. 视频回放（<Video> + 倍速切换 + 阶段色条跳帧）
 *   2. 综合评分（大字 + score_change + 分级徽章）
 *   3. 六维雷达图（手绘 Canvas 2d，点击顶点定位到阶段）
 *   4. 问题诊断（按 severity 排序 + 关键帧图 + 点击跳帧）
 *   5. 训练建议（drill 详情卡 + 「一键加入本周训练计划」→ POST /training-plan/from-analysis）
 *   6. 底部动作栏（分享：`open-type=share`；对比历史→报告列表；问 AI：`switchToCoach`）
 *   7. 删除：仅顶部「更多」操作表（不做左滑，避免与纵向滚动、视频手势冲突）
 *
 * 关键工程决策：
 *   - `phase_scores / phase_timestamps` 是 dict[str, {...}]，需要遍历 PHASE_ORDER
 *     保证 6 阶段顺序稳定（后端返回的字典在 JSON 里顺序不保证）
 *   - 视频跳帧用 Taro.createVideoContext(id).seek(seconds)
 *   - 倍速依靠 Video 的 playbackRate prop；切换后需要 key 变化强制重建才能生效的
 *     问题在 Taro 3.6+ 已修；这里通过一个 `videoKey` 作为双保险
 *   - 关键帧图片 onError 时 fallback 到视频 poster，保证 MVP mock 期（key_frame_url 空）
 *     不出现破图
 */

import { FC, useEffect, useMemo, useState } from 'react'
import { View, Text, Video, Image, Button, ScrollView } from '@tarojs/components'
import Taro, { useRouter, useShareAppMessage } from '@tarojs/taro'
import { analysisService } from '@/services/analysisService'
import { describePageLoadFailure, isRequestError } from '@/services/request'
import { shareService, type PublicReport } from '@/services/shareService'
import { trainingService } from '@/services/trainingService'
import { useUserStore } from '@/store/userStore'
import { switchToCoach, toastTabNavigationFailure } from '@/utils/tabNav'
import { getDrillDetail } from '@/constants/drillLibrary'
import { SCORE_LEVEL_META, scoreLevelFromScore } from '@/constants/scoreLevel'
import {
  PHASE_COLOR,
  PHASE_FULL_LABEL,
  PHASE_LABEL,
  PHASE_ORDER,
  SwingPhaseKey,
} from '@/constants/phaseLabels'
import { CAMERA_ANGLE_LABEL, CLUB_TYPE_LABEL } from '@/types/analysis'
import type { AnalysisReportResponse, PhaseWindow } from '@/types/analysis'
import RadarChart, { RadarAxis } from '@/components/RadarChart'
import '@/components/RadarChart.scss'
import './report.scss'

const VIDEO_ID = 'report-video'
const SEVERITY_SORT: Record<string, number> = { high: 0, medium: 1, low: 2 }
const SEVERITY_LABEL: Record<string, string> = {
  high: '严重',
  medium: '中等',
  low: '轻微',
}
const PLAYBACK_RATES = [0.5, 1, 1.5, 2] as const

function resolveAnalysisIdFromRoute(params: {
  id?: string
  scene?: string
}): string {
  const id = (params.id || '').trim()
  if (id) return id
  const raw = (params.scene || '').trim()
  if (!raw) return ''
  let decoded = raw
  try {
    decoded = decodeURIComponent(raw)
  } catch {
    /* 保持 raw */
  }
  const m = /^i=([A-Za-z0-9_]+)$/.exec(decoded)
  return m ? m[1] : ''
}

const ReportPage: FC = () => {
  const router = useRouter()
  const params = router.params as { id?: string; from_share?: string; scene?: string }
  const analysisId = resolveAnalysisIdFromRoute(params)
  // W7-T5：`from_share=1` 的 path 由朋友分享出来，被分享者点进来走"脱敏公开报告"分支
  const fromShare = params.from_share === '1'
  const currentUserToken = useUserStore((s) => s.token)

  const [report, setReport] = useState<AnalysisReportResponse | null>(null)
  const [publicReport, setPublicReport] = useState<PublicReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [rate, setRate] = useState<number>(1)
  const [syncingPlan, setSyncingPlan] = useState(false)
  /** 服务端生成的小程序码 PNG，用于分享卡片配图（O-11/O-12） */
  const [shareImageUrl, setShareImageUrl] = useState('')

  useEffect(() => {
    if (!analysisId) {
      setError('缺少分析 ID')
      setLoading(false)
      return
    }
    // 拉完整报告：未登录直接抛 401 → fallback 到公开版；
    // 已登录但不是本人 → 后端 /analyses/{id} 返回 403（analysis_service），也 fallback
    const loadFull = analysisService.getReport(analysisId)
    if (fromShare || !currentUserToken) {
      // 明确是分享链接或未登录 → 直接拿公开版，不去撞 401/403
      shareService
        .getPublicReport(analysisId)
        .then((r) => {
          setPublicReport(r)
          setLoading(false)
        })
        .catch((e: unknown) => {
          setError(describePageLoadFailure(e))
          setLoading(false)
        })
      return
    }
    loadFull
      .then((r) => {
        setReport(r)
        setLoading(false)
      })
      .catch((e: unknown) => {
        // 不是自己的 → 尝试公开版兜底
        shareService
          .getPublicReport(analysisId)
          .then((pr) => {
            setPublicReport(pr)
            setLoading(false)
          })
          .catch((inner: unknown) => {
            setError(describePageLoadFailure(inner))
            setLoading(false)
          })
      })
  }, [analysisId, fromShare, currentUserToken])

  useEffect(() => {
    if (!analysisId || analysisId === 'sample' || !currentUserToken || fromShare) {
      setShareImageUrl('')
      return
    }
    analysisService
      .createShareCard(analysisId)
      .then((r) => setShareImageUrl(r.wxa_code_url || ''))
      .catch(() => setShareImageUrl(''))
  }, [analysisId, currentUserToken, fromShare])

  // 默认给 Taro.setNavigationBarTitle 一个更友好的标题
  useEffect(() => {
    if (report) {
      Taro.setNavigationBarTitle({
        title: `${CLUB_TYPE_LABEL[report.club_type] ?? '挥杆'}分析报告`,
      }).catch(() => undefined)
    }
  }, [report])

  // ---------------- 派生数据 ----------------
  const radarAxes: RadarAxis[] = useMemo(() => {
    if (!report?.phase_scores) return []
    return PHASE_ORDER.map((key) => {
      const ps = report.phase_scores?.[key]
      return {
        key,
        label: PHASE_LABEL[key],
        score: ps?.score ?? 0,
        is_weakest: ps?.is_weakest ?? false,
      }
    })
  }, [report])

  const sortedIssues = useMemo(() => {
    if (!report) return []
    return [...report.issues].sort(
      (a, b) => (SEVERITY_SORT[a.severity] ?? 9) - (SEVERITY_SORT[b.severity] ?? 9),
    )
  }, [report])

  const scoreLevel = report?.score_level ?? scoreLevelFromScore(report?.overall_score)
  const levelMeta = scoreLevel ? SCORE_LEVEL_META[scoreLevel] : null

  const videoSrc = report?.skeleton_video_url || report?.video_url || ''

  // ---------------- 事件 ----------------
  const seekTo = (seconds: number) => {
    try {
      const ctx = Taro.createVideoContext(VIDEO_ID)
      ctx.seek(seconds)
      ctx.play()
    } catch {
      // createVideoContext 在 H5 可能无此方法；静默兜底
    }
  }

  // 倍速切换：Taro `<Video>` 的 TS 类型没暴露 playbackRate prop（但小程序底层支持），
  // 改走 VideoContext.playbackRate() 指令，避免用 as any 绕 TS。
  useEffect(() => {
    if (!report) return
    try {
      Taro.createVideoContext(VIDEO_ID).playbackRate(rate)
    } catch {
      /* noop */
    }
  }, [rate, report])

  const tapPhase = (key: string) => {
    const ts = report?.phase_timestamps?.[key as SwingPhaseKey]
    if (ts) seekTo(ts.start)
  }

  const tapIssue = (timestamp: number | null | undefined) => {
    if (typeof timestamp === 'number') seekTo(timestamp)
  }

  const handleGoHome = () => Taro.reLaunch({ url: '/pages/index/index' })
  const handleShootAgain = () => Taro.reLaunch({ url: '/pages/analysis/capture' })

  const handleSyncTrainingPlan = async () => {
    if (!analysisId || analysisId === 'sample') return
    setSyncingPlan(true)
    try {
      await trainingService.addToPlanFromAnalysis(analysisId)
      Taro.showToast({ title: '已同步到本周训练计划', icon: 'success', duration: 2000 })
    } catch (e: unknown) {
      const fallback = describePageLoadFailure(e)
      const msg =
        isRequestError(e) && e.message?.trim()
          ? e.message.trim()
          : fallback
      const line = msg.length > 140 ? `${msg.slice(0, 139)}…` : msg
      Taro.showToast({ title: line, icon: 'none', duration: 2600 })
    } finally {
      setSyncingPlan(false)
    }
  }

  const handleCompareHistory = () => {
    if (!analysisId || analysisId === 'sample') {
      Taro.navigateTo({ url: '/pages/analysis/history' }).catch(toastTabNavigationFailure)
      return
    }
    Taro.navigateTo({
      url: `/pages/analysis/history?mode=compare&anchor=${encodeURIComponent(analysisId)}`,
    }).catch(toastTabNavigationFailure)
  }

  // ---------------- 分享（W7-T5）----------------
  // 小程序分享只能通过「右上角胶囊 · 转发给朋友」或 `<Button open-type='share'>` 触发
  // （`Taro.shareAppMessage` 自 2024 起已在各小程序平台禁用）。
  // 底部的「分享报告」按钮改造成 `openType='share'`，点击会直接唤起原生转发面板。
  useShareAppMessage(() => {
    const score = report?.overall_score ?? publicReport?.overall_score
    const clubLabel = report
      ? CLUB_TYPE_LABEL[report.club_type]
      : publicReport
      ? CLUB_TYPE_LABEL[publicReport.club_type as keyof typeof CLUB_TYPE_LABEL] ?? '挥杆'
      : '挥杆'
    const title = score
      ? `我的${clubLabel}挥杆打了 ${score} 分，你来挑战一下？`
      : `我用小鸟 AI 分析了挥杆，你来看看`
    return {
      title,
      path: `/pages/analysis/report?id=${analysisId}&from_share=1`,
      imageUrl:
        shareImageUrl ||
        report?.thumbnail_url ||
        publicReport?.thumbnail_url ||
        '',
    }
  })

  /**
   * 点底部「分享报告」按钮（这个 Button 本身已加 `openType='share'`，
   * 小程序会自动唤起转发面板；这里的 click handler 只做埋点）。
   * 注意不要阻塞 UI：埋点请求设 silent=true，失败也不影响分享。
   */
  const handleShareClick = () => {
    if (!analysisId || analysisId === 'sample') return
    shareService
      .logShare({ share_type: 'report', target_id: analysisId })
      .catch(() => undefined)
  }

  /** 公开报告下 CTA：引导非本人访问者去首页体验 */
  const handleCtaTryMine = () => {
    if (currentUserToken) {
      Taro.reLaunch({ url: '/pages/analysis/capture' })
    } else {
      Taro.reLaunch({ url: '/pages/login/index' })
    }
  }

  /**
   * "问 AI 教练"跳转。
   *
   * tabBar 页必须用 `switchTab`，不可用 `navigateTo`（微信会直接失败）。
   * 上下文经 `switchToCoach` 写入 storage，由 coach 页 `consumeCoachPendingContext` 一次性读取。
   *
   * - 真实报告：`analysisId` 注入会话；示例报告不带，避免 create-session 404
   * - `prefill`：明文写入 storage，无需 URL encode
   */
  const handleAskCoach = () => {
    const prefill = '这次我的挥杆，需要重点改什么？'
    const ctx =
      analysisId && analysisId !== 'sample'
        ? { analysisId, prefill }
        : { prefill }
    switchToCoach(ctx).catch(toastTabNavigationFailure)
  }

  /**
   * 删除入口（软删除，列表页同步消失）。
   * 仅从顶部「⋯ / 更多」操作表唤起，避免正文区再放红色删除按钮打断阅读。
   */
  const handleDeleteReport = () => {
    if (!analysisId || analysisId === 'sample') return
    Taro.showModal({
      title: '删除报告',
      content: '删除后无法在「我的报告」中查看此条记录，确认删除？',
      confirmText: '删除',
      confirmColor: '#ef4444',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await analysisService.deleteAnalysis(analysisId)
          Taro.showToast({ title: '已删除', icon: 'success' })
          setTimeout(() => {
            Taro.navigateBack().catch(() => {
              Taro.redirectTo({ url: '/pages/analysis/history' }).catch(() => undefined)
            })
          }, 400)
        } catch {
          /* toast 由 http */
        }
      },
    })
  }

  const openReportMoreMenu = () => {
    Taro.showActionSheet({
      itemList: ['删除此报告'],
      success: (res) => {
        if (res.tapIndex === 0) handleDeleteReport()
      },
    }).catch(() => undefined)
  }

  // ---------------- 渲染 ----------------
  if (loading) {
    return (
      <View className='report report--loading'>
        <Text>加载报告中…</Text>
      </View>
    )
  }

  // W7-T5：公开（脱敏）报告分支 —— 被分享者访问别人的报告走这里
  if (!report && publicReport) {
    const pr = publicReport
    const prLevel = pr.score_level ?? scoreLevelFromScore(pr.overall_score)
    const prMeta = prLevel ? SCORE_LEVEL_META[prLevel] : null
    const clubText = CLUB_TYPE_LABEL[pr.club_type as keyof typeof CLUB_TYPE_LABEL] ?? pr.club_type
    const angleText = CAMERA_ANGLE_LABEL[pr.camera_angle as keyof typeof CAMERA_ANGLE_LABEL] ?? pr.camera_angle
    return (
      <ScrollView scrollY className='report report--public'>
        <View className='report__public-hero'>
          <Text className='report__public-owner'>{pr.owner_nickname_masked} 的挥杆报告</Text>
          {pr.thumbnail_url && (
            <Image
              className='report__public-thumb'
              mode='aspectFill'
              src={pr.thumbnail_url}
            />
          )}
        </View>

        <View
          className='report__score-card'
          style={{
            background: prMeta?.cssVar || 'var(--color-primary)',
            color: prMeta?.textCssVar || 'var(--color-on-primary)'
          }}
        >
          <View className='report__score-left'>
            <Text className='report__score-emoji'>{prMeta?.emoji || '⛳️'}</Text>
            <Text className='report__score-level'>{prMeta?.label || '完成分析'}</Text>
            <Text className='report__score-caption'>{prMeta?.caption}</Text>
          </View>
          <View className='report__score-right'>
            <Text className='report__score-value'>{pr.overall_score ?? '-'}</Text>
            <Text className='report__score-unit'>分</Text>
          </View>
        </View>

        <View className='report__meta'>
          <Text className='report__meta-item'>📷 {angleText}</Text>
          <Text className='report__meta-item'>🏌️ {clubText}</Text>
        </View>

        <View className='report__section'>
          <View className='report__section-header'>
            <Text className='report__section-title'>关键问题</Text>
            <Text className='report__section-hint'>共 {pr.issues_total} 项</Text>
          </View>
          {pr.issues.length === 0 ? (
            <Text className='report__empty'>🎉 这一杆没有明显问题！</Text>
          ) : (
            pr.issues.map((iss, i) => (
              <View key={i} className='report__issue report__issue--public'>
                <View className='report__issue-head'>
                  <Text className='report__issue-name'>{iss.name}</Text>
                  <Text className={`report__severity report__severity--${iss.severity}`}>
                    {SEVERITY_LABEL[iss.severity] || iss.severity}
                  </Text>
                </View>
              </View>
            ))
          )}
        </View>

        <View className='report__public-cta'>
          <Text className='report__public-cta-title'>想知道你的挥杆问题？</Text>
          <Text className='report__public-cta-desc'>
            上传一段视频，AI 教练 30 秒给你专属报告
          </Text>
          <Button
            className='report__btn report__btn--primary'
            onClick={handleCtaTryMine}
          >
            立即体验
          </Button>
        </View>
      </ScrollView>
    )
  }

  if (error || !report) {
    return (
      <View className='report report--error'>
        <Text className='report__error-icon'>😣</Text>
        <Text className='report__error-msg'>{error || '报告不存在'}</Text>
        <Button className='report__btn report__btn--primary' onClick={handleGoHome}>
          返回首页
        </Button>
      </View>
    )
  }

  const isSample = analysisId === 'sample'

  return (
    <ScrollView scrollY className='report'>
      {isSample && (
        <View className='report__sample-banner'>
          <Text className='report__sample-banner-icon'>🎬</Text>
          <Text className='report__sample-banner-text'>
            这是演示报告，用真实数据展示 AI 能发现的问题；不消耗你的分析次数。
          </Text>
        </View>
      )}
      {!isSample && (
        <View className='report__toolbar'>
          <Text className='report__toolbar-more' onClick={openReportMoreMenu}>
            更多
          </Text>
        </View>
      )}
      {/* ==================== 1. 视频回放 ==================== */}
      <View className='report__video-wrap'>
        <View className='report__video-frame'>
          <Video
            id={VIDEO_ID}
            className='report__video'
            src={videoSrc}
            controls
            showFullscreenBtn
            showCenterPlayBtn
            poster={report.thumbnail_url || undefined}
            initialTime={0}
          />
        </View>

        {/* 阶段色条（在 video 下方；点击跳帧） */}
        {report.phase_timestamps && (
          <View className='report__phasebar'>
            {PHASE_ORDER.map((key) => {
              const ts: PhaseWindow | undefined = report.phase_timestamps?.[key]
              if (!ts) return null
              const total = PHASE_ORDER.reduce((acc, k) => {
                const tt = report.phase_timestamps?.[k]
                return tt ? acc + (tt.end - tt.start) : acc
              }, 0)
              const flex = total > 0 ? (ts.end - ts.start) / total : 1 / PHASE_ORDER.length
              return (
                <View
                  key={key}
                  className='report__phasebar-seg'
                  style={{
                    flexGrow: flex,
                    background: PHASE_COLOR[key],
                  }}
                  onClick={() => seekTo(ts.start)}
                >
                  <Text className='report__phasebar-label'>{PHASE_LABEL[key]}</Text>
                </View>
              )
            })}
          </View>
        )}

        {/* 倍速 */}
        <View className='report__rates'>
          <Text className='report__rates-label'>播放速度</Text>
          <View className='report__rates-group'>
            {PLAYBACK_RATES.map((r) => (
              <View
                key={r}
                className={[
                  'report__rate',
                  rate === r ? 'report__rate--active' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                onClick={() => setRate(r)}
              >
                <Text>{r}×</Text>
              </View>
            ))}
          </View>
        </View>
      </View>

      {/* ==================== 2. 综合评分 ==================== */}
      <View
        className='report__score-card'
        style={{
          background: levelMeta?.cssVar || 'var(--color-primary)',
          color: levelMeta?.textCssVar || 'var(--color-on-primary)',
        }}
      >
        <View className='report__score-left'>
          <Text className='report__score-emoji'>{levelMeta?.emoji || '⛳️'}</Text>
          <Text className='report__score-level'>{levelMeta?.label || '分析完成'}</Text>
          <Text className='report__score-caption'>{levelMeta?.caption}</Text>
        </View>
        <View className='report__score-right'>
          <Text className='report__score-value'>{report.overall_score ?? '-'}</Text>
          <Text className='report__score-unit'>分</Text>
          {typeof report.score_change === 'number' && report.score_change !== 0 && (
            <Text
              className={[
                'report__score-change',
                report.score_change > 0 ? 'report__score-change--up' : 'report__score-change--down',
              ].join(' ')}
            >
              {report.score_change > 0 ? '▲' : '▼'} {Math.abs(report.score_change)}
            </Text>
          )}
        </View>
      </View>

      {/* 视频元信息 */}
      <View className='report__meta'>
        <Text className='report__meta-item'>
          📷 {CAMERA_ANGLE_LABEL[report.camera_angle]}
        </Text>
        <Text className='report__meta-item'>
          🏌️ {CLUB_TYPE_LABEL[report.club_type]}
        </Text>
        {report.video_duration && (
          <Text className='report__meta-item'>
            ⏱ {report.video_duration.toFixed(1)}s
          </Text>
        )}
      </View>

      {/* ==================== 3. 六维雷达 ==================== */}
      {radarAxes.length > 0 && (
        <View className='report__section'>
          <View className='report__section-header'>
            <Text className='report__section-title'>六维评分</Text>
            <Text className='report__section-hint'>点击顶点查看阶段</Text>
          </View>
          <RadarChart axes={radarAxes} onTapAxis={tapPhase} />
          <View className='report__phase-list'>
            {PHASE_ORDER.map((key) => {
              const ps = report.phase_scores?.[key]
              if (!ps) return null
              return (
                <View
                  key={key}
                  className={[
                    'report__phase-item',
                    ps.is_weakest ? 'report__phase-item--weakest' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => tapPhase(key)}
                >
                  <Text className='report__phase-name'>{PHASE_FULL_LABEL[key]}</Text>
                  <Text className='report__phase-score'>{ps.score}</Text>
                  {ps.is_weakest && <Text className='report__phase-badge'>最需改进</Text>}
                </View>
              )
            })}
          </View>
        </View>
      )}

      {/* ==================== 4. 问题诊断 ==================== */}
      <View className='report__section'>
        <View className='report__section-header'>
          <Text className='report__section-title'>问题诊断</Text>
          <Text className='report__section-hint'>共 {sortedIssues.length} 项</Text>
        </View>
        {sortedIssues.length === 0 ? (
          <Text className='report__empty'>🎉 这一杆没有明显问题，继续保持！</Text>
        ) : (
          sortedIssues.map((iss) => (
            <View
              key={iss.type}
              className='report__issue'
              onClick={() => tapIssue(iss.key_frame_timestamp)}
            >
              <View className='report__issue-head'>
                <Text className='report__issue-name'>{iss.name}</Text>
                <Text className={`report__severity report__severity--${iss.severity}`}>
                  {SEVERITY_LABEL[iss.severity] || iss.severity}
                </Text>
              </View>
              {(iss.key_frame_url || report.thumbnail_url) && (
                <Image
                  className='report__issue-frame'
                  mode='aspectFill'
                  src={iss.key_frame_url || report.thumbnail_url || ''}
                />
              )}
              <Text className='report__issue-desc'>{iss.description}</Text>
              {typeof iss.key_frame_timestamp === 'number' && (
                <Text className='report__issue-ts'>
                  👆 点击跳转到 {iss.key_frame_timestamp.toFixed(1)}s 关键帧
                </Text>
              )}
            </View>
          ))
        )}
      </View>

      {/* ==================== 5. 训练建议 ==================== */}
      {report.recommendations.length > 0 && (
        <View className='report__section'>
          <View className='report__section-header'>
            <Text className='report__section-title'>训练建议</Text>
            <Text className='report__section-hint'>
              共 {report.recommendations.length} 个动作
            </Text>
          </View>
          {!isSample && (
            <View className='report__training-sync'>
              <Button
                className='report__btn report__btn--primary report__training-sync-btn'
                loading={syncingPlan}
                disabled={syncingPlan}
                onClick={() => void handleSyncTrainingPlan()}
              >
                一键加入本周训练计划
              </Button>
              <Text className='report__training-sync-hint'>
                将根据本次分析的问题自动追加当周任务（与服务器端幂等，不会重复条目）
              </Text>
            </View>
          )}
          {report.recommendations.map((rec) => {
            const drill = getDrillDetail(rec.drill_id)
            return (
              <View key={rec.drill_id} className='report__drill'>
                <View className='report__drill-head'>
                  <Text className='report__drill-name'>{drill.name}</Text>
                  <Text className='report__drill-difficulty'>{drill.difficulty}</Text>
                </View>
                <Text className='report__drill-desc'>{drill.description}</Text>
                <View className='report__drill-meta'>
                  <Text className='report__drill-meta-item'>⏱ {drill.duration_minutes} 分钟</Text>
                  <Text className='report__drill-meta-item'>
                    🔄 {drill.sets} 组{drill.reps ? ` × ${drill.reps}` : ''}
                  </Text>
                  {drill.equipment && drill.equipment.length > 0 && (
                    <Text className='report__drill-meta-item'>
                      🎒 {drill.equipment.join('、')}
                    </Text>
                  )}
                </View>
                <View className='report__drill-steps'>
                  {drill.steps.map((step, i) => (
                    <View key={i} className='report__drill-step'>
                      <Text className='report__drill-step-idx'>{i + 1}</Text>
                      <Text className='report__drill-step-text'>{step}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )
          })}
        </View>
      )}

      {/* ==================== 6. 底部动作栏 ==================== */}
      <View className='report__footer'>
        <Button
          className='report__footer-btn'
          openType='share'
          onClick={handleShareClick}
        >
          📤 分享报告
        </Button>
        <Button className='report__footer-btn' onClick={handleCompareHistory}>
          📊 对比历史
        </Button>
        <Button className='report__footer-btn' onClick={handleAskCoach}>
          💬 问 AI 教练
        </Button>
      </View>

      <View className='report__actions'>
        <Button className='report__btn report__btn--primary' onClick={handleShootAgain}>
          再拍一段
        </Button>
        <Button className='report__btn report__btn--ghost' onClick={handleGoHome}>
          返回首页
        </Button>
      </View>
    </ScrollView>
  )
}

export default ReportPage
