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
import { Button, Image, Input, ScrollView, Text, View } from '@tarojs/components'
import type { BaseEventOrig } from '@tarojs/components'
import Taro, { useDidShow, useRouter, useShareAppMessage, useShareTimeline } from '@tarojs/taro'
import DrillCard from '@/components/DrillCard'
import AnalysisCard from '@/components/AnalysisCard'
import VideoCard from '@/components/VideoCard'
import EnvBadge from '@/components/EnvBadge'
import { APP_SHARE_MESSAGE, APP_SHARE_TIMELINE, BRAND_LOGO } from '@/constants/brandAssets'
import {
  consumeCoachPendingContext,
  switchToHome,
  toastTabNavigationFailure,
  type CoachPendingContext,
} from '@/utils/tabNav'
import { PAYMENT_ENABLED_FLAG } from '@/constants/flags'
import { useMembershipExpiringSoonModalOnShow } from '@/hooks/useMembershipExpiringSoonModalOnShow'
import { useUserStore } from '@/store/userStore'
import {
  chatErrorCause,
  getSubmitError,
  useChatStore,
  type SubmitMessageError,
} from '@/store/chatStore'
import type {
  DisplayChatMessage,
  DrillCardAttachment,
  AnalysisCardAttachment,
  VideoCardAttachment,
  MessageAttachment,
  QuickQuestionItem,
} from '@/types/chat'
import { describeIntermittentRequestFailure } from '@/services/request'
import './index.scss'

const MAX_CONTENT_LEN = 500
const WELCOME_TEXT =
  '你好！我是领翼golf 的 AI 高尔夫教练。随时问我挥杆技术、练习方法或高尔夫知识方面的问题。'

/** 访客预览：静态示例对话（微信审核须可先浏览页面详情） */
const GUEST_DEMO_MESSAGES: DisplayChatMessage[] = [
  {
    id: 'guest-demo-user',
    role: 'user',
    content: '开球老是右曲，应该怎么练？',
    attachments: [],
    created_at: '',
  },
  {
    id: 'guest-demo-assistant',
    role: 'assistant',
    content:
      '右曲常与挥杆路径偏外、杆面相对路径偏开有关。可以先做「墙面路径练习」：慢速半挥，让杆头贴近墙面内侧通过，感受由内向外的释放顺序。登录并完成挥杆分析后，我会结合你的实际数据给出更具体的训练建议。',
    attachments: [],
    created_at: '',
  },
]

const GUEST_FALLBACK_QUICK_QUESTIONS: QuickQuestionItem[] = [
  { id: 'guest-q1', text: '7 铁击球总是打薄，怎么改？', requires_analysis: false },
  { id: 'guest-q2', text: '推杆时手腕容易松，有什么练习？', requires_analysis: false },
  { id: 'guest-q3', text: '结合我的报告，这次最该先练什么？', requires_analysis: true },
]

function promptGuestLogin(content?: string) {
  Taro.showModal({
    title: '登录后开始对话',
    content:
      content ??
      '登录后 AI 教练将根据你的问题与挥杆分析生成个性化回复。',
    confirmText: '去登录',
    cancelText: '继续浏览',
    success: ({ confirm }) => {
      if (confirm) {
        Taro.navigateTo({ url: '/pages/login/index' })
      }
    },
  })
}

