/**
 * 分享海报页（Q-C1 / Batch-C-1）
 *
 * 流程：
 *  1. 拉取自己的完整报告 + 调用 `POST /analyses/{id}/share-card` 获取小程序码 URL
 *  2. 在离屏 `<Canvas type='2d'>` 上合成 750×1334 海报
 *  3. 通过 `Taro.canvasToTempFilePath` 落地为本地 PNG，绑到 `<Image>` 预览
 *  4. 三个 action：保存到相册 / 转发给好友 / 重新生成
 *
 * 注意事项（与文档同步）：
 *  - 必须登录态进入；公开（脱敏）报告无 phase_scores，不在此页绘海报
 *  - 小程序 Canvas 新版（type=2d）必须用 selectorQuery + node 引用
 *  - 保存到相册需要 scope.writePhotosAlbum，已在 app.config.ts permission 声明
 *  - 网络图 → 必须先 getImageInfo 拿本地 path 再 createImage.src，否则真机渲染失败
 */

import { FC, useCallback, useEffect, useRef, useState } from 'react'
import { Button, Canvas, Image, Text, View } from '@tarojs/components'
import Taro, { useReady, useRouter, useShareAppMessage } from '@tarojs/taro'
import { analysisService } from '@/services/analysisService'
import { shareService } from '@/services/shareService'
import { describePageLoadFailure } from '@/services/request'
import { useUserStore } from '@/store/userStore'
import { PHASE_LABEL, PHASE_ORDER } from '@/constants/phaseLabels'
import { CAMERA_ANGLE_LABEL, CLUB_TYPE_LABEL } from '@/types/analysis'
import type { AnalysisReportResponse } from '@/types/analysis'
import type { CameraAngle, ClubType } from '@/types/api'
import { POSTER_HEIGHT, POSTER_WIDTH } from '@/utils/posterLayout'
import { drawPoster, type PosterCanvasContext } from '@/utils/posterCanvas'
import './poster.scss'

const CANVAS_ID = 'poster-canvas'

interface CanvasNodeLike {
  width: number
  height: number
  getContext: (type: '2d') => PosterCanvasContext & { scale: (x: number, y: number) => void }
  createImage: () => {
    src: string
    width?: number
    height?: number
    onload: (() => void) | null
    onerror: ((e: unknown) => void) | null
  }
}

function resolveCanvasNode(): Promise<CanvasNodeLike> {
  return new Promise((resolve, reject) => {
    const query = Taro.createSelectorQuery()
    query
      .select(`#${CANVAS_ID}`)
      .fields({ node: true, size: true })
      .exec((res) => {
        const node = res?.[0]?.node as CanvasNodeLike | undefined
        if (!node) {
          reject(new Error('canvas_node_not_ready'))
          return
        }
        resolve(node)
      })
  })
}

