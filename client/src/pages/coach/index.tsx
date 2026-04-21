/**
 * AI 教练对话页（M3-T4 流式 / T5 报告跳转闭环）
 *
 * 流式接入（T4）：
 *   - `submitMessage` 走 SSE 流式；failure 气泡可"点击重试"
 *   - assistant 气泡 3 态：normal / streaming / errored
 *   - 渲染 `drill_card` 附件 → DrillCard 组件
 *   - "AI 正在思考..." 升级为三点跳动动画
 *   - 页面 unmount 时 `cancelActiveStream`
 *
 * 报告页闭环（T5）：
 *   - 识别 query `analysis_id` → `bootstrapSession(analysis_id)`，后端把该分析注入
 *     system prompt 的"最近分析"，AI 回复可以直接引用你这把的问题
 *   - 识别 query `prefill` → 首次打开 URL 时把预填问题塞进输入框（"这次我的挥杆..."）；
 *     用 `did-prefill` ref 保证只填一次（避免切 tab 回来被覆盖用户的改动）
 *   - context banner 加"查看原报告"链接，点击 `Taro.navigateBack` 或 navigateTo 回报告页
 */

import { FC, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button, Input, ScrollView, Text, View } from '@tarojs/components'
import type { BaseEventOrig } from '@tarojs/components'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import DrillCard from '@/components/DrillCard'
import { useUserStore } from '@/store/userStore'
import {
  getSubmitError,
  useChatStore,
  type SubmitMessageError,
} from '@/store/chatStore'
import type {
  DisplayChatMessage,
  DrillCardAttachment,
  QuickQuestionItem,
} from '@/types/chat'
import './index.scss'

const MAX_CONTENT_LEN = 500
const WELCOME_TEXT =
  '你好！我是你的 AI 高尔夫教练小鸟。随时问我挥杆技术、练习方法或高尔夫知识方面的问题。'

