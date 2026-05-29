/**
 * 分析模式选择器（M10-01 / M10-02 复用）
 */

import { FC } from 'react'
import { View, Text } from '@tarojs/components'
import type { AnalysisMode } from '@/types/analysis'
import './ModeSelector.scss'

export interface ModeOption {
  value: AnalysisMode
  label: string
  icon: string
  disabled?: boolean
  hint?: string
}

export interface ModeSelectorProps {
  value: AnalysisMode
  options: ModeOption[]
  onChange: (mode: AnalysisMode) => void
}

const ModeSelector: FC<ModeSelectorProps> = ({ value, options, onChange }) => (
  <View className='mode-selector'>
    {options.map((opt) => {
      const active = value === opt.value
      const disabled = opt.disabled === true
      return (
        <View
          key={opt.value}
          className={[
            'mode-selector__item',
            active ? 'mode-selector__item--active' : '',
            disabled ? 'mode-selector__item--disabled' : '',
          ]
            .filter(Boolean)
            .join(' ')}
          onClick={() => {
            if (!disabled) onChange(opt.value)
          }}
        >
          <Text className='mode-selector__icon'>{opt.icon}</Text>
          <Text className='mode-selector__label'>{opt.label}</Text>
          {opt.hint ? <Text className='mode-selector__hint'>{opt.hint}</Text> : null}
        </View>
      )
    })}
  </View>
)

export default ModeSelector