const CoachPage: FC = () => {
  const router = useRouter()
  const user = useUserStore((s) => s.user)
  const token = useUserStore((s) => s.token)
  const initialized = useUserStore((s) => s.initialized)
  const bootstrapUser = useUserStore((s) => s.bootstrap)

  useShareAppMessage(() => ({ ...APP_SHARE_MESSAGE }))
  useShareTimeline(() => ({ ...APP_SHARE_TIMELINE }))

  useMembershipExpiringSoonModalOnShow(!!token)

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
    bootstrapExistingSession,
    loadGuestPreview,
    submitMessage,
    clearSession,
    cancelActiveStream,
    hydrateQuotaFromUser,
  } = useChatStore()

  const [input, setInput] = useState('')
  const scrollAnchorRef = useRef<string>('chat-bottom-anchor')
  const [, forceRefresh] = useState(0)
  // P2-C1：粘贴超长文本时只提示一次，避免连续打字反复弹 toast
  const truncatedToastShownRef = useRef(false)
  // prefill 只生效一次：如果用户从报告页带了 pending context，输入框填上；
  // 切到其它 tab 再回来时 useDidShow 会再触发，但这时不能覆盖用户已经改过的内容
  const didPrefillRef = useRef(false)
  // P0-3：上一次成功 bootstrap 的"上下文 key"（指纹），避免每次 useDidShow 都重复
  // 拉远端建会话。
  // 取值范围：
  //   - `'session:<id>'`：来自对话历史进入
  //   - `'analysis:<id>'`：从某份分析报告问 AI
  //   - `'fresh'`：通用入口（无 analysis 上下文）
  //   - `null`：还没 bootstrap 过
  // 仅当本次计算出的 key !== 上次 key 时才重新 bootstrap，
  // 否则用户每次切回 coach tab 都会创建新会话 / 重复加载历史，引发幽灵会话。
  const bootstrappedKeyRef = useRef<string | null>(null)

  useEffect(() => {
    if (!initialized) {
      void bootstrapUser()
    }
  }, [initialized, bootstrapUser])

  /** 登出或 token 清空：重置对话 store 与 bootstrap 指纹；否则重新登录后因 ref 仍为 fresh 跳过 bootstrap，沿用上一账号残留 session */
  useEffect(() => {
    if (!token) {
      bootstrappedKeyRef.current = null
      didPrefillRef.current = false
      useChatStore.getState().reset()
    }
  }, [token])

  /* ---------- bootstrap ---------- */
  const runBootstrap = useCallback(
    (overrideAnalysisId?: string) => {
      const analysisId = overrideAnalysisId || router.params?.analysis_id || null
      return bootstrapSession(analysisId).catch((err) => {
        bootstrappedKeyRef.current = null
        throw err
      })
    },
    [bootstrapSession, router.params?.analysis_id],
  )

  const runBootstrapExisting = useCallback(
    (sessionId: string, ctxAnalysisId?: string | null) => {
      return bootstrapExistingSession(sessionId, ctxAnalysisId).catch((err) => {
        bootstrappedKeyRef.current = null
        throw err
      })
    },
    [bootstrapExistingSession],
  )

  useDidShow(() => {
    if (!token) {
      if (bootstrappedKeyRef.current !== 'guest-preview') {
        bootstrappedKeyRef.current = 'guest-preview'
        void loadGuestPreview()
      }
      return
    }
    hydrateQuotaFromUser(user?.quota)

    // 一次性消费从其它页 switchTab 带过来的 pending context（无 pending 时返回 null）
    const pending: Partial<CoachPendingContext> | null = consumeCoachPendingContext()

    // 计算本次 show 应该用的"会话指纹"：
    //   - 优先级 sessionId > pending.analysisId > router.params.analysis_id > 默认 fresh
    let nextKey: string
    if (pending?.sessionId) {
      nextKey = `session:${pending.sessionId}`
    } else if (pending?.analysisId) {
      nextKey = `analysis:${pending.analysisId}`
    } else if (router.params?.analysis_id) {
      nextKey = `analysis:${router.params.analysis_id}`
    } else {
      nextKey = 'fresh'
    }

    // P0-3 关键：相同 key 不重复 bootstrap，否则切 tab 回来会幽灵创建新会话。
    // pending 已经被 consume 了一次（"取走即清"语义），所以下一次 show 走的就是
    // router.params 兜底或 fresh，与"上次 bootstrap key"对比即可。
    if (nextKey !== bootstrappedKeyRef.current) {
      bootstrappedKeyRef.current = nextKey
      if (pending?.sessionId) {
        runBootstrapExisting(
          pending.sessionId,
          pending.contextAnalysisId,
        ).catch(() => undefined)
      } else if (pending?.analysisId) {
        runBootstrap(pending.analysisId).catch(() => undefined)
      } else {
        runBootstrap().catch(() => undefined)
      }
    }

    // 预填问题：仅在"本次有新 pending.prefill"或首次进入带 router.params.prefill 时填一次。
    // 用户切 tab 回来不会再被覆盖（didPrefillRef 控制）。
    if (!didPrefillRef.current) {
      const prefillFromRouter = router.params?.prefill
        ? (() => {
            try {
              return decodeURIComponent(router.params.prefill as string)
            } catch {
              return ''
            }
          })()
        : ''
      const prefill = pending?.prefill || prefillFromRouter
      if (prefill) setInput(prefill)
      didPrefillRef.current = true
    } else if (pending?.prefill) {
      // 之前 didPrefill=true，但本次 user 又从报告页带了新 prefill —— 这是新意图，应覆盖
      setInput(pending.prefill)
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
  const isGuest = initialized && !token
  const trimmed = input.trim()
  const canSend = isGuest
    ? Boolean(trimmed && !sending)
    : Boolean(
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
        toastSubmitError(se, err)
      }
    },
    [submitMessage],
  )

  const handleSend = useCallback(() => {
    if (isGuest) {
      promptGuestLogin(
        trimmed
          ? '登录后即可发送本条问题并获取个性化回复'
          : '输入问题后，登录即可发送',
      )
      return
    }
    if (!canSend) return
    const content = trimmed
    setInput('')
    void runSend(content)
  }, [isGuest, canSend, runSend, trimmed])

  const handleInput = (e: BaseEventOrig<{ value: string }>) => {
    const raw = e.detail?.value ?? ''
    const value = raw.slice(0, MAX_CONTENT_LEN)
    // P2-C1：粘贴/拼音组合后超过上限时，明确告知用户"已被截断到 500 字"，
    // 而不是"突然少了一段还不知道为什么"。
    if (raw.length > MAX_CONTENT_LEN && !truncatedToastShownRef.current) {
      truncatedToastShownRef.current = true
      Taro.showToast({
        title: `单条最多 ${MAX_CONTENT_LEN} 字，已自动截断`,
        icon: 'none',
        duration: 1800,
      })
    }
    // 用户主动删字到上限以下后允许再次提示（下一次粘贴超长再弹一次）
    if (raw.length <= MAX_CONTENT_LEN) {
      truncatedToastShownRef.current = false
    }
    setInput(value)
  }

  const handleTapQuickQuestion = useCallback(
    (q: QuickQuestionItem) => {
      if (sending) return
      if (isGuest) {
        setInput(q.text)
        return
      }
      if (q.requires_analysis && (user?.stats?.total_analyses ?? 0) === 0) {
        Taro.showModal({
          title: '需要先上传一次挥杆',
          content: '这个问题需要结合你的挥杆分析，先去"首页 → 开始分析"拍一次吧。',
          confirmText: '去分析',
          success: ({ confirm }) => {
            if (confirm)
              void switchToHome().catch(toastTabNavigationFailure)
          },
        })
        return
      }
      setInput(q.text)
    },
    [isGuest, sending, user?.stats?.total_analyses],
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

  if (!initialized) {
    return (
      <View className='coach coach--loading'>
        <Text className='coach__loading-text'>加载中...</Text>
      </View>
    )
  }

  if (!isGuest && loading && messages.length === 0 && !bootstrapError) {
    return (
      <View className='coach coach--loading'>
        <Text className='coach__loading-text'>正在接入 AI 教练...</Text>
      </View>
    )
  }

  if (!isGuest && bootstrapError) {
    return (
      <View className='coach coach--error'>
        <Text className='coach__error-icon'>⚠️</Text>
        <Text className='coach__error-msg'>{bootstrapError}</Text>
        <Button className='coach__retry-btn' onClick={() => runBootstrap()}>
          重新加载
        </Button>
      </View>
    )
  }

  const showEmptyState = !isGuest && messages.length === 0 && !sending
  const displayQuickQuestions =
    isGuest && quickQuestions.length === 0
      ? GUEST_FALLBACK_QUICK_QUESTIONS
      : quickQuestions
  const showQuickQuestions =
    isGuest || (showEmptyState && displayQuickQuestions.length > 0)
  const quotaExhausted = !isGuest && isQuotaExhausted(quota)
  const remainingText = isGuest
    ? '登录后可开始对话 · 可先浏览示例'
    : renderQuotaText(quota)
  const userBubbleInitial = pickUserBubbleInitial(user?.nickname)

  return (
    <View className={`coach${isGuest ? ' coach--browse' : ''}`}>
      <EnvBadge />
      <View
        className={`coach__header ${
          contextAnalysisId && !isGuest ? '' : 'coach__header--compact'
        }`}
      >
        {isGuest ? (
          <View className='coach__guest-banner'>
            <Text className='coach__guest-banner-text'>
              功能预览 · 登录后开启完整对话
            </Text>
            <Text
              className='coach__guest-banner-link'
              onClick={() => Taro.navigateTo({ url: '/pages/login/index' })}
            >
              登录
            </Text>
          </View>
        ) : (
          <>
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
            ) : null}
            <Text className='coach__clear-btn' onClick={handleClear}>
              清空对话
            </Text>
          </>
        )}
      </View>

      <ScrollView
        className='coach__scroll'
        scrollY
        scrollWithAnimation
        scrollIntoView={scrollAnchorRef.current}
        enhanced
        enableFlex
        showScrollbar={false}
      >
        <View className='coach__scroll-inner'>
          <MessageBubble
            message={buildWelcomeMessage()}
            isWelcome
            logoSrc={BRAND_LOGO}
          />

          {isGuest ? (
            <>
              <View className='coach__demo-label'>
                <Text className='coach__demo-label-text'>示例对话（预览）</Text>
              </View>
              {GUEST_DEMO_MESSAGES.map((m) => (
                <MessageBubble
                  key={m.id}
                  message={m}
                  logoSrc={BRAND_LOGO}
                  userInitial='访'
                />
              ))}
              <View className='coach__disclaimer'>
                <Text className='coach__disclaimer-text'>
                  回复为人工智能生成内容，仅供参考，不能替代持证教练现场指导或医疗处置。
                </Text>
              </View>
            </>
          ) : null}

          {showQuickQuestions && (
            <View className='coach__quick'>
              <Text className='coach__quick-title'>试试这些问题：</Text>
              {displayQuickQuestions.map((q) => (
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
              logoSrc={BRAND_LOGO}
              userInitial={userBubbleInitial}
              onLongPress={() => handleLongPress(m)}
              onRetry={m.errored && m.role === 'assistant' ? () => handleRetry(m) : undefined}
            />
          ))}

          {sending && messages[messages.length - 1]?.content === '' && (
            <View className='coach__msg coach__msg--assistant'>
              <View className='coach__avatar-wrap'>
                <Image className='coach__avatar-img' src={BRAND_LOGO} mode='aspectFit' />
              </View>
              <View className='coach__msg-body'>
                <View className='coach__typing'>
                  <Text className='coach__typing-dot' />
                  <Text className='coach__typing-dot' />
                  <Text className='coach__typing-dot' />
                </View>
              </View>
            </View>
          )}

          <View id={scrollAnchorRef.current} className='coach__anchor' />
        </View>
      </ScrollView>

      <View className='coach__footer'>
        {quotaExhausted ? (
          // W8-T3：PAYMENT_ENABLED=false 时不引导升级会员，
          //   改为提示"次日刷新 / 联系运营"，避免误导内测用户去找付费入口
          <View
            className='coach__upgrade'
            onClick={() =>
              PAYMENT_ENABLED_FLAG
                ? Taro.showModal({
                    title: '今日对话已用完',
                    content: '升级会员即可享受不限次 AI 对话。',
                    confirmText: '开通会员',
                    success: ({ confirm }) => {
                      if (confirm) {
                        Taro.navigateTo({ url: '/pages/profile/membership' })
                      }
                    },
                  })
                : Taro.showModal({
                    title: '今日对话已用完',
                    content: '内测阶段全员可用，明天 0 点自动刷新。',
                    confirmText: '我知道了',
                    showCancel: false,
                  })
            }
          >
            <Text className='coach__upgrade-text'>
              {PAYMENT_ENABLED_FLAG
                ? '今日对话已用完，点此了解会员特权'
                : '今日对话已用完，明天 0 点自动刷新'}
            </Text>
          </View>
        ) : (
          <View className='coach__input-row'>
            <Input
              className='coach__input'
              type='text'
              placeholder={
                isGuest
                  ? '输入问题，登录后发送…'
                  : sending
                    ? 'AI 正在回复，稍等片刻...'
                    : '问问 AI 教练...'
              }
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
              {isGuest ? '登录发送' : '发送'}
            </Button>
          </View>
        )}
        <View className='coach__meta'>
          <Text className='coach__quota'>{remainingText}</Text>
          {!isGuest ? (
            <Text
              className={`coach__len ${
                input.length >= MAX_CONTENT_LEN
                  ? 'coach__len--danger'
                  : input.length >= MAX_CONTENT_LEN - 50
                    ? 'coach__len--warning'
                    : ''
              }`}
            >
              {input.length}/{MAX_CONTENT_LEN}
            </Text>
          ) : null}
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
  /** 小程序内用品牌 LOGO 圆标，替代默认 emoji */
  logoSrc: string
  /** 用户气泡右侧首字头像 */
  userInitial?: string
  onLongPress?: () => void
  onRetry?: () => void
}

function renderMessageAttachment(
  attachment: MessageAttachment,
  key: string,
): JSX.Element | null {
  switch (attachment.type) {
    case 'drill_card':
      return (
        <DrillCard
          key={key}
          attachment={attachment as DrillCardAttachment}
        />
      )
    case 'video_card':
      return (
        <VideoCard
          key={key}
          attachment={attachment as VideoCardAttachment}
        />
      )
    case 'analysis_card':
      return (
        <AnalysisCard
          key={key}
          attachment={attachment as AnalysisCardAttachment}
        />
      )
    default:
      return (
        <View key={key} className='coach__attachment-placeholder'>
          <Text>（暂不支持的附件类型，请升级 App）</Text>
        </View>
      )
  }
}

const MessageBubble: FC<BubbleProps> = ({
  message,
  isWelcome,
  logoSrc,
  userInitial = '我',
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

  return (
    <View
      className={`coach__msg ${
        isUser ? 'coach__msg--user' : 'coach__msg--assistant'
      }`}
      onLongPress={onLongPress}
    >
      {!isUser && (
        <View className='coach__avatar-wrap'>
          <Image className='coach__avatar-img' src={logoSrc} mode='aspectFit' />
        </View>
      )}
      <View className='coach__msg-body'>
        <View className='coach__bubble-col'>
          <View className={cls}>
            <Text
              userSelect={!!isWelcome}
              className={
                isUser
                  ? 'coach__bubble-text coach__bubble-text--user'
                  : isWelcome
                    ? 'coach__bubble-text coach__bubble-text--welcome'
                    : 'coach__bubble-text coach__bubble-text--ai'
              }
            >
              {message.content}
            </Text>
            {message.streaming && !message.errored && (
              <Text className='coach__cursor'>▎</Text>
            )}
          </View>
          {!isUser &&
            (message.attachments || []).map((att, i) =>
              renderMessageAttachment(att, `${message.id}-att-${i}`),
            )}
          {onRetry && (
            <View className='coach__retry-row' onClick={onRetry}>
              <Text>↻ 点击重试</Text>
            </View>
          )}
        </View>
      </View>
      {isUser && (
        <View className='coach__avatar-wrap coach__avatar-wrap--user'>
          <Text className='coach__avatar-letter'>{userInitial}</Text>
        </View>
      )}
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

/** 用户气泡右侧圆标：优先昵称首字，缺省「我」 */
function pickUserBubbleInitial(nickname: string | null | undefined): string {
  const s = (nickname ?? '').trim()
  if (!s) return '我'
  const ch = [...s][0]
  return ch || '我'
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

function toastSubmitError(
  err: SubmitMessageError | null,
  wrapped?: unknown,
): void {
  if (!err) {
    Taro.showToast({
      title:
        wrapped !== undefined
          ? describeIntermittentRequestFailure(wrapped).toastTitle
          : '发送失败',
      icon: 'none',
    })
    return
  }
  switch (err.kind) {
    case 'quota_exhausted':
      // W8-T3：PAYMENT_ENABLED=false 时不引导升级会员
      if (PAYMENT_ENABLED_FLAG) {
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
      } else {
        Taro.showModal({
          title: '今日对话已用完',
          content: '内测阶段全员可用，明天 0 点自动刷新。',
          confirmText: '我知道了',
          showCancel: false,
        })
      }
      break
    case 'rate_limit':
      Taro.showToast({ title: '操作太快了，稍等片刻再试', icon: 'none' })
      break
    case 'content_violation':
      // P1-C1：内容审核命中。给用户更明确的提示，且不消耗配额
      Taro.showModal({
        title: '消息无法发送',
        content: err.message || '内容涉嫌违规，请调整后重试',
        confirmText: '我知道了',
        showCancel: false,
      })
      break
    case 'service_error':
      Taro.showToast({
        title: 'AI 教练开小差了，点击气泡重试',
        icon: 'none',
      })
      break
    case 'network':
    default: {
      const raw = wrapped !== undefined ? chatErrorCause(wrapped) ?? wrapped : undefined
      const fallback = err.message?.trim() || '网络中断，点击气泡重试'
      const title =
        raw !== undefined
          ? describeIntermittentRequestFailure(raw).toastTitle
          : fallback
      Taro.showToast({
        title,
        icon: 'none',
      })
      break
    }
  }
}
