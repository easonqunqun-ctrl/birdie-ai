/**
 * 品牌图（源文件在仓库 `UI/LOGO.png`，同步至 `src/assets/brand/logo.png`）
 * 备选图 `UI/LOGO1.png` → `assets/brand/logo-alt.png`，需用时再 `import` 以免打入主包。
 */
import logoUrl from '@/assets/brand/logo.png'
import logoAltUrl from '@/assets/brand/logo-alt.png'

/** 主 LOGO（浅色底、通用） */
export const BRAND_LOGO = logoUrl

/**
 * P2-B2：分享卡片兜底图。
 *
 * 微信小程序 `useShareAppMessage.imageUrl` / `useShareTimeline.imageUrl`：
 *   - 留空 → 用页面截屏（不可控、可能含敏感内容如邀请码）
 *   - 给本地路径 → 稳定可控
 *   - 推荐尺寸 5:4（500×400）；目前用 1024×1024 logo-alt 兜底，被微信
 *     居中裁剪后可接受
 *
 * TODO（W9 视觉收尾）：让设计师出一张 5:4 品牌分享卡片
 *   （建议元素：品牌主色渐变底 + LOGO + slogan「AI 看挥杆，发现进步空间」），
 *   出图后替换本常量即可。
 */
export const BRAND_SHARE_COVER = logoAltUrl
