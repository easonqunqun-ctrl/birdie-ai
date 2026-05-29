/**
 * P2-M12-05 · 用户报告 vs 职业镜头并排对比（双视频 + 叠加雷达）。
 */

import { FC, useEffect, useMemo, useState } from 'react'
import { View, Text, Video, Image, Button, ScrollView } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import DualRadarChart from '@/components/DualRadarChart'
import '@/components/DualRadarChart.scss'
import { PHASE2_PROS_ENABLED_FLAG } from '@/constants/flags'
import { CAMERA_ANGLE_LABEL, CLUB_TYPE_LABEL } from '@/types/analysis'
import type { AnalysisReportResponse } from '@/types/analysis'
import { analysisService } from '@/services/analysisService'
import { describePageLoadFailure } from '@/services/request'
import { prosService, type ProMatchItemRead } from '@/services/prosService'
import {
  buildProPhaseCompareRows,
  buildProRadarAxes,
  buildUserRadarAxes,
  proScoresAreReferenceOnly,
} from '@/utils/proCompareRadar'
import { resolveReportPlaybackSrc } from '@/utils/reportPlayback'
import './pro-compare.scss'

const USER_VIDEO_ID = 'pro-compare-user-video'
const PRO_VIDEO_ID = 'pro-compare-pro-video'

