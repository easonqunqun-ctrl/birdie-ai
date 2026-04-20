/**
 * 分析报告页（MVP §4.3 完整 UI）
 *
 * 6 个区域（对应 docs/12 T5 范围）：
 *   1. 视频回放（<Video> + 倍速切换 + 阶段色条跳帧）
 *   2. 综合评分（大字 + score_change + 分级徽章）
 *   3. 六维雷达图（手绘 Canvas 2d，点击顶点定位到阶段）
 *   4. 问题诊断（按 severity 排序 + 关键帧图 + 点击跳帧）
 *   5. 训练建议（drill 详情卡 + 加入训练计划占位）
 *   6. 底部动作栏（分享 / 对比 / AI 教练 全部占位 toast）
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
import Taro, { useRouter } from '@tarojs/taro'
import { analysisService } from '@/services/analysisService'
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

const ReportPage: FC = () => {
  const router = useRouter()
  const analysisId = (router.params as { id?: string }).id || ''
  const [report, setReport] = useState<AnalysisReportResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [rate, setRate] = useState<number>(1)

  // 拉一次报告
  useEffect(() => {
    if (!analysisId) {
      setError('缺少分析 ID')
      setLoading(false)
      return
    }
    analysisService
      .getReport(analysisId)
      .then((r) => {
        setReport(r)
        setLoading(false)
      })
      .catch((e: Error) => {
        setError(e.message || '加载报告失败')
        setLoading(false)
      })
  }, [analysisId])

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

  const toastSoon = (feature: string) => {
    Taro.showToast({ title: `${feature}即将上线`, icon: 'none', duration: 1500 })
  }

  const handleGoHome = () => Taro.reLaunch({ url: '/pages/index/index' })
  const handleShootAgain = () => Taro.reLaunch({ url: '/pages/analysis/capture' })

  /**
   * "问 AI 教练"跳转。
   *
   * - 真实报告（id 以 `ana_` 开头）：把 analysis_id 带到 coach 页，
   *   让后端在 `POST /chat/sessions` 时把该分析注入 system prompt 的"最近分析"
   * - 示例报告（id = 'sample'）：不带 analysis_id，走通用 system prompt
   *   —— 示例报告后端不落真实 analysis 数据，带过去会让 create-session 报 404
   * - 预填问题：方便用户点进去直接按"发送"，不强制（可删可改）
   */
  const handleAskCoach = () => {
    const prefill = encodeURIComponent('这次我的挥杆，需要重点改什么？')
    const params = [`prefill=${prefill}`]
    if (analysisId && analysisId !== 'sample') {
      params.push(`analysis_id=${analysisId}`)
    }
    Taro.navigateTo({ url: `/pages/coach/index?${params.join('&')}` })
  }

  // ---------------- 渲染 ----------------
  if (loading) {
    return (
      <View className='report report--loading'>
        <Text>加载报告中…</Text>
      </View>
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
      {/* ==================== 1. 视频回放 ==================== */}
      <View className='report__video-wrap'>
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
                <Button
                  className='report__btn report__btn--drill'
                  onClick={() => toastSoon('加入训练计划')}
                >
                  加入训练计划
                </Button>
              </View>
            )
          })}
        </View>
      )}

      {/* ==================== 6. 底部动作栏 ==================== */}
      <View className='report__footer'>
        <Button className='report__footer-btn' onClick={() => toastSoon('分享报告')}>
          📤 分享报告
        </Button>
        <Button className='report__footer-btn' onClick={() => toastSoon('对比历史')}>
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
