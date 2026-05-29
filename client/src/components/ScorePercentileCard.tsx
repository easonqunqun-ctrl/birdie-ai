/**
 * P2-W16-B · ENG-05 · 同水平+同器材分位卡（"你击败了 X% 同水平用户"）.
 *
 * 设计要点
 * ========
 *
 * 1. **样本量自检**：cohort_size < 5 → 服务端已经把 percentile/median 设 null，前端**就不渲染**整张卡。
 *    （别在小样本上吹牛骗自己。）
 * 2. **得分对位**：同时显示 user_score / median，让"我比群体高/低多少"直接可看。
 * 3. **club_type 透传**：训练页可同时挂多张卡（用户可在卡片切换"七号铁/一号木"）。
 *    本组件本身只渲染**一张**，club_type 切换由父组件控。
 * 4. **percentile=0 也显示**："只击败 0%"是个真实信号，不能藏（避免用户误以为"加载失败"）。
 * 5. **加载/错误**：本组件不做 loading 态——父组件没拿到数据就别 render；
 *    错误兜底交给 catch block + ToastErr。
 *
 * 颜色语义
 * --------
 * - percentile ≥ 75 → 金（c9a227） · "你打得不错"
 * - percentile ≥ 50 → 主色靛蓝 · "中位之上"
 * - percentile < 50 → 文字次级灰 · 不渲染金/绿，避免视觉鼓励"我刚击败 5%" 这种 UX 误导
 *
 * 隐私
 * ----
 * 后端只回聚合（cohort_size / median / percentile），本组件不暴露其他用户细节，
 * 也不允许"对方/对手"等措辞——只用"同水平用户"等抽象词。
 */

import { FC } from 'react'
import { Text, View } from '@tarojs/components'
import './ScorePercentileCard.scss'

export interface ScorePercentileData {
  user_score: number | null
  percentile: number | null
  cohort_size: number
  cohort_label: string
  median: number | null
  club_type: string
  golf_level: string | null
  computed_at: string
}

export interface ScorePercentileCardProps {
  data: ScorePercentileData | null
  /** 父组件可在这里塞"切换器"（如 ClubTypePicker），渲染在卡片头部右侧 */
  rightSlot?: React.ReactNode
}

const ScorePercentileCard: FC<ScorePercentileCardProps> = ({ data, rightSlot }) => {
  if (!data) return null
  const { user_score, percentile, cohort_size, cohort_label, median } = data

  // W16-A 服务端约定：cohort_size < 5 → percentile=null，UI 整卡隐藏
  if (percentile === null || user_score === null) return null

  // 颜色梯度：≥75 金 / ≥50 主色 / <50 次级灰
  let percentileTone: 'gold' | 'primary' | 'muted' = 'muted'
  if (percentile >= 75) percentileTone = 'gold'
  else if (percentile >= 50) percentileTone = 'primary'

  return (
    <View className="score-percentile-card">
      <View className="score-percentile-card__head">
        <Text className="score-percentile-card__title">同水平对比</Text>
        {rightSlot ? <View className="score-percentile-card__slot">{rightSlot}</View> : null}
      </View>

      <View className="score-percentile-card__body">
        <Text className={`score-percentile-card__pct score-percentile-card__pct--${percentileTone}`}>
          {percentile}%
        </Text>
        <Text className="score-percentile-card__sub">
          击败 {percentile}% {cohort_label}
        </Text>
      </View>

      <View className="score-percentile-card__meta">
        <View className="score-percentile-card__meta-item">
          <Text className="score-percentile-card__meta-label">你</Text>
          <Text className="score-percentile-card__meta-value">{user_score}</Text>
        </View>
        <View className="score-percentile-card__meta-divider" />
        <View className="score-percentile-card__meta-item">
          <Text className="score-percentile-card__meta-label">群体中位</Text>
          <Text className="score-percentile-card__meta-value">{median}</Text>
        </View>
        <View className="score-percentile-card__meta-divider" />
        <View className="score-percentile-card__meta-item">
          <Text className="score-percentile-card__meta-label">样本</Text>
          <Text className="score-percentile-card__meta-value">{cohort_size}</Text>
        </View>
      </View>
    </View>
  )
}

export default ScorePercentileCard
