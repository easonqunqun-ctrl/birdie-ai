/**
 * 跨端 KV：小程序用 Taro sync API。
 * 业务层（utils/storage 等）只调本适配器，勿直接 Taro.getStorageSync。
 * （原 RN AsyncStorage 分支已移除，App 端改用独立 Flutter 工程。）
 */
import Taro from '@tarojs/taro'

type JsonValue = unknown

/** 兼容历史调用点：小程序 sync API 立即可用，无需 hydrate。 */
export async function hydrateKvStorage(): Promise<void> {
  // no-op
}

export function isKvStorageReady(): boolean {
  return true
}

export function setStorageSync(key: string, data: JsonValue): void {
  Taro.setStorageSync(key, data)
}

export function getStorageSync(key: string): JsonValue {
  return Taro.getStorageSync(key)
}

export function removeStorageSync(key: string): void {
  Taro.removeStorageSync(key)
}

export function clearStorageSync(): void {
  Taro.clearStorageSync()
}