const ProComparePage: FC = () => {
  const router = useRouter()
  const analysisId = (router.params.id || '').trim()
  const clipIdParam = (router.params.clipId || '').trim()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<AnalysisReportResponse | null>(null)
  const [matchItem, setMatchItem] = useState<ProMatchItemRead | null>(null)

  useEffect(() => {
    if (!PHASE2_PROS_ENABLED_FLAG) {
      setError('球手对比库尚未开放')
      setLoading(false)
      return
    }
    if (!analysisId || analysisId === 'sample') {
      setError('示例报告不支持职业对比')
      setLoading(false)
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const [loadedReport, matchResult] = await Promise.all([
          analysisService.getReport(analysisId),
          prosService.matchForAnalysis(analysisId, { limit: 5, record: false }),
        ])
        if (cancelled) return
        if (loadedReport.status !== 'completed') {
          setError('仅已完成分析可与职业镜头对比')
          setLoading(false)
          return
        }
        const picked =
          matchResult.matches.find((m) => m.clip.id === clipIdParam) ??
          matchResult.matches[0] ??
          null
        if (!picked) {
          setError('暂无匹配的职业镜头，请稍后再试')
          setLoading(false)
          return
        }
        setReport(loadedReport)
        setMatchItem(picked)
        setLoading(false)
      } catch (e: unknown) {
        if (!cancelled) {
          setError(describePageLoadFailure(e))
          setLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [analysisId, clipIdParam])

  const userVideoSrc = useMemo(
    () => (report ? resolveReportPlaybackSrc(report, 'original') : ''),
    [report],
  )
  const userAxes = useMemo(
    () => (report ? buildUserRadarAxes(report) : []),
    [report],
  )
  const proAxes = useMemo(
    () => (matchItem ? buildProRadarAxes(matchItem.clip, userAxes) : []),
    [matchItem, userAxes],
  )
  const phaseRows = useMemo(() => {
    if (!report || !matchItem) return []
    return buildProPhaseCompareRows(report, matchItem.clip)
  }, [report, matchItem])
  const proReferenceOnly = matchItem
    ? proScoresAreReferenceOnly(matchItem.clip)
    : false

  if (loading) {
    return (
      <View className='pro-compare'>
        <Text className='pro-compare__hint'>加载对比数据…</Text>
      </View>
    )
  }

  if (error || !matchItem || !report) {
    return (
      <View className='pro-compare'>
        <Text className='pro-compare__hint'>{error || '无法加载对比'}</Text>
        <Button onClick={() => Taro.navigateBack().catch(() => undefined)}>返回</Button>
      </View>
    )
  }

  const { player, clip, match_score: matchScore } = matchItem
  const club = CLUB_TYPE_LABEL[report.club_type] ?? report.club_type
  const angle = CAMERA_ANGLE_LABEL[report.camera_angle] ?? report.camera_angle

  return (
    <ScrollView scrollY className='pro-compare'>
      <View className='pro-compare__inner'>
        <View className='pro-compare__head'>
          <Text className='pro-compare__title'>和职业球手并排对比</Text>
          <Text className='pro-compare__subtitle'>
            匹配度 {matchScore} · {player.name}
          </Text>
          <Text className='pro-compare__meta'>
            {club} · {angle}
          </Text>
        </View>

        <View className='pro-compare__score-row'>
          <View className='pro-compare__score-col'>
            <Text className='pro-compare__score-tag'>你</Text>
            <Text className='pro-compare__score-value'>{report.overall_score ?? '—'}</Text>
          </View>
          <View className='pro-compare__score-col pro-compare__score-col--pro'>
            <Text className='pro-compare__score-tag'>职业</Text>
            <Text className='pro-compare__score-value'>{clip.overall_score ?? '—'}</Text>
          </View>
        </View>

        <View className='pro-compare__videos'>
          <View className='pro-compare__video-col'>
            <Text className='pro-compare__video-label'>你的挥杆</Text>
            <View className='pro-compare__video-frame'>
              {userVideoSrc ? (
                <Video
                  id={USER_VIDEO_ID}
                  className='pro-compare__video'
                  src={userVideoSrc}
                  controls
                  showCenterPlayBtn
                  objectFit='contain'
                />
              ) : (
                <Text className='pro-compare__video-empty'>暂无视频</Text>
              )}
            </View>
          </View>
          <View className='pro-compare__video-col'>
            <Text className='pro-compare__video-label'>{player.name}</Text>
            <View className='pro-compare__video-frame'>
              {clip.video_url ? (
                <Video
                  id={PRO_VIDEO_ID}
                  className='pro-compare__video'
                  src={clip.video_url}
                  poster={clip.thumbnail_url || undefined}
                  controls
                  showCenterPlayBtn
                  objectFit='contain'
                />
              ) : clip.thumbnail_url ? (
                <Image
                  className='pro-compare__video-poster'
                  src={clip.thumbnail_url}
                  mode='aspectFill'
                />
              ) : (
                <Text className='pro-compare__video-empty'>暂无视频</Text>
              )}
            </View>
          </View>
        </View>

        <Text className='pro-compare__credit'>来源：{clip.source_credit}</Text>

        {userAxes.length > 0 && proAxes.length > 0 && (
          <View className='pro-compare__section'>
            <Text className='pro-compare__section-title'>六维雷达叠加</Text>
            {proReferenceOnly && (
              <Text className='pro-compare__section-hint'>
                职业镜头暂无分阶段明细，虚线为综合分参考基线
              </Text>
            )}
            <DualRadarChart
              primaryAxes={userAxes}
              secondaryAxes={proAxes}
              primaryLabel='你'
              secondaryLabel={player.name}
            />
          </View>
        )}

        {phaseRows.length > 0 && (
          <View className='pro-compare__section'>
            <Text className='pro-compare__section-title'>六维分差</Text>
            <View className='pro-compare__phase-table'>
              <View className='pro-compare__phase-head'>
                <Text className='pro-compare__phase-cell pro-compare__phase-cell--label'>
                  阶段
                </Text>
                <Text className='pro-compare__phase-cell'>你</Text>
                <Text className='pro-compare__phase-cell'>职业</Text>
                <Text className='pro-compare__phase-cell'>差值</Text>
              </View>
              {phaseRows.map((row) => (
                <View key={row.key} className='pro-compare__phase-row'>
                  <Text className='pro-compare__phase-cell pro-compare__phase-cell--label'>
                    {row.label}
                  </Text>
                  <Text className='pro-compare__phase-cell'>{row.userScore ?? '—'}</Text>
                  <Text className='pro-compare__phase-cell'>{row.proScore ?? '—'}</Text>
                  <Text
                    className={[
                      'pro-compare__phase-cell',
                      row.delta != null && row.delta > 0
                        ? 'pro-compare__phase-cell--up'
                        : row.delta != null && row.delta < 0
                          ? 'pro-compare__phase-cell--down'
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

        <View className='pro-compare__actions'>
          <Button
            className='pro-compare__btn pro-compare__btn--primary'
            onClick={() =>
              Taro.navigateTo({
                url: `/pages/analysis/report?id=${encodeURIComponent(analysisId)}`,
              })
            }
          >
            返回完整报告
          </Button>
          <Button
            className='pro-compare__btn'
            onClick={() =>
              Taro.navigateTo({
                url: `/pages/pros/clip-insight?clipId=${encodeURIComponent(clip.id)}&playerId=${encodeURIComponent(player.id)}&analysisId=${encodeURIComponent(analysisId)}`,
              })
            }
          >
            查看 PGC 解说
          </Button>
          <Button
            className='pro-compare__btn'
            onClick={() =>
              Taro.navigateTo({
                url: `/pages/pros/detail?id=${encodeURIComponent(player.id)}`,
              })
            }
          >
            查看球手详情
          </Button>
        </View>
      </View>
    </ScrollView>
  )
}

export default ProComparePage