function resolvePosterImageUrl(url: string): string {
  if (!url) return url
  const matched = url.match(/^(https?:\/\/[^/]+)\/minio\/[^/]+\/(share\/wxa\/[^?#]+)/i)
  if (matched) {
    return `${matched[1]}/v1/assets/image/${matched[2]}`
  }
  return url
}

function readCanvasPixelRatio(): number {
  try {
    const info = Taro.getWindowInfo?.()
    if (info?.pixelRatio) {
      return Math.max(1, Math.min(3, info.pixelRatio))
    }
  } catch {
    /* noop */
  }
  return 2
}

async function loadImageToCanvas(
  canvas: CanvasNodeLike,
  remoteUrl: string,
): Promise<unknown> {
  if (!remoteUrl) return null

  const normalizedUrl = resolvePosterImageUrl(remoteUrl)
  let localPath = normalizedUrl
  if (/^https?:\/\//i.test(normalizedUrl)) {
    try {
      const dl = await Taro.downloadFile({ url: normalizedUrl })
      if (dl.statusCode === 200 && dl.tempFilePath) {
        localPath = dl.tempFilePath
      }
    } catch {
      /* 回退 getImageInfo 直链 */
    }
  }

  try {
    const info = await Taro.getImageInfo({ src: localPath })
    return await new Promise((resolve) => {
      const img = canvas.createImage()
      img.onload = () => {
        if (!img.width && info.width > 0) img.width = info.width
        if (!img.height && info.height > 0) img.height = info.height
        resolve(img)
      }
      img.onerror = () => resolve(null)
      img.src = info.path
    })
  } catch {
    return null
  }
}

async function ensurePhotoAuth(): Promise<void> {
  const setting = await Taro.getSetting()
  const scope = setting.authSetting['scope.writePhotosAlbum']
  if (scope === true) return
  if (scope === false) {
    // 之前明确拒绝过；只能引导去系统设置
    const modal = await Taro.showModal({
      title: '需要相册权限',
      content: '保存海报到相册需要您授权，点击「去设置」开启',
      confirmText: '去设置',
      cancelText: '取消',
    })
    if (!modal.confirm) throw new Error('user_canceled')
    const opened = await Taro.openSetting()
    if (!opened.authSetting['scope.writePhotosAlbum']) throw new Error('user_denied')
    return
  }
  // 首次：直接 authorize；用户点拒绝会抛错
  await Taro.authorize({ scope: 'scope.writePhotosAlbum' })
}

const PosterPage: FC = () => {
  const router = useRouter()
  const params = router.params as { id?: string }
  const analysisId = (params.id || '').trim()
  const currentUserToken = useUserStore((s) => s.token)

  const [report, setReport] = useState<AnalysisReportResponse | null>(null)
  const [wxaCodeUrl, setWxaCodeUrl] = useState<string>('')
  const [wxaFetchSettled, setWxaFetchSettled] = useState(false)
  const [posterTempPath, setPosterTempPath] = useState<string>('')
  const [drawing, setDrawing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const readyRef = useRef(false)

  useReady(() => {
    readyRef.current = true
  })

  useEffect(() => {
    if (!currentUserToken) {
      Taro.showToast({ title: '请先登录后再生成海报', icon: 'none' })
      setTimeout(() => Taro.navigateBack().catch(() => undefined), 700)
      return
    }
    if (!analysisId) {
      setError('缺少分析 ID')
      return
    }
    analysisService
      .getReport(analysisId)
      .then((r) => setReport(r))
      .catch((e: unknown) => setError(describePageLoadFailure(e)))
    analysisService
      .createShareCard(analysisId)
      .then((r) => setWxaCodeUrl(r.wxa_code_url || ''))
      .catch(() => setWxaCodeUrl(''))
      .finally(() => setWxaFetchSettled(true))
  }, [analysisId, currentUserToken])

  const generatePoster = useCallback(async () => {
    if (!report) return
    if (drawing) return
    setDrawing(true)
    setError(null)
    try {
      // useReady 还没回调时 selector 拿不到 node；等一下
      if (!readyRef.current) {
        await new Promise<void>((resolve) => setTimeout(resolve, 120))
      }
      const canvas = await resolveCanvasNode()
      const ctx = canvas.getContext('2d')
      const dpr = readCanvasPixelRatio()
      canvas.width = POSTER_WIDTH * dpr
      canvas.height = POSTER_HEIGHT * dpr
      ctx.scale(dpr, dpr)

      const wxaImage = await loadImageToCanvas(canvas, wxaCodeUrl)

      const phaseScores = PHASE_ORDER.map((k) => report.phase_scores?.[k]?.score ?? 0)
      const phaseLabels = PHASE_ORDER.map((k) => PHASE_LABEL[k])
      const topIssues = (report.issues || []).slice(0, 3).map((i) => i.name)

      drawPoster(
        ctx,
        {
          overallScore: report.overall_score ?? null,
          scoreLevel: report.score_level ?? null,
          phaseScores,
          phaseLabels,
          clubLabel:
            CLUB_TYPE_LABEL[report.club_type as ClubType] || '挥杆',
          cameraAngleLabel:
            CAMERA_ANGLE_LABEL[report.camera_angle as CameraAngle] || '',
          thumbnailUrl: report.thumbnail_url || null,
          wxaCodeUrl: wxaCodeUrl || null,
          topIssues,
        },
        { wxaCodeImage: wxaImage, thumbnailImage: null },
      )

      await new Promise<void>((resolve) => setTimeout(resolve, 60))

      const file = await new Promise<{ tempFilePath: string }>((resolve, reject) => {
        Taro.canvasToTempFilePath({
          canvas: canvas as unknown as Taro.canvasToTempFilePath.Option['canvas'],
          fileType: 'png',
          success: (res) => resolve(res),
          fail: (err) => reject(err),
        })
      })
      setPosterTempPath(file.tempFilePath)

      shareService
        .logShare({ share_type: 'invite_poster', target_id: analysisId })
        .catch(() => undefined)
    } catch (e) {
      const code = (e as { errMsg?: string } | null)?.errMsg
      setError(code ? `海报生成失败：${code}` : '海报生成失败，请重试')
    } finally {
      setDrawing(false)
    }
  }, [analysisId, drawing, report, wxaCodeUrl])

  useEffect(() => {
    if (report && wxaFetchSettled) {
      generatePoster()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report, wxaFetchSettled, wxaCodeUrl])

  const handleSave = async () => {
    if (!posterTempPath || saving) return
    setSaving(true)
    try {
      await ensurePhotoAuth()
      await Taro.saveImageToPhotosAlbum({ filePath: posterTempPath })
      Taro.showToast({ title: '已保存到相册', icon: 'success' })
    } catch (e) {
      const msg = (e as { errMsg?: string } | null)?.errMsg || ''
      if (msg.includes('cancel') || msg.includes('user_canceled')) {
        Taro.showToast({ title: '已取消', icon: 'none' })
      } else {
        Taro.showToast({ title: '保存失败，请稍后重试', icon: 'none' })
      }
    } finally {
      setSaving(false)
    }
  }

  const handleShareClick = () => {
    if (!analysisId || !posterTempPath) return
    shareService
      .logShare({ share_type: 'invite_poster', target_id: analysisId })
      .catch(() => undefined)
  }

  useShareAppMessage(() => {
    const score = report?.overall_score
    const clubLabel = report
      ? CLUB_TYPE_LABEL[report.club_type as ClubType] || '挥杆'
      : '挥杆'
    const title = score
      ? `我的${clubLabel}挥杆打了 ${score} 分，你来挑战一下？`
      : '我用领翼golf分析了挥杆，你来看看'
    return {
      title,
      path: `/pages/analysis/report?id=${analysisId}&from_share=1`,
      imageUrl: posterTempPath || report?.thumbnail_url || '',
    }
  })

  return (
    <View className='poster'>
      <View className='poster__hero'>
        <Text className='poster__hero-title'>分享你的挥杆报告</Text>
        <View className='poster__hero-sub'>
          <Text>保存海报到相册，发朋友圈，邀请球友一起练</Text>
        </View>
      </View>

      <View className='poster__preview'>
        {posterTempPath ? (
          <Image
            className='poster__preview-image'
            src={posterTempPath}
            mode='aspectFit'
            showMenuByLongpress
          />
        ) : (
          <View className='poster__preview-empty'>
            <Text>{drawing ? '正在生成海报…' : '正在准备数据…'}</Text>
          </View>
        )}
        {drawing && (
          <View className='poster__loading'>
            <Text className='poster__loading-text'>正在合成海报…</Text>
          </View>
        )}
      </View>

      {error && (
        <View className='poster__error'>
          <Text>{error}</Text>
        </View>
      )}

      <View className='poster__tip'>
        <Text>保存或转发海报，邀请球友扫码查看完整挥杆报告。</Text>
      </View>

      <View className='poster__actions'>
        <Button
          className='poster__btn poster__btn--gold'
          onClick={handleSave}
          disabled={!posterTempPath || saving}
          loading={saving}
        >
          保存到相册
        </Button>
        <Button
          className='poster__btn poster__btn--primary'
          openType='share'
          disabled={!posterTempPath}
          onClick={handleShareClick}
        >
          转发给微信好友
        </Button>
        <Button
          className='poster__btn poster__btn--ghost'
          onClick={generatePoster}
          disabled={drawing || !report}
        >
          重新生成
        </Button>
      </View>

      <Canvas
        id={CANVAS_ID}
        canvasId={CANVAS_ID}
        type='2d'
        className='poster__canvas'
      />
    </View>
  )
}

export default PosterPage
