/**
 * P2-M13-08 · 发起挑战赛
 */

import { FC, useCallback, useState } from 'react'
import { View, Text, Input, Button } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { PHASE2_MEETUP_ENABLED_FLAG } from '@/constants/flags'
import {
  meetupEventService,
  type MeetupEventTemplate,
  type MeetupEventTemplateCode,
} from '@/services/meetupEventService'
import './create.scss'

const MeetupEventCreatePage: FC = () => {
  const [templates, setTemplates] = useState<MeetupEventTemplate[]>([])
  const [title, setTitle] = useState('')
  const [templateCode, setTemplateCode] = useState<MeetupEventTemplateCode | ''>('')
  const [submitting, setSubmitting] = useState(false)

  const loadTemplates = useCallback(async () => {
    try {
      const list = await meetupEventService.listTemplates()
      setTemplates(list)
      if (!templateCode && list[0]) {
        setTemplateCode(list[0].code)
      }
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '加载模板失败',
        icon: 'none',
      })
    }
  }, [templateCode])

  useDidShow(() => {
    if (!PHASE2_MEETUP_ENABLED_FLAG) {
      Taro.navigateBack()
      return
    }
    void loadTemplates()
  })

  const onSubmit = async () => {
    const trimmed = title.trim()
    if (!trimmed || !templateCode) {
      Taro.showToast({ title: '请填写标题并选择模板', icon: 'none' })
      return
    }
    setSubmitting(true)
    try {
      const event = await meetupEventService.create({
        title: trimmed,
        template_code: templateCode,
      })
      Taro.showToast({ title: '已创建', icon: 'success' })
      Taro.redirectTo({
        url: `/pages/meetup/events/detail?id=${encodeURIComponent(event.id)}`,
      })
    } catch (e) {
      Taro.showToast({
        title: e instanceof Error ? e.message : '创建失败',
        icon: 'none',
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <View className='meetup-event-create'>
      <Text className='meetup-event-create__label'>挑战名称</Text>
      <Input
        className='meetup-event-create__input'
        value={title}
        placeholder='例如：周末推杆小挑战'
        onInput={(e) => setTitle(e.detail.value)}
      />

      <Text className='meetup-event-create__label'>选择模板（荣誉徽章，无现金奖励）</Text>
      {templates.map((tpl) => (
        <View
          key={tpl.code}
          className={[
            'meetup-event-create__tpl',
            templateCode === tpl.code ? 'meetup-event-create__tpl--active' : '',
          ]
            .filter(Boolean)
            .join(' ')}
          onClick={() => setTemplateCode(tpl.code)}
        >
          <Text className='meetup-event-create__tpl-title'>{tpl.label}</Text>
          <Text className='meetup-event-create__tpl-desc'>{tpl.description}</Text>
        </View>
      ))}

      <Button
        className='meetup-event-create__submit'
        loading={submitting}
        disabled={submitting}
        onClick={() => void onSubmit()}
      >
        创建并开放报名
      </Button>
    </View>
  )
}

export default MeetupEventCreatePage
