import { FC, useMemo, useState } from 'react'
import { View, Text, Textarea, Input, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { feedbackService } from '@/services/feedbackService'
import { isRequestError } from '@/services/request'
import './feedback.scss'

const MAX_LEN = 500

const FeedbackPage: FC = () => {
  const [content, setContent] = useState('')
  const [contact, setContact] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const trimmedLen = useMemo(() => content.trim().length, [content])
  const canSubmit = trimmedLen > 0 && trimmedLen <= MAX_LEN && !submitting

  const onSubmit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    try {
      await feedbackService.submit({
        content: content.trim(),
        contact: contact.trim() || undefined,
      })
      Taro.showToast({ title: '感谢你的反馈', icon: 'success' })
      setTimeout(() => Taro.navigateBack().catch(() => undefined), 800)
    } catch (err) {
      if (isRequestError(err) && err.code === 42901) {
        Taro.showToast({ title: '反馈太频繁，请稍后再试', icon: 'none' })
      } else if (isRequestError(err) && err.kind === 'http_unauthorized') {
        Taro.showToast({ title: '登录已失效，请重新登录', icon: 'none' })
      } else {
        Taro.showToast({ title: '提交失败，请稍后重试', icon: 'none' })
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <View className='feedback'>
      <Text className='feedback__title'>你的建议很重要</Text>
      <Text className='feedback__desc'>
        遇到 bug、不顺手的交互、想要的训练动作，都欢迎告诉我们。每一条都会被产品和工程团队看到。
      </Text>

      <Text className='feedback__label'>反馈内容</Text>
      <Textarea
        className='feedback__textarea'
        value={content}
        maxlength={MAX_LEN}
        placeholder={`说说你的想法（${MAX_LEN} 字以内）`}
        placeholderClass='feedback__placeholder'
        onInput={(e) => setContent(e.detail.value)}
        autoHeight
      />
      <Text className='feedback__counter'>
        {trimmedLen} / {MAX_LEN}
      </Text>

      <Text className='feedback__label'>联系方式（选填）</Text>
      <Input
        className='feedback__input'
        value={contact}
        maxlength={128}
        placeholder='手机号 / 邮箱 / 微信号，方便我们回访'
        placeholderClass='feedback__placeholder'
        onInput={(e) => setContact(e.detail.value)}
      />

      <View className='feedback__actions'>
        <Button
          className='feedback__submit'
          disabled={!canSubmit}
          loading={submitting}
          onClick={onSubmit}
        >
          提交反馈
        </Button>
      </View>
    </View>
  )
}

export default FeedbackPage
