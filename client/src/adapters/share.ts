/**
 * 微信分享钩子跨端适配。
 * `useShareAppMessage` / `useShareTimeline` 仅小程序存在；RN / H5 为 no-op。
 * `TARO_ENV` 为编译期常量，各端产物只会保留对应分支（满足 hooks 规则）。
 */
import {
  useShareAppMessage as taroUseShareAppMessage,
  useShareTimeline as taroUseShareTimeline,
} from '@tarojs/taro'

type ShareAppMessageResult = {
  title?: string
  path?: string
  imageUrl?: string
  [key: string]: unknown
}

type ShareTimelineResult = {
  title?: string
  query?: string
  imageUrl?: string
  [key: string]: unknown
}

function useShareAppMessageNoop(_factory: () => ShareAppMessageResult): void {}
function useShareTimelineNoop(_factory: () => ShareTimelineResult): void {}

export const useShareAppMessage =
  process.env.TARO_ENV === 'weapp' ? taroUseShareAppMessage : useShareAppMessageNoop

export const useShareTimeline =
  process.env.TARO_ENV === 'weapp' ? taroUseShareTimeline : useShareTimelineNoop
