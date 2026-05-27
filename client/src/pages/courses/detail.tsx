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
import {
  coursesService,
  type CourseRead,
  type LessonRead,
} from '@/services/coursesService'
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
