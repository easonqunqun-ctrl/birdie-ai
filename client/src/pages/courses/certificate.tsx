/**
 * M11-05 · 阶段通关证书页：Canvas 合成 + 保存相册。
 */

import { FC, useCallback, useEffect, useRef, useState } from 'react'
import { Button, Canvas, Image, Text, View } from '@tarojs/components'
import Taro, { useReady, useRouter } from '@tarojs/taro'
import { PHASE2_COURSES_ENABLED_FLAG } from '@/constants/flags'
import {
  coursesService,
  type CertificateDetail,
} from '@/services/coursesService'
import {
  CERT_HEIGHT,
  CERT_WIDTH,
  drawStageCertificate,
  type CertificateCanvasContext,
} from '@/utils/certificateCanvas'
import { formatCertificateIssuedAt } from '@/utils/certificateLayout'
import './certificate.scss'

const CANVAS_ID = 'stage-cert-canvas'

interface CanvasNodeLike {
  width: number
  height: number
  getContext: (type: '2d') => CertificateCanvasContext & {
    scale: (x: number, y: number) => void
  }
}

function resolveCanvasNode(): Promise<CanvasNodeLike> {
  return new Promise((resolve, reject) => {
    Taro.createSelectorQuery()
      .select(`#${CANVAS_ID}`)
      .fields({ node: true, size: true })
      .exec((res) => {
        const node = res?.[0]?.node as CanvasNodeLike | undefined
        if (!node) {
          reject(new Error('canvas_not_ready'))
          return
        }
        resolve(node)
      })
  })
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

const CertificatePage: FC = () => {
  const router = useRouter()
  const certId = router.params.id ?? ''
  const [loading, setLoading] = useState(true)
  const [cert, setCert] = useState<CertificateDetail | null>(null)
  const [previewPath, setPreviewPath] = useState('')
  const [rendering, setRendering] = useState(false)
  const readyRef = useRef(false)

  useReady(() => {
    readyRef.current = true
  })

  const renderCertificate = useCallback(async (detail: CertificateDetail) => {
    setRendering(true)
    try {
      if (!readyRef.current) {
        await new Promise<void>((resolve) => setTimeout(resolve, 120))
      }
      const node = await resolveCanvasNode()
      const dpr = readCanvasPixelRatio()
      node.width = CERT_WIDTH * dpr
      node.height = CERT_HEIGHT * dpr
      const ctx = node.getContext('2d')
      ctx.scale(dpr, dpr)
      drawStageCertificate(ctx, {
        holderName: detail.holder_name,
        courseTitle: detail.course_title,
        stage: detail.stage,
        stageTitle: detail.stage_title,
        badgeLabel: detail.badge_label,
        issuedAtLabel: formatCertificateIssuedAt(detail.issued_at),
      })
      const out = await Taro.canvasToTempFilePath({
        canvas: node as unknown as Taro.Canvas,
        width: CERT_WIDTH * dpr,
        height: CERT_HEIGHT * dpr,
        destWidth: CERT_WIDTH * dpr,
        destHeight: CERT_HEIGHT * dpr,
      })
      setPreviewPath(out.tempFilePath)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '证书生成失败'
      Taro.showToast({ title: msg, icon: 'none' })
    } finally {
      setRendering(false)
    }
  }, [])

  useEffect(() => {
    if (!PHASE2_COURSES_ENABLED_FLAG) return
    if (!certId) {
      setLoading(false)
      return
    }
    void (async () => {
      try {
        const detail = await coursesService.certificateDetail(certId)
        setCert(detail)
      } catch (e) {
        const msg = e instanceof Error ? e.message : '加载失败'
        Taro.showToast({ title: msg, icon: 'none' })
      } finally {
        setLoading(false)
      }
    })()
  }, [certId])

  useEffect(() => {
    if (!cert) return
    void renderCertificate(cert)
  }, [cert, renderCertificate])

  const saveToAlbum = async () => {
    if (!previewPath) return
    try {
      await Taro.saveImageToPhotosAlbum({ filePath: previewPath })
      Taro.showToast({ title: '已保存到相册', icon: 'success' })
    } catch {
      Taro.showToast({ title: '保存失败，请检查相册权限', icon: 'none' })
    }
  }

  if (!PHASE2_COURSES_ENABLED_FLAG) {
    return (
      <View className='certificate'>
        <Text className='certificate__loading'>功能尚未开放</Text>
      </View>
    )
  }

  if (loading || !cert) {
    return (
      <View className='certificate'>
        <Text className='certificate__loading'>{loading ? '加载中…' : '证书不存在'}</Text>
      </View>
    )
  }

  return (
    <View className='certificate'>
      <View className='certificate__hero'>
        <Text className='certificate__hero-title'>{cert.badge_label}</Text>
        <Text className='certificate__hero-sub'>{cert.stage_title}</Text>
      </View>

      <View className='certificate__preview'>
        {previewPath ? (
          <Image className='certificate__preview-image' src={previewPath} mode='aspectFit' />
        ) : (
          <Text className='certificate__loading'>{rendering ? '生成证书…' : '准备中…'}</Text>
        )}
        <Canvas
          type='2d'
          id={CANVAS_ID}
          className='certificate__canvas-hidden'
          style={{ width: `${CERT_WIDTH}px`, height: `${CERT_HEIGHT}px`, position: 'fixed', left: '-9999px' }}
        />
      </View>

      <View className='certificate__actions'>
        <Button className='certificate__btn' onClick={() => void saveToAlbum()}>
          保存到相册
        </Button>
        <Button
          className='certificate__btn certificate__btn--ghost'
          onClick={() => Taro.navigateBack({ delta: 1 })}
        >
          返回
        </Button>
      </View>
    </View>
  )
}

export default CertificatePage
