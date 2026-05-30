/**
 * M8-06 · 单学员看板详情。
 */

import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { PHASE2_COACH_ENABLED_FLAG } from '@/constants/flags'
import {
  coachStudentsService,
  type CoachDashboardDetailResponse,
} from '@/services/coachStudentsService'
import { useUserStore } from '@/store/userStore'
import './detail.scss'

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  if (sameDay) return `今天 ${hh}:${mm}`
  const yyyy = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mo}-${dd} ${hh}:${mm}`
}

const CoachStudentDetailPage: FC = () => {
  const router = useRouter()
  const studentUserId = (router.params.studentUserId || '').trim()
  const currentRole = useUserStore((s) => s.currentRole)
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<CoachDashboardDetailResponse | null>(null)

  const load = useCallback(async () => {
    if (!PHASE2_COACH_ENABLED_FLAG || currentRole !== 'coach' || !studentUserId) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const res = await coachStudentsService.dashboardDetail(studentUserId)
      setDetail(res)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载失败',
        icon: 'none',
      })
    } finally {
      setLoading(false)
    }
  }, [currentRole, studentUserId])

  useEffect(() => {
    void load()
  }, [load])

  useDidShow(() => {
    void load()
  })

  if (!PHASE2_COACH_ENABLED_FLAG) {
    return (
      <View className='coach-student-detail coach-student-detail--blocked'>
        <Text>教练功能尚未开放</Text>
      </View>
    )
  }

  if (currentRole !== 'coach') {
    return (
      <View className='coach-student-detail coach-student-detail--blocked'>
        <Text>请先在「我的」页切换教练模式</Text>
      </View>
    )
  }

  if (!studentUserId) {
    return (
      <View className='coach-student-detail coach-student-detail--blocked'>
        <Text>缺少学员 ID</Text>
      </View>
    )
  }

  if (loading && !detail) {
    return (
      <View className='coach-student-detail coach-student-detail--blocked'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (!detail) {
    return (
      <View className='coach-student-detail coach-student-detail--blocked'>
        <Text>暂无数据</Text>
      </View>
    )
  }

  const displayName = detail.display_name || studentUserId

  return (
    <View className='coach-student-detail'>
      <View className='coach-student-detail__head'>
        <View className='coach-student-detail__name-row'>
          <Text className='coach-student-detail__name'>{displayName}</Text>
          {detail.needs_response ? (
            <Text className='coach-student-detail__badge'>待回应</Text>
          ) : null}
        </View>

        <View className='coach-student-detail__metrics'>
          <View className='coach-student-detail__metric'>
            <Text className='coach-student-detail__metric-label'>近 7 天分析</Text>
            <Text className='coach-student-detail__metric-value'>{detail.analyses_7d}</Text>
          </View>
          <View className='coach-student-detail__metric'>
            <Text className='coach-student-detail__metric-label'>待完成作业</Text>
            <Text className='coach-student-detail__metric-value'>{detail.pending_tasks}</Text>
          </View>
          <View className='coach-student-detail__metric'>
            <Text className='coach-student-detail__metric-label'>最近分析</Text>
            <Text className='coach-student-detail__metric-value'>
              {formatWhen(detail.last_analysis_at)}
            </Text>
          </View>
        </View>

        <View className='coach-student-detail__actions'>
          <Button
            className='coach-student-detail__action-btn'
            onClick={() =>
              Taro.navigateTo({
                url: `/pages/coach/task-assign/index?studentUserId=${encodeURIComponent(studentUserId)}&studentName=${encodeURIComponent(displayName)}`,
              })
            }
          >
            布置作业
          </Button>
          {detail.recent_analyses[0] ? (
            <Button
              className='coach-student-detail__action-btn coach-student-detail__action-btn--ghost'
              onClick={() =>
                Taro.navigateTo({
                  url: `/pages/coach/analysis-annotate?analysisId=${encodeURIComponent(detail.recent_analyses[0].id)}`,
                })
              }
            >
              批注最近报告
            </Button>
          ) : null}
        </View>
      </View>

      <View className='coach-student-detail__section'>
        <Text className='coach-student-detail__section-title'>最近分析报告</Text>
        {detail.recent_analyses.length === 0 ? (
          <Text className='coach-student-detail__empty'>暂无分析报告</Text>
        ) : (
          detail.recent_analyses.map((item) => (
            <View key={item.id} className='coach-student-detail__row'>
              <View className='coach-student-detail__row-top'>
                <Text className='coach-student-detail__row-title'>
                  {item.club_type || '挥杆分析'}
                  {item.overall_score != null ? ` · ${item.overall_score} 分` : ''}
                </Text>
                <Text className='coach-student-detail__row-meta'>{formatWhen(item.created_at)}</Text>
              </View>
              <Text
                className='coach-student-detail__link'
                onClick={() =>
                  Taro.navigateTo({
                    url: `/pages/analysis/report?id=${encodeURIComponent(item.id)}`,
                  })
                }
              >
                查看报告 →
              </Text>
              <Text
                className='coach-student-detail__link coach-student-detail__link--secondary'
                onClick={() =>
                  Taro.navigateTo({
                    url: `/pages/coach/analysis-annotate?analysisId=${encodeURIComponent(item.id)}`,
                  })
                }
              >
                写批注
              </Text>
            </View>
          ))
        )}
      </View>

      <View className='coach-student-detail__section'>
        <Text className='coach-student-detail__section-title'>最近批注</Text>
        {detail.recent_annotations.length === 0 ? (
          <Text className='coach-student-detail__empty'>暂无批注记录</Text>
        ) : (
          detail.recent_annotations.map((item) => (
            <View key={item.id} className='coach-student-detail__row'>
              <View className='coach-student-detail__row-top'>
                <Text className='coach-student-detail__row-title'>
                  {item.annotation_type === 'video_ref' ? '参考镜头' : '文字批注'}
                </Text>
                <Text className='coach-student-detail__row-meta'>{formatWhen(item.created_at)}</Text>
              </View>
              {item.text_content ? (
                <Text className='coach-student-detail__row-sub'>{item.text_content}</Text>
              ) : null}
            </View>
          ))
        )}
      </View>

      <View className='coach-student-detail__section'>
        <Text className='coach-student-detail__section-title'>待完成作业</Text>
        {detail.pending_coach_tasks.length === 0 ? (
          <Text className='coach-student-detail__empty'>暂无待完成作业</Text>
        ) : (
          detail.pending_coach_tasks.map((item) => (
            <View key={item.id} className='coach-student-detail__row'>
              <View className='coach-student-detail__row-top'>
                <Text className='coach-student-detail__row-title'>
                  {item.drill_name || '训练动作'} × {item.target_count}
                </Text>
                <Text className='coach-student-detail__row-meta'>{formatWhen(item.created_at)}</Text>
              </View>
            </View>
          ))
        )}
      </View>
    </View>
  )
}

export default CoachStudentDetailPage
