import { FC, useState } from 'react'
import { View, Text, Input, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useUserStore } from '@/store/userStore'
import { userService } from '@/services/userService'
import './account-deletion.scss'

const AccountDeletionPage: FC = () => {
  const { user, fetchMe, logout } = useUserStore()
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  const scheduled = user?.account_deletion_scheduled_at
  const scheduledText = scheduled
    ? (() => {
        try {
          return new Date(scheduled).toLocaleString()
        } catch {
          return scheduled
        }
      })()
    : ''

  const onSubmit = () => {
    if (text.trim() !== 'DELETE') {
      Taro.showToast({ title: '请在输入框中完整输入 DELETE', icon: 'none' })
      return
    }
    Taro.showModal({
      title: '最后确认',
      content: '提交后账号将进入注销排期，到期后数据将永久删除且不可恢复。',
      success: async ({ confirm }) => {
        if (!confirm) return
        setSubmitting(true)
        try {
          await userService.requestAccountDeletion('DELETE')
          await fetchMe()
          Taro.showToast({ title: '已提交注销', icon: 'success' })
          setText('')
        } catch (e: any) {
          const msg = e?.data?.message || e?.message || '操作失败'
          Taro.showToast({ title: msg, icon: 'none' })
        } finally {
          setSubmitting(false)
        }
      }
    })
  }

  const onCancelSchedule = () => {
    Taro.showModal({
      title: '取消注销',
      content: '确定恢复账号？已排期的删除将被撤销。',
      success: async ({ confirm }) => {
        if (!confirm) return
        setCancelling(true)
        try {
          await userService.cancelAccountDeletion()
          await fetchMe()
          Taro.showToast({ title: '已取消', icon: 'success' })
        } catch (e: any) {
          const msg = e?.data?.message || e?.message || '操作失败'
          Taro.showToast({ title: msg, icon: 'none' })
        } finally {
          setCancelling(false)
        }
      }
    })
  }

  if (!user) {
    return (
      <View className='account-del'>
        <Text>请先登录</Text>
      </View>
    )
  }

  return (
    <View className='account-del'>
      <Text className='account-del__title'>注销说明</Text>
      <Text className='account-del__desc'>
        注销后，我们将在排期时间到达时删除你的账号与关联数据。若你仍有未完成订单或争议，可能暂时无法完成注销（以服务端提示为准）。
      </Text>
      <View className='account-del__warn'>
        在下方输入框中输入大写 DELETE 以确认你理解此操作不可撤销。
      </View>

      {scheduled && (
        <View className='account-del__scheduled'>
          <Text>
            当前状态：已排期注销
            {scheduledText ? `，预计时间：${scheduledText}` : ''}。
          </Text>
          <Button
            className='account-del__btn'
            style={{ marginTop: 20 }}
            loading={cancelling}
            onClick={onCancelSchedule}
          >
            撤销注销
          </Button>
        </View>
      )}

      {!scheduled && (
        <>
          <Text className='account-del__field-label'>确认文本</Text>
          <Input
            className='account-del__input'
            value={text}
            placeholder='输入 DELETE'
            onInput={(e) => setText(e.detail.value)}
          />
          <View className='account-del__actions'>
            <Button
              className='account-del__btn account-del__btn--danger'
              loading={submitting}
              onClick={onSubmit}
            >
              确认注销
            </Button>
            <Button
              className='account-del__btn'
              onClick={() => Taro.navigateBack()}
            >
              返回
            </Button>
          </View>
        </>
      )}

      {scheduled && (
        <View className='account-del__actions'>
          <Button
            className='account-del__btn'
            onClick={() => {
              logout()
              Taro.reLaunch({ url: '/pages/login/index' })
            }}
          >
            退出并返回登录
          </Button>
        </View>
      )}
    </View>
  )
}

export default AccountDeletionPage
