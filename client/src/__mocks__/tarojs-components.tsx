/**
 * @tarojs/components 测试 stub
 *
 * 把 Taro UI 原语 View / Text / Button / ScrollView 等映射成对应的 HTML 标签，
 * 让 React Testing Library 能在 jsdom 里渲染、query 与点击。
 *
 * 设计原则：
 *  - 仅做语义映射；不复现 Taro 的小程序事件模型（如 onTap → bindtap）。
 *    业务代码里的 onClick 在 jsdom 下能正常触发；onTap 等不映射。
 *  - 保留 children 与 className，让 RTL 的 getByText / getByRole 可用。
 */
import * as React from 'react'

type Props = React.PropsWithChildren<Record<string, any>>

const make = (tag: keyof JSX.IntrinsicElements) =>
  React.forwardRef<HTMLElement, Props>(function TaroComp(props, ref) {
    const { children, className, style, ...rest } = props
    // Taro 习惯写 catchMove / catchTouchMove；为避免被 React 当成未知 DOM 属性报错，过滤掉
    const safeRest: Record<string, unknown> = {}
    for (const k of Object.keys(rest)) {
      if (/^(catch|bind)[A-Z]/.test(k)) continue
      if (k === 'hoverClass' || k === 'hoverStartTime' || k === 'hoverStayTime') continue
      safeRest[k] = (rest as Record<string, unknown>)[k]
    }
    return React.createElement(
      tag as string,
      { className, style, ref, ...safeRest } as any,
      children,
    )
  })

export const View = make('div')
export const Text = make('span')
export const Block = make('div')
export const ScrollView = make('div')
export const Swiper = make('div')
export const SwiperItem = make('div')
export const Image = make('img')
export const Button = make('button')
export const Input = make('input')
export const Textarea = make('textarea')
export const Video = make('video')
export const Form = make('form')
export const Label = make('label')
export const Icon = make('i')
export const Picker = make('div')
export const Slider = make('input')
export const Switch = make('input')
export const Canvas = make('canvas')
export const CoverView = make('div')
export const CoverImage = make('img')
export const Progress = make('progress')
export const RichText = make('div')
export const Map = make('div')

export default {
  View,
  Text,
  Block,
  ScrollView,
  Swiper,
  SwiperItem,
  Image,
  Button,
  Input,
  Textarea,
  Video,
  Form,
  Label,
  Icon,
  Picker,
  Slider,
  Switch,
  Canvas,
  CoverView,
  CoverImage,
  Progress,
  RichText,
  Map,
}
