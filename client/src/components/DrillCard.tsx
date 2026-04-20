/**
 * DrillCard — AI 回复里携带的"训练动作卡片"附件渲染
 *
 * 数据来源：
 *   - 后端 SSE `attachment` 事件：`{type: 'drill_card', drill_id, name}`
 *   - 详情（时长 / 步骤 / 难度）由前端内置 `@/constants/drillLibrary`
 *     按 `drill_id` 查；查不到兜底为通用模板
 *
 * 交互：
 *   - 默认折叠只显示名称 / 时长 / "查看步骤"
 *   - 点击卡片展开显示 3-5 条步骤
 *   - "加入训练计划" 在 M3 阶段是占位 —— toast `M4 再开放`
 */

import { FC, useState } from 'react'
import { View, Text, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { getDrillDetail } from '@/constants/drillLibrary'
import type { DrillCardAttachment } from '@/types/chat'
import './DrillCard.scss'

interface DrillCardProps {
  attachment: DrillCardAttachment
}

export const DrillCard: FC<DrillCardProps> = ({ attachment }) => {
  const detail = getDrillDetail(attachment.drill_id)
  // 附件上的 name 优先展示（AI 有时起的名字更贴合上下文，如"针对你今天的下杆快"）；
  // fallback 到内置 drill 库的 name
  const title = attachment.name || detail.name
  const [expanded, setExpanded] = useState(false)

  const toggle = () => setExpanded((v) => !v)
  const handleAddToPlan = (e: { stopPropagation?: () => void }) => {
    e.stopPropagation?.()
    Taro.showToast({ title: '训练计划 M4 再开放', icon: 'none' })
  }

  return (
    <View className='drill-card' onClick={toggle}>
      <View className='drill-card__head'>
        <View className='drill-card__meta'>
          <Text className='drill-card__badge'>{detail.difficulty}</Text>
          <Text className='drill-card__name'>{title}</Text>
        </View>
        <Text className='drill-card__duration'>
          {detail.duration_minutes} 分钟 · {detail.sets} 组
        </Text>
      </View>

      <Text className='drill-card__desc'>{detail.description}</Text>

      {expanded && (
        <View className='drill-card__steps'>
          {detail.steps.map((step, i) => (
            <View key={i} className='drill-card__step'>
              <Text className='drill-card__step-index'>{i + 1}</Text>
              <Text className='drill-card__step-text'>{step}</Text>
            </View>
          ))}
          {detail.equipment && detail.equipment.length > 0 && (
            <Text className='drill-card__equipment'>
              所需器材：{detail.equipment.join(' / ')}
            </Text>
          )}
        </View>
      )}

      <View className='drill-card__footer'>
        <Text className='drill-card__toggle'>
          {expanded ? '收起步骤' : '查看步骤'}
        </Text>
        <Button
          className='drill-card__add-btn'
          onClick={handleAddToPlan}
        >
          加入训练计划
        </Button>
      </View>
    </View>
  )
}

export default DrillCard