const CoachPage: FC = () => {
  const router = useRouter()
  const user = useUserStore((s) => s.user)
  const token = useUserStore((s) => s.token)

  const {
    currentSessionId,
    contextAnalysisId,
    messages,
    quickQuestions,
    quota,
    loading,
    sending,
    bootstrapError,
    bootstrapSession,
    submitMessage,
    clearSession,
    cancelActiveStream,
    hydrateQuotaFromUser,
  } = useChatStore()

  const [input, setInput] = useState('')
  const scrollAnchorRef = useRef<string>('chat-bottom-anchor')
  const [, forceRefresh] = useState(0)
  // prefill 只生效一次：如果用户从报告页带了 ?prefill=xxx，输入框填上；
  // 切到其它 tab 再回来时 useDidShow 会再触发，但这时不能覆盖用户已经改过的内容
  const didPrefillRef = useRef(false)

  /* ---------- bootstrap ---------- */
  const runBootstrap = useCallback(() => {
    const analysisId = router.params?.analysis_id || null
    bootstrapSession(analysisId).catch(() => {
      // 错误已写进 bootstrapError
    })
  }, [bootstrapSession, router.params?.analysis_id])

  useDidShow(() => {
    if (!token) {
      Taro.reLaunch({ url: '/pages/login/index' })
      return
    }
    hydrateQuotaFromUser(user?.quota)
    runBootstrap()

    // 处理预填问题；只做一次，之后 useDidShow 再触发也不覆盖用户输入
    if (!didPrefillRef.current) {
      const raw = router.params?.prefill
      if (raw) {
        try {
          const decoded = decodeURIComponent(raw)
          if (decoded) setInput(decoded)
        } catch {
          // URI 解码失败就当用户没带，不影响主流程
        }
      }
      didPrefillRef.current = true
    }
  })

  useEffect(() => {
    if (user?.quota) hydrateQuotaFromUser(user.quota)
  }, [user?.quota, hydrateQuotaFromUser])

  // 页面卸载时清理可能还活着的 SSE 连接，避免后台继续 onChunkReceived
  useEffect(() => {
    return () => {
      cancelActiveStream()
    }
  }, [cancelActiveStream])

  /* ---------- 滚动到底 ---------- */
  useEffect(() => {
    scrollAnchorRef.current = `chat-bottom-${Date.now()}`
    forceRefresh((n) => n + 1)
  }, [messages.length, sending])

  // 流式追加 delta 时，最后一条 assistant 的 content 长度也在变化；
  // 但不想对每个字符都滚一次（掉帧），只在每 ~40ms 检查一次最新长度
  const lastAssistantLen =
    messages.length > 0 ? messages[messages.length - 1].content.length : 0
  useEffect(() => {
    if (!sending) return
    const t = setTimeout(() => {
      scrollAnchorRef.current = `chat-bottom-${Date.now()}`
      forceRefresh((n) => n + 1)
    }, 40)
    return () => clearTimeout(t)
  }, [lastAssistantLen, sending])

  /* ---------- 发送逻辑 ---------- */
  const trimmed = input.trim()
  const canSend = Boolean(
    trimmed && !sending && currentSessionId && !isQuotaExhausted(quota),
  )

  const runSend = useCallback(
    async (content: string) => {
      try {
        await submitMessage(content)
      } catch (err) {
        // 流式失败时：user/assistant 气泡已保留（或标记 errored），这里只做 toast，
        // 不再往输入框回填（不然用户一看"又多了一条 errored 还多了一条草稿"，双重污染）
        const se = getSubmitError(err)
        toastSubmitError(se)
      }
    },
    [submitMessage],
  )

  const handleSend = useCallback(() => {
    if (!canSend) return
    const content = trimmed
    setInput('')
    void runSend(content)
  }, [canSend, runSend, trimmed])

  const handleInput = (e: BaseEventOrig<{ value: string }>) => {
    const value = (e.detail?.value ?? '').slice(0, MAX_CONTENT_LEN)
    setInput(value)
  }

  const handleTapQuickQuestion = useCallback(
    (q: QuickQuestionItem) => {
      if (sending) return
      if (q.requires_analysis && (user?.stats?.total_analyses ?? 0) === 0) {
        Taro.showModal({
          title: '需要先上传一次挥杆',
          content: '这个问题需要结合你的挥杆分析，先去"首页 → 开始分析"拍一次吧。',
          confirmText: '去分析',
          success: ({ confirm }) => {
            if (confirm) Taro.switchTab?.({ url: '/pages/index/index' })
          },
        })
        return
      }
      setInput(q.text)
    },
    [sending, user?.stats?.total_analyses],
  )

  /* ---------- 清空对话 ---------- */
  const handleClear = useCallback(() => {
    Taro.showModal({
      title: '清空对话？',
      content: sending
        ? '当前 AI 正在回复，点击清空会立即中断。'
        : '会删除本次会话的全部历史，AI 将以新会话身份开始。',
      confirmText: '清空',
      confirmColor: '#c14a4a',
      success: async ({ confirm }) => {
        if (!confirm) return
        await clearSession()
        runBootstrap()
      },
    })
  }, [sending, clearSession, runBootstrap])

  /* ---------- 复制 ---------- */
  const handleLongPress = useCallback((m: DisplayChatMessage) => {
    if (!m.content) return
    Taro.setClipboardData({
      data: m.content,
      success: () => Taro.showToast({ title: '已复制', icon: 'success' }),
    })
  }, [])

  /* ---------- 错误气泡重试 ---------- */
  const handleRetry = useCallback(
    (m: DisplayChatMessage) => {
      // 找到这条 errored assistant 的前一条 user，重发其 content
      const idx = messages.findIndex((x) => x.id === m.id)
      if (idx <= 0) return
      const prevUser = messages[idx - 1]
      if (prevUser.role !== 'user') return
      // 移除这两条占位，再重新发；保留其它历史
      useChatStore.setState((state) => ({
        messages: state.messages.slice(0, idx - 1),
      }))
      void runSend(prevUser.content)
    },
    [messages, runSend],
  )

  /* ---------- 渲染 loading / error ---------- */
  if (loading && messages.length === 0 && !bootstrapError) {
    return (
      <View className='coach coach--loading'>
        <Text className='coach__loading-text'>正在接入 AI 教练...</Text>
      </View>
    )
  }

  if (bootstrapError) {
    return (
      <View className='coach coach--error'>
        <Text className='coach__error-icon'>⚠️</Text>
        <Text className='coach__error-msg'>{bootstrapError}</Text>
        <Button className='coach__retry-btn' onClick={runBootstrap}>
          重新加载
        </Button>
      </View>
    )
  }

  const showEmptyState = messages.length === 0 && !sending
  const quotaExhausted = isQuotaExhausted(quota)
  const remainingText = renderQuotaText(quota)

  return (
    <View className='coach'>
      <View className='coach__header'>
        {contextAnalysisId ? (
          <View className='coach__context-banner'>
            <Text className='coach__context-banner-text'>
              基于报告 {shortId(contextAnalysisId)} 的对话
            </Text>
            <Text
              className='coach__context-banner-link'
              onClick={() => openOriginalReport(contextAnalysisId)}
            >
              查看原报告 ›
            </Text>
          </View>
        ) : (
          <View className='coach__context-banner coach__context-banner--ghost' />
        )}
        <Text className='coach__clear-btn' onClick={handleClear}>
          清空对话
        </Text>
      </View>

      <ScrollView
        className='coach__scroll'
        scrollY
        scrollWithAnimation
        scrollIntoView={scrollAnchorRef.current}
        enhanced
        showScrollbar={false}
      >
        <MessageBubble
          message={buildWelcomeMessage()}
          isWelcome
        />

        {showEmptyState && (
          <View className='coach__quick'>
            <Text className='coach__quick-title'>试试这些问题：</Text>
            {quickQuestions.map((q) => (
              <View
                key={q.id}
                className={`coach__quick-chip ${
                  q.requires_analysis ? 'coach__quick-chip--locked' : ''
                }`}
                onClick={() => handleTapQuickQuestion(q)}
              >
                <Text>{q.text}</Text>
                {q.requires_analysis && (
                  <Text className='coach__quick-chip-tag'>需分析</Text>
                )}
              </View>
            ))}
          </View>
        )}

        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            onLongPress={() => handleLongPress(m)}
            onRetry={m.errored && m.role === 'assistant' ? () => handleRetry(m) : undefined}
          />
        ))}

        {sending && messages[messages.length - 1]?.content === '' && (
          <View className='coach__typing'>
            <Text className='coach__typing-dot' />
            <Text className='coach__typing-dot' />
            <Text className='coach__typing-dot' />
          </View>
        )}

        <View id={scrollAnchorRef.current} className='coach__anchor' />
      </ScrollView>

      <View className='coach__footer'>
        {quotaExhausted ? (
          <View
            className='coach__upgrade'
            onClick={() =>
              Taro.showModal({
                title: '今日对话已用完',
                content: '升级会员即可享受不限次 AI 对话。',
                confirmText: '开通会员',
                success: ({ confirm }) => {
                  if (confirm) {
                    Taro.navigateTo({ url: '/pages/profile/membership' })
                  }
                },
              })
            }
          >
            <Text className='coach__upgrade-text'>
              今日对话已用完，点此了解会员特权
            </Text>
          </View>
        ) : (
          <View className='coach__input-row'>
            <Input
              className='coach__input'
              type='text'
              placeholder={sending ? 'AI 正在回复，稍等片刻...' : '问问 AI 教练...'}
              value={input}
              confirmType='send'
              maxlength={MAX_CONTENT_LEN}
              onInput={handleInput}
              onConfirm={handleSend}
              disabled={sending}
            />
            <Button
              className={`coach__send-btn ${
                canSend ? '' : 'coach__send-btn--disabled'
              }`}
              disabled={!canSend}
              loading={sending}
              onClick={handleSend}
            >
              发送
            </Button>
          </View>
        )}
        <View className='coach__meta'>
          <Text className='coach__quota'>{remainingText}</Text>
          <Text className='coach__len'>
            {input.length}/{MAX_CONTENT_LEN}
          </Text>
        </View>
      </View>
    </View>
  )
}

