/**
 * P-01：并排对比两份历史报告（综合分、六维、问题摘要；完整报告从本页或列表进入）。
 */

import { FC, useEffect, useMemo, useState } from 'react'
import { View, Text, Button, ScrollView } from '@tarojs/components'
import Taro, { useRouter, useShareAppMessage } from '@tarojs/taro'
import { analysisService } from '@/services/analysisService'
import { describePageLoadFailure } from '@/services/request'
import { PHASE_LABEL, PHASE_ORDER } from '@/constants/phaseLabels'
import { SCORE_LEVEL_META, scoreLevelFromScore } from '@/constants/scoreLevel'
import { CAMERA_ANGLE_LABEL, CLUB_TYPE_LABEL } from '@/types/analysis'
import type { AnalysisReportResponse } from '@/types/analysis'
import { track } from '@/utils/track'
import './compare.scss'

function reportTimestamp(r: AnalysisReportResponse): number {
  const iso = r.analyzed_at || r.created_at
  const t = new Date(iso).getTime()
  return Number.isNaN(t) ? 0 : t
}

function formatWhen(iso: string | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${mi}`
}

function clubAngleLine(r: AnalysisReportResponse): string {
  const club = CLUB_TYPE_LABEL[r.club_type] ?? r.club_type
  const angle = CAMERA_ANGLE_LABEL[r.camera_angle] ?? r.camera_angle
  return `${club} · ${angle}`
}

function issueNameSet(r: AnalysisReportResponse): Set<string> {
  return new Set(r.issues.map((i) => i.name))
}

const ComparePage: FC = () => {
  const router = useRouter()
  const { left = '', right = '' } = router.params as { left?: string; right?: string }
  const idL = (left || '').trim()
  const idR = (right || '').trim()

  const [earlier, setEarlier] = useState<AnalysisReportResponse | null>(null)
  const [later, setLater] = useState<AnalysisReportResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!idL || !idR || idL === idR) {
      setError('请选择两篇不同的分析报告')
      setLoading(false)
      return
    }
    if (idL === 'sample' || idR === 'sample') {
      setError('示例报告不支持并排对比，请选择两次正式分析')
      setLoading(false)
      return
    }
    Promise.all([analysisService.getReport(idL), analysisService.getReport(idR)])
      .then(([ra, rb]) => {
        if (ra.status !== 'completed' || rb.status !== 'completed') {
          setError('仅支持对比已完成的分析报告')
          setLoading(false)
          return
        }
        const tA = reportTimestamp(ra)
        const tB = reportTimestamp(rb)
        if (tA <= tB) {
          setEarlier(ra)
          setLater(rb)
        } else {
          setEarlier(rb)
          setLater(ra)
        }
        setLoading(false)
      })
      .catch((e: unknown) => {
        setError(describePageLoadFailure(e))
        setLoading(false)
      })
  }, [idL, idR])

  const phaseRows = useMemo(() => {
    if (!earlier || !later) return []
    return PHASE_ORDER.map((key) => {
      const sE = earlier.phase_scores?.[key]?.score
      const sL = later.phase_scores?.[key]?.score
      const delta =
        typeof sE === 'number' && typeof sL === 'number' ? sL - sE : null
      return { key, label: PHASE_LABEL[key], earlier: sE, later: sL, delta }
    })
  }, [earlier, later])

  const issueDiff = useMemo(() => {
    if (!earlier || !later) {
      return { resolved: [] as string[], newly: [] as string[] }
    }
    const before = issueNameSet(earlier)
    const after = issueNameSet(later)
    const resolved = [...before].filter((n) => !after.has(n))
    const newly = [...after].filter((n) => !before.has(n))
    return { resolved, newly }
  }, [earlier, later])

  const scoreDelta = useMemo(() => {
    if (!earlier || !later) return 0
    return (later.overall_score ?? 0) - (earlier.overall_score ?? 0)
  }, [earlier, later])

  /** PP-10：晒进步一句话 */
  const progressShareLine = useMemo(() => {
    const resolvedN = issueDiff.resolved.length
    if (scoreDelta > 0 && resolvedN > 0) {
      return `综合分 +${scoreDelta}，已缓解 ${resolvedN} 项问题`
    }
    if (scoreDelta > 0) return `综合分进步 +${scoreDelta}，继续保持`
    if (resolvedN > 0) return `已缓解 ${resolvedN} 项问题，再拍一次巩固`
    return '两次挥杆对比 · 用数据看见进步'
  }, [scoreDelta, issueDiff.resolved.length])

  useShareAppMessage(() => {
    if (!later) {
      return { title: '领翼golf 挥杆对比', path: '/pages/index/index' }
    }
    track('share_report', {
      analysis_id: later.id,
      channel: 'compare_progress',
      score_delta: scoreDelta,
    })
    return {
      title: `我的挥杆进步：${progressShareLine}`,
      path: `/pages/analysis/report?id=${later.id}&from_share=1`,
      imageUrl: later.thumbnail_url || '',
    }
  })

  if (loading) {
    return (
      <View className='compare'>
        <View className='compare__loading'>
          <Text className='compare__loading-text'>加载对比数据…</Text>
        </View>
      </View>
    )
  }

  if (error || !earlier || !later) {
    return (
      <View className='compare'>
        <Text className='compare__hint'>{error || '无法加载报告'}</Text>
        <View className='compare__actions'>
          <Button onClick={() => Taro.navigateBack().catch(() => undefined)}>
            返回
          </Button>
        </View>
      </View>
    )
  }

  const deltaLabel =
    scoreDelta === 0
      ? '较晚一次与较早一次综合分相同。'
      : scoreDelta > 0
        ? `较晚一次比较早一次高 ${scoreDelta} 分。`
        : `较晚一次比较早一次低 ${Math.abs(scoreDelta)} 分。`
  const deltaTone =
    scoreDelta > 0 ? 'up' : scoreDelta < 0 ? 'down' : 'flat'
  const deltaBadge =
    scoreDelta === 0 ? '持平' : scoreDelta > 0 ? `+${scoreDelta}` : `${scoreDelta}`

  const levelE = scoreLevelFromScore(earlier.overall_score)
  const levelL = scoreLevelFromScore(later.overall_score)
  const metaE = levelE ? SCORE_LEVEL_META[levelE] : null
  const metaL = levelL ? SCORE_LEVEL_META[levelL] : null

  const topIssues = (r: AnalysisReportResponse, n: number) =>
    r.issues.slice(0, n).map((i) => i.name)

  return (
    <ScrollView scrollY className='compare'>
      <View className='compare__inner'>
      <View className='compare__head'>
        <Text className='compare__title'>历史报告对比</Text>
        <Text className='compare__hint'>按分析时间：左为较早 · 右为较晚</Text>
      </View>

      {/* PP-10：晒进步叙事卡 */}
      <View className='compare__progress-share'>
        <Text className='compare__progress-share-eyebrow'>晒进步</Text>
        <Text className='compare__progress-share-line'>{progressShareLine}</Text>
        <Text className='compare__progress-share-sub'>
          {clubAngleLine(later)} · 建议同机位再练再拍
        </Text>
        <View className='compare__progress-share-actions'>
          <Button className='compare__btn compare__btn--primary' openType='share'>
            分享进步给球友
          </Button>
          <Button
            className='compare__btn'
            onClick={() =>
              Taro.navigateTo({
                url: `/pages/analysis/poster?id=${encodeURIComponent(later.id)}`,
              }).catch(() => undefined)
            }
          >
            生成较晚报告海报
          </Button>
        </View>
      </View>

      <View className={`compare__summary compare__summary--${deltaTone}`}>
        <Text className='compare__summary-badge'>{deltaBadge}</Text>
        <View className='compare__summary-texts'>
          <Text className='compare__summary-title'>综合分变化</Text>
          <Text className='compare__summary-body'>{deltaLabel}</Text>
          {typeof later.score_change === 'number' && (
            <Text className='compare__summary-meta'>
              较晚报告标注：较上一次 {later.score_change >= 0 ? '+' : ''}
              {later.score_change} 分
            </Text>
          )}
        </View>
      </View>

      <View className='compare__row'>
        <View className='compare__col'>
          <Text className='compare__col-tag'>较早</Text>
          <Text className='compare__col-label'>{clubAngleLine(earlier)}</Text>
          <Text className='compare__score'>{earlier.overall_score ?? '—'}</Text>
          {metaE && (
            <Text className='compare__level' style={{ color: metaE.cssVar }}>
              {metaE.label}
            </Text>
          )}
          <Text className='compare__meta'>{formatWhen(earlier.analyzed_at || earlier.created_at)}</Text>
        </View>
        <View className='compare__col'>
          <Text className='compare__col-tag'>较晚</Text>
          <Text className='compare__col-label'>{clubAngleLine(later)}</Text>
          <Text className='compare__score'>{later.overall_score ?? '—'}</Text>
          {metaL && (
            <Text className='compare__level' style={{ color: metaL.cssVar }}>
              {metaL.label}
            </Text>
          )}
          <Text className='compare__meta'>{formatWhen(later.analyzed_at || later.created_at)}</Text>
        </View>
      </View>

      {(issueDiff.resolved.length > 0 || issueDiff.newly.length > 0) && (
        <View className='compare__section'>
          <Text className='compare__section-title'>问题变化</Text>
          {issueDiff.resolved.length > 0 && (
            <View className='compare__diff-block compare__diff-block--resolved'>
              <Text className='compare__diff-tag'>已缓解 · {issueDiff.resolved.length} 项</Text>
              {issueDiff.resolved.map((name) => (
                <Text key={name} className='compare__diff-item'>
                  · {name}
                </Text>
              ))}
            </View>
          )}
          {issueDiff.newly.length > 0 && (
            <View className='compare__diff-block compare__diff-block--new'>
              <Text className='compare__diff-tag'>新出现 · {issueDiff.newly.length} 项</Text>
              {issueDiff.newly.map((name) => (
                <Text key={name} className='compare__diff-item'>
                  · {name}
                </Text>
              ))}
            </View>
          )}
        </View>
      )}

      {phaseRows.length > 0 && (
        <View className='compare__section'>
          <Text className='compare__section-title'>六维对比</Text>
          <View className='compare__phase-table'>
            <View className='compare__phase-head'>
              <Text className='compare__phase-cell compare__phase-cell--label'>阶段</Text>
              <Text className='compare__phase-cell'>较早</Text>
              <Text className='compare__phase-cell'>较晚</Text>
              <Text className='compare__phase-cell'>变化</Text>
            </View>
            {phaseRows.map((row) => (
              <View key={row.key} className='compare__phase-row'>
                <Text className='compare__phase-cell compare__phase-cell--label'>
                  {row.label}
                </Text>
                <Text className='compare__phase-cell'>{row.earlier ?? '—'}</Text>
                <Text className='compare__phase-cell'>{row.later ?? '—'}</Text>
                <Text
                  className={[
                    'compare__phase-cell',
                    row.delta != null && row.delta > 0
                      ? 'compare__phase-cell--up'
                      : row.delta != null && row.delta < 0
                        ? 'compare__phase-cell--down'
                        : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  {row.delta == null
                    ? '—'
                    : row.delta === 0
                      ? '0'
                      : `${row.delta > 0 ? '+' : ''}${row.delta}`}
                </Text>
              </View>
            ))}
          </View>
        </View>
      )}

      <View className='compare__section'>
        <Text className='compare__section-title'>问题摘要</Text>
        <View className='compare__issues-row'>
          <View className='compare__issues-col'>
            <Text className='compare__issues-tag'>较早 · {earlier.issues.length} 项</Text>
            {earlier.issues.length === 0 ? (
              <Text className='compare__issues-empty'>无明显问题</Text>
            ) : (
              topIssues(earlier, 3).map((name) => (
                <Text key={name} className='compare__issues-item'>
                  · {name}
                </Text>
              ))
            )}
          </View>
          <View className='compare__issues-col'>
            <Text className='compare__issues-tag'>较晚 · {later.issues.length} 项</Text>
            {later.issues.length === 0 ? (
              <Text className='compare__issues-empty'>无明显问题</Text>
            ) : (
              topIssues(later, 3).map((name) => (
                <Text key={name} className='compare__issues-item'>
                  · {name}
                </Text>
              ))
            )}
          </View>
        </View>
      </View>

      <View className='compare__actions'>
        <Button
          className='compare__btn compare__btn--primary'
          onClick={() =>
            Taro.navigateTo({
              url: `/pages/analysis/report?id=${encodeURIComponent(earlier.id)}`,
            })
          }
        >
          打开较早完整报告
        </Button>
        <Button
          className='compare__btn compare__btn--primary'
          onClick={() =>
            Taro.navigateTo({
              url: `/pages/analysis/report?id=${encodeURIComponent(later.id)}`,
            })
          }
        >
          打开较晚完整报告
        </Button>
        <Button
          className='compare__btn'
          onClick={() => Taro.navigateBack().catch(() => undefined)}
        >
          返回
        </Button>
      </View>
      </View>
    </ScrollView>
  )
}

export default ComparePage
