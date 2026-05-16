import { FC, useState } from 'react'
import { View, Text, Button, Input } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { describeIntermittentRequestFailure, isRequestError } from '@/services/request'
import { useUserStore } from '@/store/userStore'
import { userService } from '@/services/userService'
import { FREQS, GOALS, LEVELS, MAX_GOALS } from '@/constants/golf'
import type { GolfLevel, PrimaryGoal, UserUpdateRequest, WeeklyFreq } from '@/types/api'
import './edit.scss'

/**
 * "我的 · 编辑档案" 页。
 *
 * 设计点：
 * - 只提交发生变化的字段（减少无谓写入 & 对应后端的 exclude_unset）。
 * - 昵称长度约束（2-12）与后端 Pydantic schema 保持一致，前端先拦截。
 * - 头像暂不做上传（W3/COS 落地后再接），允许用户贴 URL 或留空。
 */
const ProfileEditPage: FC = () => {
  const { user, fetchMe } = useUserStore()

  const [nickname, setNickname] = useState(user?.nickname ?? '')
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url ?? '')
  const [level, setLevel] = useState<GolfLevel | null>(
    (user?.golf_level as GolfLevel | null) ?? null
  )
  const [goals, setGoals] = useState<PrimaryGoal[]>(
    (user?.primary_goals as PrimaryGoal[] | undefined) ?? []
  )
  const [freq, setFreq] = useState<WeeklyFreq | null>(
    (user?.weekly_practice_frequency as WeeklyFreq | null) ?? null
  )
  const [saving, setSaving] = useState(false)

  if (!user) {
    return (
      <View className='profile-edit profile-edit--empty'>
        <Text>请先登录</Text>
      </View>
    )
  }

  const toggleGoal = (g: PrimaryGoal) => {
    setGoals((prev) =>
      prev.includes(g)
        ? prev.filter((x) => x !== g)
        : prev.length >= MAX_GOALS
          ? prev
          : [...prev, g]
    )
  }

  /** 基于 user 的当前值做 diff，只发送有变更的字段 */
  const buildPatch = (): UserUpdateRequest | null => {
    const patch: UserUpdateRequest = {}
    const trimmedNickname = nickname.trim()
    if (trimmedNickname !== (user.nickname ?? '')) {
      patch.nickname = trimmedNickname
    }
    if (avatarUrl !== (user.avatar_url ?? '')) {
      patch.avatar_url = avatarUrl || undefined
    }
    if (level && level !== user.golf_level) {
      patch.golf_level = level
    }
    const currentGoals = (user.primary_goals ?? []) as PrimaryGoal[]
    if (!arraysEqual(goals, currentGoals)) {
      patch.primary_goals = goals
    }
    if (freq && freq !== user.weekly_practice_frequency) {
      patch.weekly_practice_frequency = freq
    }
    return Object.keys(patch).length > 0 ? patch : null
  }

  const handleSave = async () => {
    // 昵称长度校验（与后端 schema 一致）
    const trimmed = nickname.trim()
    if (trimmed && (trimmed.length < 2 || trimmed.length > 12)) {
      Taro.showToast({ title: '昵称需 2-12 字', icon: 'none' })
      return
    }
    const patch = buildPatch()
    if (!patch) {
      Taro.showToast({ title: '未修改', icon: 'none' })
      return
    }
    setSaving(true)
    try {
      await userService.updateMe(patch)
      await fetchMe()
      Taro.showToast({ title: '保存成功', icon: 'success' })
      setTimeout(() => Taro.navigateBack(), 400)
    } catch (e) {
      console.warn('update profile failed', e)
      const title =
        isRequestError(e) && e.kind === 'business' && e.message?.trim()
          ? e.message.trim().slice(0, 220)
          : describeIntermittentRequestFailure(e).toastTitle
      Taro.showToast({
        title,
        icon: 'none',
      })
      setSaving(false)
    }
  }

  return (
    <View className='profile-edit'>
      <View className='profile-edit__section'>
        <Text className='profile-edit__section-title'>基础信息</Text>
        <View className='profile-edit__field'>
          <Text className='profile-edit__field-label'>昵称</Text>
          <Input
            className='profile-edit__input'
            value={nickname}
            placeholder='2-12 个字'
            maxlength={12}
            onInput={(e) => setNickname(e.detail.value)}
          />
        </View>
        <View className='profile-edit__field'>
          <Text className='profile-edit__field-label'>头像 URL</Text>
          <Input
            className='profile-edit__input'
            value={avatarUrl}
            placeholder='留空使用默认头像'
            onInput={(e) => setAvatarUrl(e.detail.value)}
          />
        </View>
      </View>

      <View className='profile-edit__section'>
        <Text className='profile-edit__section-title'>高尔夫水平</Text>
        <View className='profile-edit__options'>
          {LEVELS.map((l) => (
            <View
              key={l.value}
              className={`profile-edit__option ${level === l.value ? 'profile-edit__option--active' : ''}`}
              onClick={() => setLevel(l.value)}
            >
              <Text className='profile-edit__option-label'>{l.label}</Text>
              <Text className='profile-edit__option-desc'>{l.desc}</Text>
            </View>
          ))}
        </View>
      </View>

      <View className='profile-edit__section'>
        <Text className='profile-edit__section-title'>主要目标（最多 {MAX_GOALS} 个）</Text>
        <View className='profile-edit__chips'>
          {GOALS.map((g) => (
            <View
              key={g.value}
              className={`profile-edit__chip ${goals.includes(g.value) ? 'profile-edit__chip--active' : ''}`}
              onClick={() => toggleGoal(g.value)}
            >
              <Text>{g.label}</Text>
            </View>
          ))}
        </View>
      </View>

      <View className='profile-edit__section'>
        <Text className='profile-edit__section-title'>练习频率</Text>
        <View className='profile-edit__chips'>
          {FREQS.map((f) => (
            <View
              key={f.value}
              className={`profile-edit__chip ${freq === f.value ? 'profile-edit__chip--active' : ''}`}
              onClick={() => setFreq(f.value)}
            >
              <Text>{f.label}</Text>
            </View>
          ))}
        </View>
      </View>

      <View className='profile-edit__footer'>
        <Button
          className='profile-edit__btn'
          loading={saving}
          disabled={saving}
          onClick={handleSave}
        >
          {saving ? '保存中…' : '保存'}
        </Button>
      </View>
    </View>
  )
}

function arraysEqual<T>(a: readonly T[], b: readonly T[]): boolean {
  if (a.length !== b.length) return false
  const setA = new Set(a)
  return b.every((x) => setA.has(x))
}

export default ProfileEditPage
