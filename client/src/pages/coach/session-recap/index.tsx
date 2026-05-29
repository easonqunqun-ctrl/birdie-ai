/**
 * M8-07 · 教练教学报告：选学员 + LLM 汇总 + PDF 导出。
 */

import { FC, useCallback, useEffect, useMemo, useState } from 'react'
import { View, Text, Button, Textarea, Switch } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { PHASE2_COACH_ENABLED_FLAG } from '@/constants/flags'
import { coachRecapService, type CoachRecapListItem } from '@/services/coachRecapService'
import {
  coachStudentsService,
  type CoachDashboardStudentItem,
} from '@/services/coachStudentsService'
import { useUserStore } from '@/store/userStore'
import './index.scss'

function todayIsoDate(): string {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const CoachSessionRecapPage: FC = () => {
  const currentRole = useUserStore((s) => s.currentRole)
  const [loading, setLoading] = useState(true)
  const [students, setStudents] = useState<CoachDashboardStudentItem[]>([])
  const [selected, setSelected] = useState<Record<string, boolean>>({})
  const [analysisMap, setAnalysisMap] = useState<Record<string, string>>({})
  const [coachNotes, setCoachNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [recapId, setRecapId] = useState('')
  const [aiSummary, setAiSummary] = useState('')
  const [pdfUrl, setPdfUrl] = useState('')
  const [history, setHistory] = useState<CoachRecapListItem[]>([])

  const selectedStudentIds = useMemo(
    () => students.filter((s) => selected[s.student_user_id]).map((s) => s.student_user_id),
    [selected, students],
  )

  const selectedAnalysisIds = useMemo(
    () =>
      selectedStudentIds
        .map((sid) => analysisMap[sid])
        .filter((id): id is string => Boolean(id)),
    [analysisMap, selectedStudentIds],
  )

  const load = useCallback(async () => {
    if (!PHASE2_COACH_ENABLED_FLAG || currentRole !== 'coach') {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const [dashboardRes, historyRes] = await Promise.all([
        coachStudentsService.dashboardList().catch(() => ({ students: [], total: 0, cached_at: null })),
        coachRecapService.list().catch(() => ({ items: [], total: 0 })),
      ])
      setStudents(dashboardRes.students)
      setHistory(historyRes.items)
      const nextSelected: Record<string, boolean> = {}
      const nextAnalysis: Record<string, string> = {}
      for (const item of dashboardRes.students.slice(0, 4)) {
        nextSelected[item.student_user_id] = false
        try {
          const detail = await coachStudentsService.dashboardDetail(item.student_user_id)
          const latest = detail.recent_analyses[0]
          if (latest) nextAnalysis[item.student_user_id] = latest.id
        } catch {
          /* ignore per-student detail failure */
        }
      }
      setSelected(nextSelected)
      setAnalysisMap(nextAnalysis)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载失败',
        icon: 'none',
      })
    } finally {
      setLoading(false)
    }
  }, [currentRole])

  useEffect(() => {
    void load()
  }, [load])

  const toggleStudent = (studentUserId: string, checked: boolean) => {
    setSelected((prev) => ({ ...prev, [studentUserId]: checked }))
  }

  const handleGenerate = async () => {
    if (submitting) return
    if (selectedStudentIds.length === 0) {
      Taro.showToast({ title: '请至少选择 1 位学员', icon: 'none' })
      return
    }
    if (selectedAnalysisIds.length !== selectedStudentIds.length) {
      Taro.showToast({ title: '部分学员缺少可用分析报告', icon: 'none' })
      return
    }
    setSubmitting(true)
    try {
      const res = await coachRecapService.create({
        session_date: todayIsoDate(),
        student_ids: selectedStudentIds,
        analysis_ids: selectedAnalysisIds,
        coach_manual_notes: coachNotes.trim() || undefined,
      })
      setRecapId(res.recap_id)
      setAiSummary(res.ai_summary)
      setPdfUrl('')
      Taro.showToast({ title: '已生成汇总', icon: 'success' })
      const historyRes = await coachRecapService.list()
      setHistory(historyRes.items)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '生成失败',
        icon: 'none',
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleExportPdf = async () => {
    if (!recapId || submitting) return
    setSubmitting(true)
    try {
      const res = await coachRecapService.exportPdf(recapId)
      setPdfUrl(res.pdf_url)
      Taro.setClipboardData({ data: res.pdf_url })
      Taro.showToast({ title: 'PDF 链接已复制', icon: 'success' })
      const historyRes = await coachRecapService.list()
      setHistory(historyRes.items)
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '导出失败',
        icon: 'none',
      })
    } finally {
      setSubmitting(false)
    }
  }

  if (!PHASE2_COACH_ENABLED_FLAG) {
    return (
      <View className='coach-session-recap coach-session-recap--blocked'>
        <Text>教练功能尚未开放</Text>
      </View>
    )
  }

  if (currentRole !== 'coach') {
    return (
      <View className='coach-session-recap coach-session-recap--blocked'>
        <Text>请先在「我的」页切换教练模式</Text>
      </View>
    )
  }

  return (
    <View className='coach-session-recap'>
      <Text className='coach-session-recap__title'>教学报告</Text>
      <Text className='coach-session-recap__hint'>
        选择本节课学员，系统将基于最近分析报告生成汇总，并可导出带水印 PDF（链接 24 小时有效）。
      </Text>

      {loading ? (
        <View className='coach-session-recap coach-session-recap--blocked'>
          <Text>加载中…</Text>
        </View>
      ) : null}

      {!loading && (
        <>
          <View className='coach-session-recap__section'>
            <Text className='coach-session-recap__section-title'>选择学员</Text>
            {students.length === 0 ? (
              <Text className='coach-session-recap__hint'>暂无 active 学员</Text>
            ) : (
              students.map((item) => (
                <View
                  key={item.student_user_id}
                  className={`coach-session-recap__student${
                    selected[item.student_user_id] ? ' coach-session-recap__student--selected' : ''
                  }`}
                >
                  <View>
                    <Text className='coach-session-recap__student-name'>{item.display_name}</Text>
                    <Text className='coach-session-recap__student-meta'>
                      7 天分析 {item.analyses_7d}
                      {analysisMap[item.student_user_id] ? ' · 已匹配最近报告' : ' · 无可用报告'}
                    </Text>
                  </View>
                  <Switch
                    checked={Boolean(selected[item.student_user_id])}
                    onChange={(e) => toggleStudent(item.student_user_id, Boolean(e.detail.value))}
                  />
                </View>
              ))
            )}
          </View>

          <View className='coach-session-recap__section'>
            <Text className='coach-session-recap__label'>教练补充（可选）</Text>
            <Textarea
              className='coach-session-recap__textarea'
              value={coachNotes}
              maxlength={2000}
              onInput={(e) => setCoachNotes(e.detail.value)}
              placeholder='下节课重点、场地条件等'
            />
          </View>

          <View className='coach-session-recap__actions'>
            <Button
              className='coach-session-recap__btn'
              loading={submitting}
              onClick={() => void handleGenerate()}
            >
              生成 LLM 汇总
            </Button>
            {recapId ? (
              <Button
                className='coach-session-recap__btn coach-session-recap__btn--ghost'
                loading={submitting}
                onClick={() => void handleExportPdf()}
              >
                导出 PDF
              </Button>
            ) : null}
          </View>

          {aiSummary ? (
            <View className='coach-session-recap__section'>
              <Text className='coach-session-recap__section-title'>AI 汇总预览</Text>
              <Text className='coach-session-recap__summary'>{aiSummary}</Text>
              {pdfUrl ? (
                <Text className='coach-session-recap__link' onClick={() => Taro.setClipboardData({ data: pdfUrl })}>
                  复制 PDF 链接
                </Text>
              ) : null}
            </View>
          ) : null}

          {history.length > 0 ? (
            <View className='coach-session-recap__section'>
              <Text className='coach-session-recap__section-title'>历史报告</Text>
              {history.map((item) => (
                <View key={item.id} className='coach-session-recap__history-item'>
                  <Text className='coach-session-recap__history-title'>
                    {item.session_date} · {item.student_ids.length} 位学员
                  </Text>
                  <Text className='coach-session-recap__history-meta'>{item.status}</Text>
                  {item.pdf_url ? (
                    <Text
                      className='coach-session-recap__link'
                      onClick={() => Taro.setClipboardData({ data: item.pdf_url || '' })}
                    >
                      复制 PDF 链接
                    </Text>
                  ) : null}
                </View>
              ))}
            </View>
          ) : null}
        </>
      )}
    </View>
  )
}

export default CoachSessionRecapPage
