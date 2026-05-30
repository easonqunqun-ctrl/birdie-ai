/**
 * M11-06 · 教练定制课程创建 / 编辑 / 发布。
 */

import { FC, useCallback, useEffect, useMemo, useState } from 'react'
import { View, Text, Input, Textarea, Button } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { PHASE2_COACH_ENABLED_FLAG, PHASE2_COURSES_ENABLED_FLAG } from '@/constants/flags'
import { coachCoursesService } from '@/services/coachCoursesService'
import type { CourseRead, LessonRead } from '@/services/coursesService'
import { useUserStore } from '@/store/userStore'
import './edit.scss'

const STAGES = [1, 2, 3, 4, 5, 6, 7] as const

function splitObjectives(raw: string): string[] {
  return raw
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 20)
}

function joinObjectives(items: string[]): string {
  return items.join('\n')
}

const CoachCourseEditPage: FC = () => {
  const router = useRouter()
  const courseId = router.params.id ? decodeURIComponent(router.params.id) : ''
  const isCreate = !courseId
  const currentRole = useUserStore((s) => s.currentRole)

  const [loading, setLoading] = useState(!isCreate)
  const [saving, setSaving] = useState(false)
  const [course, setCourse] = useState<CourseRead | null>(null)
  const [lessons, setLessons] = useState<LessonRead[]>([])

  const [title, setTitle] = useState('')
  const [subtitle, setSubtitle] = useState('')
  const [description, setDescription] = useState('')
  const [stage, setStage] = useState<number>(2)
  const [estimatedMinutes, setEstimatedMinutes] = useState('60')
  const [objectivesText, setObjectivesText] = useState('')

  const [lessonTitle, setLessonTitle] = useState('')
  const [lessonDuration, setLessonDuration] = useState('15')
  const [lessonTranscript, setLessonTranscript] = useState('')
  const [addingLesson, setAddingLesson] = useState(false)

  const loadDetail = useCallback(async () => {
    if (!courseId) return
    setLoading(true)
    try {
      const detail = await coachCoursesService.getDetail(courseId)
      setCourse(detail.course)
      setLessons(detail.lessons)
      setTitle(detail.course.title)
      setSubtitle(detail.course.subtitle ?? '')
      setDescription(detail.course.description ?? '')
      setStage(detail.course.stage)
      setEstimatedMinutes(String(detail.course.estimated_minutes))
      setObjectivesText(joinObjectives(detail.course.learning_objectives ?? []))
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载失败',
        icon: 'none',
      })
      setTimeout(() => Taro.navigateBack(), 800)
    } finally {
      setLoading(false)
    }
  }, [courseId])

  useEffect(() => {
    if (!isCreate) void loadDetail()
  }, [isCreate, loadDetail])

  const readOnly = useMemo(
    () => Boolean(course?.is_published),
    [course?.is_published],
  )

  const handleSave = async () => {
    const trimmedTitle = title.trim()
    if (!trimmedTitle) {
      Taro.showToast({ title: '请填写课程标题', icon: 'none' })
      return
    }
    const minutes = Number.parseInt(estimatedMinutes.trim(), 10)
    if (!Number.isFinite(minutes) || minutes < 1) {
      Taro.showToast({ title: '请填写有效时长', icon: 'none' })
      return
    }
    setSaving(true)
    try {
      Taro.showLoading({ title: '保存中' })
      const payload = {
        title: trimmedTitle,
        subtitle: subtitle.trim() || null,
        description: description.trim() || null,
        stage,
        estimated_minutes: minutes,
        learning_objectives: splitObjectives(objectivesText),
      }
      if (isCreate) {
        const created = await coachCoursesService.create(payload)
        Taro.hideLoading()
        Taro.redirectTo({
          url: `/pages/coach/courses/edit?id=${encodeURIComponent(created.id)}`,
        })
        return
      }
      if (readOnly) {
        Taro.hideLoading()
        Taro.showToast({ title: '请先下架再编辑', icon: 'none' })
        return
      }
      const updated = await coachCoursesService.update(courseId, payload)
      setCourse(updated)
      Taro.hideLoading()
      Taro.showToast({ title: '已保存', icon: 'success' })
    } catch (e) {
      Taro.hideLoading()
      Taro.showToast({
        title: e instanceof Error ? e.message : '保存失败',
        icon: 'none',
      })
    } finally {
      setSaving(false)
    }
  }

  const handleAddLesson = async () => {
    if (!courseId || readOnly) return
    const trimmed = lessonTitle.trim()
    if (!trimmed) {
      Taro.showToast({ title: '请填写课时标题', icon: 'none' })
      return
    }
    const duration = Number.parseInt(lessonDuration.trim(), 10)
    if (!Number.isFinite(duration) || duration < 1) {
      Taro.showToast({ title: '请填写有效课时时长', icon: 'none' })
      return
    }
    setAddingLesson(true)
    try {
      const sortOrder = lessons.length
      const lesson = await coachCoursesService.addLesson(courseId, {
        code: `lesson-${sortOrder + 1}`,
        title: trimmed,
        sort_order: sortOrder,
        duration_minutes: duration,
        transcript: lessonTranscript.trim() || null,
      })
      setLessons((prev) => [...prev, lesson])
      setLessonTitle('')
      setLessonTranscript('')
      setLessonDuration('15')
      Taro.showToast({ title: '课时已添加', icon: 'success' })
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '添加失败',
        icon: 'none',
      })
    } finally {
      setAddingLesson(false)
    }
  }

  const handlePublish = async () => {
    if (!courseId) return
    if (lessons.length === 0) {
      Taro.showToast({ title: '请至少添加 1 个课时', icon: 'none' })
      return
    }
    const ok = await Taro.showModal({
      title: '发布课程',
      content: '发布后学员可在学习路径中看到，确定发布？',
    })
    if (!ok.confirm) return
    setSaving(true)
    try {
      const updated = await coachCoursesService.publish(courseId)
      setCourse(updated)
      Taro.showToast({ title: '已发布', icon: 'success' })
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '发布失败',
        icon: 'none',
      })
    } finally {
      setSaving(false)
    }
  }

  const handleUnpublish = async () => {
    if (!courseId) return
    const ok = await Taro.showModal({
      title: '下架课程',
      content: '下架后学员将无法看到，可继续编辑后再发布。',
    })
    if (!ok.confirm) return
    setSaving(true)
    try {
      const updated = await coachCoursesService.unpublish(courseId)
      setCourse(updated)
      Taro.showToast({ title: '已下架', icon: 'success' })
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '下架失败',
        icon: 'none',
      })
    } finally {
      setSaving(false)
    }
  }

  if (!PHASE2_COACH_ENABLED_FLAG || !PHASE2_COURSES_ENABLED_FLAG) {
    return (
      <View className='coach-course-edit coach-course-edit--blocked'>
        <Text>课程功能尚未开放</Text>
      </View>
    )
  }

  if (currentRole !== 'coach') {
    return (
      <View className='coach-course-edit coach-course-edit--blocked'>
        <Text>请先在「我的」页切换教练模式</Text>
      </View>
    )
  }

  if (loading) {
    return (
      <View className='coach-course-edit coach-course-edit--blocked'>
        <Text>加载中…</Text>
      </View>
    )
  }

  return (
    <View className='coach-course-edit'>
      <View className='coach-course-edit__section'>
        <Text className='coach-course-edit__section-title'>基本信息</Text>
        {course && (
          <Text className='coach-course-edit__status'>
            {course.is_published ? '已发布 · 编辑需先下架' : '草稿 · 可编辑'}
          </Text>
        )}
        <Text className='coach-course-edit__label'>课程标题</Text>
        <Input
          className='coach-course-edit__input'
          value={title}
          disabled={readOnly}
          placeholder='例如：短杆控制专项'
          onInput={(e) => setTitle(e.detail.value)}
        />
        <Text className='coach-course-edit__label'>副标题（可选）</Text>
        <Input
          className='coach-course-edit__input'
          value={subtitle}
          disabled={readOnly}
          placeholder='一句话介绍'
          onInput={(e) => setSubtitle(e.detail.value)}
        />
        <Text className='coach-course-edit__label'>课程简介</Text>
        <Textarea
          className='coach-course-edit__textarea'
          value={description}
          disabled={readOnly}
          placeholder='学员将看到的内容说明'
          onInput={(e) => setDescription(e.detail.value)}
        />
        <Text className='coach-course-edit__label'>所属阶段</Text>
        <View className='coach-course-edit__stage-row'>
          {STAGES.map((s) => (
            <View
              key={s}
              className={`coach-course-edit__stage-chip ${
                stage === s ? 'coach-course-edit__stage-chip--active' : ''
              }`}
              onClick={() => !readOnly && setStage(s)}
            >
              <Text>{s} 阶</Text>
            </View>
          ))}
        </View>
        <Text className='coach-course-edit__label'>预计总时长（分钟）</Text>
        <Input
          className='coach-course-edit__input'
          type='number'
          value={estimatedMinutes}
          disabled={readOnly}
          onInput={(e) => setEstimatedMinutes(e.detail.value)}
        />
        <Text className='coach-course-edit__label'>学习目标（每行一条）</Text>
        <Textarea
          className='coach-course-edit__textarea'
          value={objectivesText}
          disabled={readOnly}
          placeholder={'掌握基本站位\n理解杆面控制'}
          onInput={(e) => setObjectivesText(e.detail.value)}
        />
      </View>

      {!isCreate && (
        <View className='coach-course-edit__section'>
          <Text className='coach-course-edit__section-title'>
            课时 ({lessons.length})
          </Text>
          {lessons.length === 0 && (
            <Text className='coach-course-edit__empty-lessons'>
              还没有课时，请在下方的表单添加
            </Text>
          )}
          {lessons.map((lesson) => (
            <View key={lesson.id} className='coach-course-edit__lesson'>
              <Text className='coach-course-edit__lesson-title'>
                {lesson.sort_order + 1}. {lesson.title}
              </Text>
              <Text className='coach-course-edit__lesson-meta'>
                {lesson.duration_minutes} 分钟
                {lesson.transcript ? ' · 含讲解' : ''}
              </Text>
            </View>
          ))}

          {!readOnly && (
            <>
              <Text className='coach-course-edit__label'>新课时标题</Text>
              <Input
                className='coach-course-edit__input'
                value={lessonTitle}
                placeholder='例如：握杆与站位'
                onInput={(e) => setLessonTitle(e.detail.value)}
              />
              <Text className='coach-course-edit__label'>时长（分钟）</Text>
              <Input
                className='coach-course-edit__input'
                type='number'
                value={lessonDuration}
                onInput={(e) => setLessonDuration(e.detail.value)}
              />
              <Text className='coach-course-edit__label'>讲解文案（可选）</Text>
              <Textarea
                className='coach-course-edit__textarea'
                value={lessonTranscript}
                placeholder='图文讲解，学员展开可见'
                onInput={(e) => setLessonTranscript(e.detail.value)}
              />
              <Button
                className='coach-course-edit__btn coach-course-edit__btn--secondary'
                loading={addingLesson}
                disabled={addingLesson}
                onClick={() => void handleAddLesson()}
              >
                添加课时
              </Button>
            </>
          )}
        </View>
      )}

      <View className='coach-course-edit__footer'>
        <Button
          className='coach-course-edit__btn coach-course-edit__btn--primary'
          loading={saving}
          disabled={saving}
          onClick={() => void handleSave()}
        >
          {isCreate ? '创建课程' : readOnly ? '已发布（下架后可改）' : '保存修改'}
        </Button>
        {!isCreate && course && !course.is_published && (
          <Button
            className='coach-course-edit__btn coach-course-edit__btn--secondary'
            disabled={saving}
            onClick={() => void handlePublish()}
          >
            发布课程
          </Button>
        )}
        {!isCreate && course?.is_published && (
          <Button
            className='coach-course-edit__btn coach-course-edit__btn--ghost'
            disabled={saving}
            onClick={() => void handleUnpublish()}
          >
            下架以便编辑
          </Button>
        )}
      </View>
    </View>
  )
}

export default CoachCourseEditPage