export default CoachPage

/* ==================== 子组件 ==================== */

interface BubbleProps {
  message: DisplayChatMessage
  isWelcome?: boolean
  onLongPress?: () => void
  onRetry?: () => void
}

const MessageBubble: FC<BubbleProps> = ({
  message,
  isWelcome,
  onLongPress,
  onRetry,
}) => {
  const isUser = message.role === 'user'
  const cls = useMemo(
    () =>
      [
        'coach__bubble',
        isUser ? 'coach__bubble--user' : 'coach__bubble--ai',
        isWelcome ? 'coach__bubble--welcome' : '',
        message.streaming ? 'coach__bubble--streaming' : '',
        message.errored ? 'coach__bubble--errored' : '',
      ]
        .filter(Boolean)
        .join(' '),
    [isUser, isWelcome, message.streaming, message.errored],
  )

  const drillAttachments = (message.attachments || []).filter(
    (a): a is DrillCardAttachment => a.type === 'drill_card',
  )
  const otherAttachments = (message.attachments || []).filter(
    (a) => a.type !== 'drill_card',
  )

  return (
    <View
      className={`coach__row ${
        isUser ? 'coach__row--right' : 'coach__row--left'
      }`}
      onLongPress={onLongPress}
    >
      {!isUser && <View className='coach__avatar'>🤖</View>}
      <View className='coach__bubble-col'>
        <View className={cls}>
          <Text>{message.content}</Text>
          {message.streaming && !message.errored && (
            <Text className='coach__cursor'>▎</Text>
          )}
        </View>
        {!isUser && drillAttachments.map((att, i) => (
          <DrillCard key={`${message.id}-drill-${i}`} attachment={att} />
        ))}
        {!isUser && otherAttachments.length > 0 && (
          <View className='coach__attachment-placeholder'>
            <Text>（暂不支持的附件类型，请升级 App）</Text>
          </View>
        )}
        {onRetry && (
          <View className='coach__retry-row' onClick={onRetry}>
            <Text>↻ 点击重试</Text>
          </View>
        )}
      </View>
    </View>
  )
}

