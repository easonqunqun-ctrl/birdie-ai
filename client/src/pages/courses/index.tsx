/**
 * P2-M11-03 · 学习路径列表页：按 stage 分组展示已发布课程，点击进详情。
 *
 * 灰度
 * ----
 * - `PHASE2_COURSES_ENABLED_FLAG=false` 时本页 onShow 立即 redirectBack
 *   并 Toast 提示，避免被直跳链接进入空白页
 * - 后端 GET /v1/courses 在 flag 关时返 404；客户端守门是兜底
 *
 * 数据契约（与 M11-02）
 * ---------------------
 * - 列表只含 `is_published=true` 课程；草稿对小程序不可见
 * - 按 `stage` 升序，再按 `sort_order` 升序
 * - `is_member_only=true` 课程显示 🔒 角标，但不阻断点击（详情页再处理付费）
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, ScrollView } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { PHASE2_COURSES_ENABLED_FLAG } from '@/constants/flags'
import { coursesService, type CourseRead } from '@/services/coursesService'
import './index.scss'

const STAGE_TITLES: Record<number, string> = {
  1: '第 1 阶 · 入门',
  2: '第 2 阶 · 基础',
  3: '第 3 阶 · 进阶',
  4: '第 4 阶 · 整合',
  5: '第 5 阶 · 精修',
  6: '第 6 阶 · 高阶',
  7: '第 7 阶 · 大师',
}

const CoursesIndexPage: FC = () => {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [courses, setCourses] = useState<CourseRead[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await coursesService.list()
      setCourses(data)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '加载失败'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useDidShow(() => {
    if (!PHASE2_COURSES_ENABLED_FLAG) {
      Taro.showToast({ title: '该功能尚未开放', icon: 'none' })
      // 等 Toast 显示后退回，避免空白页
      setTimeout(() => Taro.navigateBack({ delta: 1 }), 1200)
      return
    }
    void load()
  })

  // 关 flag 时 onShow 已经处理 redirect；这里渲染占位避免白屏
  if (!PHASE2_COURSES_ENABLED_FLAG) {
    return (
      <View className='courses-list courses-list--blocked'>
        <Text>功能维护中…</Text>
      </View>
    )
  }

  if (loading) {
    return (
      <View className='courses-list courses-list--empty'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error) {
    return (
      <View className='courses-list courses-list--empty'>
        <Text className='courses-list__error'>{error}</Text>
        <View className='courses-list__retry' onClick={() => void load()}>
          <Text>重试</Text>
        </View>
      </View>
    )
  }

  if (courses.length === 0) {
    return (
      <View className='courses-list courses-list--empty'>
        <Text>暂无课程，敬请期待</Text>
      </View>
    )
  }

  // 按 stage 分组（service 已按 stage+sort_order 排序，这里只需 chunk）
  const groups = new Map<number, CourseRead[]>()
  for (const c of courses) {
    const arr = groups.get(c.stage) ?? []
    arr.push(c)
    groups.set(c.stage, arr)
  }
  const stages = Array.from(groups.keys()).sort((a, b) => a - b)

  const onTap = (course: CourseRead) => {
    Taro.navigateTo({
      url: `/pages/courses/detail?id=${encodeURIComponent(course.id)}`,
    })
  }

  return (
    <ScrollView scrollY className='courses-list'>
      {stages.map((stage) => (
        <View key={stage} className='courses-list__stage'>
          <View className='courses-list__stage-header'>
            <Text className='courses-list__stage-title'>
              {STAGE_TITLES[stage] ?? `第 ${stage} 阶`}
            </Text>
            <Text className='courses-list__stage-count'>
              {groups.get(stage)?.length ?? 0} 门
            </Text>
          </View>
          {(groups.get(stage) ?? []).map((course) => (
            <View
              key={course.id}
              className='courses-list__card'
              onClick={() => onTap(course)}
            >
              <View className='courses-list__card-main'>
                <Text className='courses-list__card-title'>{course.title}</Text>
                {course.subtitle && (
                  <Text className='courses-list__card-subtitle'>
                    {course.subtitle}
                  </Text>
                )}
                <View className='courses-list__card-meta'>
                  <Text className='courses-list__card-meta-item'>
                    约 {course.estimated_minutes} 分钟
                  </Text>
                  {course.is_member_only && (
                    <Text className='courses-list__card-badge'>会员</Text>
                  )}
                </View>
              </View>
              <Text className='courses-list__card-arrow'>›</Text>
            </View>
          ))}
        </View>
      ))}
    </ScrollView>
  )
}

export default CoursesIndexPage
