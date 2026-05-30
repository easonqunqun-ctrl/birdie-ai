import { FC } from 'react'
import { Text, View } from '@tarojs/components'
import {
  formatMonthTitle,
  practiceCalendarWeekdayLabels,
  type PracticeCalendarGrid,
} from '@/utils/practiceCalendarLayout'
import './PracticeCalendar.scss'

export interface PracticeCalendarProps {
  grid: PracticeCalendarGrid
  onPrevMonth?: () => void
  onNextMonth?: () => void
  /** 是否允许切到下月（通常不允许超过当月） */
  canGoNext?: boolean
  /** 嵌入训练页白卡时去掉自身卡片底/阴影，避免双层嵌套 */
  embedded?: boolean
}

export const PracticeCalendar: FC<PracticeCalendarProps> = ({
  grid,
  onPrevMonth,
  onNextMonth,
  canGoNext = true,
  embedded = false,
}) => {
  const weekdays = practiceCalendarWeekdayLabels()

  return (
    <View
      className={`practice-calendar${embedded ? ' practice-calendar--embedded' : ''}`}
    >
      <View className='practice-calendar__header'>
        <Text
          className='practice-calendar__nav'
          onClick={onPrevMonth}
        >
          ‹
        </Text>
        <Text className='practice-calendar__title'>{formatMonthTitle(grid.monthKey)}</Text>
        <Text
          className={`practice-calendar__nav ${canGoNext ? '' : 'is-disabled'}`}
          onClick={canGoNext ? onNextMonth : undefined}
        >
          ›
        </Text>
      </View>
      <View className='practice-calendar__weekdays'>
        {weekdays.map((w) => (
          <Text key={w} className='practice-calendar__weekday'>
            {w}
          </Text>
        ))}
      </View>
      {grid.weeks.map((week, wi) => (
        <View key={wi} className='practice-calendar__row'>
          {week.map((cell, ci) => (
            <View
              key={`${wi}-${ci}`}
              className={[
                'practice-calendar__cell',
                cell.inMonth ? '' : 'practice-calendar__cell--pad',
                cell.isToday ? 'is-today' : '',
                cell.count > 0 ? 'has-practice' : '',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              {cell.inMonth ? (
                <>
                  <Text className='practice-calendar__day'>{cell.day}</Text>
                  {cell.count > 0 ? (
                    <Text className='practice-calendar__dot'>{cell.count > 1 ? cell.count : '·'}</Text>
                  ) : null}
                </>
              ) : null}
            </View>
          ))}
        </View>
      ))}
      <Text className='practice-calendar__footer'>
        本月打卡 {grid.monthTotal} 次
      </Text>
    </View>
  )
}

export default PracticeCalendar