/* ==================== 工具 ==================== */

function buildWelcomeMessage(): DisplayChatMessage {
  return {
    id: 'welcome-bubble',
    role: 'assistant',
    content: WELCOME_TEXT,
    attachments: [],
    created_at: '',
  }
}

function isQuotaExhausted(q: { remaining: number; total: number }) {
  if (q.total < 0 || q.remaining < 0) return false
  return q.remaining <= 0
}

function renderQuotaText(q: { remaining: number; total: number }): string {
  if (q.total < 0 || q.remaining < 0) return '会员无限次'
  if (q.remaining <= 0) return '今日已用完'
  return `今日剩余 ${q.remaining}/${q.total} 次`
}

function shortId(id: string): string {
  if (id.length <= 10) return id
  return `${id.slice(0, 7)}...${id.slice(-4)}`
}

/**
 * "查看原报告"：优先 navigateBack（大多数场景是 report → chat，返回能保住页面状态），
 * 如果没有上一页（比如用户是从首页"问 AI 教练"入口进入的，session 是老的、带着 context）
 * 则 navigateTo 一个新报告页实例。
 */
function openOriginalReport(analysisId: string) {
  const pages = Taro.getCurrentPages?.() ?? []
  if (pages.length > 1) {
    Taro.navigateBack({ delta: 1 })
    return
  }
  Taro.navigateTo({ url: `/pages/analysis/report?id=${analysisId}` })
}

function toastSubmitError(err: SubmitMessageError | null) {
  if (!err) {
    Taro.showToast({ title: '发送失败', icon: 'none' })
    return
  }
  switch (err.kind) {
    case 'quota_exhausted':
      Taro.showModal({
        title: '今日对话已用完',
        content: '升级会员即可享受不限次 AI 对话。',
        confirmText: '开通会员',
        success: ({ confirm }) => {
          if (confirm) {
            Taro.navigateTo({ url: '/pages/profile/membership' })
          }
        },
      })
      break
    case 'rate_limit':
      Taro.showToast({ title: '操作太快了，稍等片刻再试', icon: 'none' })
      break
    case 'service_error':
      Taro.showToast({
        title: 'AI 教练开小差了，点击气泡重试',
        icon: 'none',
      })
      break
    case 'network':
    default:
      Taro.showToast({
        title: err.message || '网络中断，点击气泡重试',
        icon: 'none',
      })
  }
}
