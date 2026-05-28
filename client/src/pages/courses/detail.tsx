/**
 * P2-M11-03 · 课程详情页：课程头部 + lessons 列表（accordion 展开 transcript）。
 *
 * URL 参数
 * --------
 * `?id=crs_xxx` 从列表页透传；非法 / 不存在 / 草稿 → 后端 404 → 这里展示错误并提供返回
 *
 * 灰度
 * ----
 * 与列表页同步：`PHASE2_COURSES_ENABLED_FLAG=false` 时退回，避免直跳链接进入
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, ScrollView } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { PHASE2_COURSES_ENABLED_FLAG } from '@/constants/flags'
import { analysisService } from '@/services/analysisService'
import {
  coursesService,
  type CourseRead,
  type LessonRead,
  type LessonAttemptResponse,
} from '@/services/coursesService'
import type { AnalysisListItem } from '@/types/analysis'
import {
  getAssessmentMaxAttempts,
  getAssessmentMinScore,
  isAssessmentLesson,
} from '@/utils/courseAssessment'
import './detail.scss'

const CourseDetailPage: FC = () => {
  const router = useRouter()
  const courseId = router.params.id

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [course, setCourse] = useState<CourseRead | null>(null)
  const [lessons, setLessons] = useState<LessonRead[]>([])
  // 同一时间最多展开一节，避免页面过长
  const [expandedLessonId, setExpandedLessonId] = useState<string | null>(null)
  const [submittingLessonId, setSubmittingLessonId] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!courseId) {
      setError('参数错误')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      // 并发：course detail + lessons；任意一个 404 走 catch
      const [c, l] = await Promise.all([
        coursesService.detail(courseId),
        coursesService.lessons(courseId),
      ])
      setCourse(c)
      setLessons(l.items)
      // 默认展开第一节，让用户立刻有内容可看
      if (l.items.length > 0) {
        setExpandedLessonId(l.items[0].id)
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : '加载失败'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [courseId])

  useDidShow(() => {
    if (!PHASE2_COURSES_ENABLED_FLAG) {
      Taro.showToast({ title: '该功能尚未开放', icon: 'none' })
      setTimeout(() => Taro.navigateBack({ delta: 1 }), 1200)
      return
    }
    void load()
  })

  if (!PHASE2_COURSES_ENABLED_FLAG) {
    return (
      <View className='course-detail course-detail--blocked'>
        <Text>功能维护中…</Text>
      </View>
    )
  }

  if (loading) {
    return (
      <View className='course-detail course-detail--empty'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error || !course) {
    return (
      <View className='course-detail course-detail--empty'>
        <Text className='course-detail__error'>{error ?? '课程不存在'}</Text>
        <View
          className='course-detail__back'
          onClick={() => Taro.navigateBack({ delta: 1 })}
        >
          <Text>返回</Text>
        </View>
      </View>
    )
  }

  const toggleLesson = (id: string) => {
    setExpandedLessonId((cur) => (cur === id ? null : id))
  }

  const formatAnalysisLabel = (item: AnalysisListItem): string => {
    const score =
      item.overall_score != null ? `${Math.round(item.overall_score)}分` : '—'
    const when = item.analyzed_at ?? item.created_at
    const date = when ? when.slice(0, 10) : '未知日期'
    return `${date} · ${score}`
  }

  const showAttemptResult = (result: LessonAttemptResponse) => {
    const title = result.passed ? '考核通过' : '未通过'
    let content = `${result.feedback}\n得分 ${result.score} / 及格 ${result.min_score}`
    content += `\n今日已考 ${result.attempts_used}/${result.max_attempts} 次`
    if (result.stage_upgraded && result.upgraded_to_stage != null) {
      content += `\n恭喜升阶至第 ${result.upgraded_to_stage} 阶！`
    }
    void Taro.showModal({ title, content, showCancel: false })
  }

  const handleSubmitAssessment = async (lesson: LessonRead) => {
    if (submittingLessonId) return
    setSubmittingLessonId(lesson.id)
    try {
      const res = await analysisService.listAnalyses({ page: 1, page_size: 20 })
      const completed = res.items.filter((i) => i.status === 'completed')
      if (completed.length === 0) {
        Taro.showToast({ title: '请先完成一次挥杆分析', icon: 'none' })
        return
      }
      const pickList = completed.slice(0, 6)
      const sheet = await Taro.showActionSheet({
        itemList: pickList.map(formatAnalysisLabel),
      })
      const picked = pickList[sheet.tapIndex]
      if (!picked) return
      const result = await coursesService.submitLessonAttempt(lesson.id, picked.id)
      showAttemptResult(result)
    } catch (e) {
      if (e && typeof e === 'object' && 'errMsg' in e) {
        const msg = String((e as { errMsg?: string }).errMsg ?? '')
        if (msg.includes('cancel')) return
      }
      const msg = e instanceof Error ? e.message : '提交失败'
      Taro.showToast({ title: msg, icon: 'none' })
    } finally {
      setSubmittingLessonId(null)
    }
  }

  return (
    <ScrollView scrollY className='course-detail'>
      <View className='course-detail__header'>
        <Text className='course-detail__stage'>第 {course.stage} 阶</Text>
        <Text className='course-detail__title'>{course.title}</Text>
        {course.subtitle && (
          <Text className='course-detail__subtitle'>{course.subtitle}</Text>
        )}
        {course.description && (
          <Text className='course-detail__desc'>{course.description}</Text>
        )}
        {course.learning_objectives.length > 0 && (
          <View className='course-detail__objectives'>
            <Text className='course-detail__objectives-title'>本课学习目标</Text>
            {course.learning_objectives.map((obj, i) => (
              <View key={i} className='course-detail__objectives-item'>
                <Text className='course-detail__objectives-bullet'>·</Text>
                <Text className='course-detail__objectives-text'>{obj}</Text>
              </View>
            ))}
          </View>
        )}
      </View>

      <View className='course-detail__lessons'>
        <Text className='course-detail__lessons-title'>
          课时 {lessons.length} / 总时长 {course.estimated_minutes} 分钟
        </Text>
        {lessons.length === 0 && (
          <View className='course-detail__lessons-empty'>
            <Text>本课尚无内容，敬请期待</Text>
          </View>
        )}
        {lessons.map((lesson) => {
          const expanded = expandedLessonId === lesson.id
          const isAssessment = isAssessmentLesson(lesson)
          const submitting = submittingLessonId === lesson.id
          return (
            <View key={lesson.id} className='course-detail__lesson-card'>
              <View
                className='course-detail__lesson-header'
                onClick={() => toggleLesson(lesson.id)}
              >
                <View className='course-detail__lesson-header-main'>
                  <Text className='course-detail__lesson-index'>
                    {lesson.sort_order}.
                  </Text>
                  <Text className='course-detail__lesson-title'>
                    {lesson.title}
                  </Text>
                  {isAssessment && (
                    <Text className='course-detail__lesson-badge'>考核</Text>
                  )}
                </View>
                <View className='course-detail__lesson-header-right'>
                  <Text className='course-detail__lesson-duration'>
                    {lesson.duration_minutes} 分钟
                  </Text>
                  <Text className='course-detail__lesson-arrow'>
                    {expanded ? '▴' : '▾'}
                  </Text>
                </View>
              </View>
              {expanded && (
                <View className='course-detail__lesson-body'>
                  {lesson.transcript ? (
                    <Text className='course-detail__lesson-transcript'>
                      {lesson.transcript}
                    </Text>
                  ) : (
                    <Text className='course-detail__lesson-transcript course-detail__lesson-transcript--muted'>
                      （暂无图文讲解）
                    </Text>
                  )}
                  {lesson.video_url && (
                    <View
                      className='course-detail__lesson-video-cta'
                      onClick={() =>
                        Taro.showToast({
                          title: '视频播放将在后续版本上线',
                          icon: 'none',
                        })
                      }
                    >
                      <Text>▶ 观看视频</Text>
                    </View>
                  )}
                  {isAssessment && (
                    <View className='course-detail__assessment'>
                      <Text className='course-detail__assessment-hint'>
                        及格线 {getAssessmentMinScore(lesson)} 分 · 每日最多{' '}
                        {getAssessmentMaxAttempts(lesson)} 次
                      </Text>
                      <View
                        className={[
                          'course-detail__assessment-cta',
                          submitting ? 'course-detail__assessment-cta--busy' : '',
                        ].join(' ')}
                        onClick={() => !submitting && void handleSubmitAssessment(lesson)}
                      >
                        <Text>{submitting ? '提交中…' : '选择分析报告并提交考核'}</Text>
                      </View>
                    </View>
                  )}
                </View>
              )}
            </View>
          )
        })}
      </View>
    </ScrollView>
  )
}

export default CourseDetailPage
