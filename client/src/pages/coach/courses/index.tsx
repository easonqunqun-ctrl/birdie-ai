/**
 * M11-06 · 教练定制课程列表。
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { PHASE2_COACH_ENABLED_FLAG, PHASE2_COURSES_ENABLED_FLAG } from '@/constants/flags'
import { coachCoursesService } from '@/services/coachCoursesService'
import type { CourseRead } from '@/services/coursesService'
import { useUserStore } from '@/store/userStore'
import './index.scss'

const CoachCoursesIndexPage: FC = () => {
  const currentRole = useUserStore((s) => s.currentRole)
  const [loading, setLoading] = useState(true)
  const [items, setItems] = useState<CourseRead[]>([])

  const load = useCallback(async () => {
    if (
      !PHASE2_COACH_ENABLED_FLAG ||
      !PHASE2_COURSES_ENABLED_FLAG ||
      currentRole !== 'coach'
    ) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const data = await coachCoursesService.listMine()
      setItems(data)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载失败',
        icon: 'none',
      })
    } finally {
      setLoading(false)
    }
  }, [currentRole])

  useDidShow(() => {
    void load()
  })

  if (!PHASE2_COACH_ENABLED_FLAG || !PHASE2_COURSES_ENABLED_FLAG) {
    return (
      <View className='coach-courses coach-courses--blocked'>
        <Text>课程功能尚未开放</Text>
      </View>
    )
  }

  if (currentRole !== 'coach') {
    return (
      <View className='coach-courses coach-courses--blocked'>
        <Text>请先在「我的」页切换教练模式</Text>
      </View>
    )
  }

  return (
    <View className='coach-courses'>
      <View className='coach-courses__head'>
        <Text className='coach-courses__title'>定制课程</Text>
        <Button
          className='coach-courses__create-btn'
          onClick={() => Taro.navigateTo({ url: '/pages/coach/courses/edit' })}
        >
          新建
        </Button>
      </View>
      <Text className='coach-courses__hint'>
        创建并发布后将出现在学员「学习路径」中，并标注「教练定制」。
      </Text>

      {loading && <Text className='coach-courses__empty'>加载中…</Text>}
      {!loading && items.length === 0 && (
        <Text className='coach-courses__empty'>还没有课程，点右上角新建</Text>
      )}

      {!loading &&
        items.map((course) => (
          <View
            key={course.id}
            className='coach-courses__card'
            onClick={() =>
              Taro.navigateTo({
                url: `/pages/coach/courses/edit?id=${encodeURIComponent(course.id)}`,
              })
            }
          >
            <View className='coach-courses__card-top'>
              <View className='coach-courses__card-main'>
                <Text className='coach-courses__card-title'>{course.title}</Text>
                {course.subtitle && (
                  <Text className='coach-courses__card-sub'>{course.subtitle}</Text>
                )}
                <View className='coach-courses__card-meta'>
                  <Text className='coach-courses__badge'>第 {course.stage} 阶</Text>
                  <Text className='coach-courses__badge'>
                    约 {course.estimated_minutes} 分钟
                  </Text>
                  <Text
                    className={`coach-courses__badge ${
                      course.is_published
                        ? 'coach-courses__badge--published'
                        : 'coach-courses__badge--draft'
                    }`}
                  >
                    {course.is_published ? '已发布' : '草稿'}
                  </Text>
                </View>
              </View>
              <Text className='coach-courses__arrow'>›</Text>
            </View>
          </View>
        ))}
    </View>
  )
}

export default CoachCoursesIndexPage
