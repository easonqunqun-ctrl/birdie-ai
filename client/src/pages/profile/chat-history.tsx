import { FC, useCallback, useEffect, useState } from 'react'
import { View, Text, Button, ScrollView } from '@tarojs/components'
import Taro, { usePullDownRefresh } from '@tarojs/taro'
import { chatService } from '@/services/chatService'
import { switchToCoachWithSession } from '@/utils/tabNav'
import type { ChatSessionListItem } from '@/types/chat'
import './chat-history.scss'

const ChatHistoryPage: FC = () => {
  const [items, setItems] = useState<ChatSessionListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await chatService.listSessions({ page: 1, page_size: 50 })
      setItems(res.items)
      setError(null)
    } catch (e) {
      setError((e as Error).message || '加载失败')
    } finally {
      setLoading(false)
      Taro.stopPullDownRefresh()
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  usePullDownRefresh(() => {
    setLoading(true)
    load()
  })

  const openSession = (it: ChatSessionListItem) => {
    void switchToCoachWithSession(it.id, it.context_analysis_id)
  }

  if (loading) {
    return (
      <View className='chat-hist chat-hist--loading'>
        <Text>加载中…</Text>
      </View>
    )
  }

  if (error) {
    return (
      <View className='chat-hist chat-hist--error'>
        <Text>😣</Text>
        <Text className='chat-hist__error-msg'>{error}</Text>
        <Button onClick={() => { setLoading(true); void load() }}>重试</Button>
      </View>
    )
  }

  if (items.length === 0) {
    return (
      <View className='chat-hist chat-hist--empty'>
        <Text>暂无对话记录</Text>
        <Text style={{ marginTop: 12, fontSize: 26, color: 'var(--color-text-tertiary)' }}>
          在 AI 教练里提问后会出现在这里
        </Text>
      </View>
    )
  }

  return (
    <ScrollView scrollY className='chat-hist'>
      {items.map((it) => (
        <View
          key={it.id}
          className='chat-hist__item'
          onClick={() => openSession(it)}
        >
          <Text className='chat-hist__preview'>
            {it.last_message_preview || '（无预览）'}
          </Text>
          <View className='chat-hist__meta'>
            <Text>
              {it.message_count} 条消息
              {it.last_message_at
                ? ` · ${it.last_message_at.slice(0, 16).replace('T', ' ')}`
                : ''}
            </Text>
            <Text>›</Text>
          </View>
        </View>
      ))}
    </ScrollView>
  )
}

export default ChatHistoryPage
