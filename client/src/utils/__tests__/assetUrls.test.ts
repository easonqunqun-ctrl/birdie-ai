import { buildAssetImageUrl, buildAssetVideoUrl } from '@/utils/assetUrls'

describe('assetUrls', () => {
  it('buildAssetVideoUrl 拼接 API 同源视频代理路径', () => {
    expect(buildAssetVideoUrl('samples/swing_demo.mp4')).toBe(
      'http://localhost:8000/v1/assets/video/samples/swing_demo.mp4',
    )
  })

  it('buildAssetImageUrl 去掉 key 前导斜杠', () => {
    expect(buildAssetImageUrl('/samples/swing_demo_thumb.jpg')).toBe(
      'http://localhost:8000/v1/assets/image/samples/swing_demo_thumb.jpg',
    )
  })
})
