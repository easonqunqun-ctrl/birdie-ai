#!/usr/bin/env bash
# W10：比对 client/package.json 中与壳工程常见的原生 SDK，给出在 rn-shell 下执行的 add 示例。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SHELL_PKG="${CLIENT_DIR}/rn-shell/package.json"
CLIENT_PKG="${CLIENT_DIR}/package.json"

if [[ ! -f "${SHELL_PKG}" ]]; then
  echo "未找到 rn-shell/package.json — 请先 pnpm setup:rn-shell（或 bash scripts/bootstrap-rn-shell.sh）"
  exit 1
fi

CLIENT_PKG="${CLIENT_PKG}" SHELL_PKG_JSON="${SHELL_PKG}" node <<'NODE'
const fs = require('fs')
const clientPath = process.env.CLIENT_PKG
const shellPath = process.env.SHELL_PKG_JSON
const deps = JSON.parse(fs.readFileSync(clientPath, 'utf8')).dependencies || {}
const shell = JSON.parse(fs.readFileSync(shellPath, 'utf8'))
const shellDeps = { ...shell.dependencies, ...shell.devDependencies }
const want = [
  'react-native-wechat-lib',
  'react-native-image-picker',
  'react-native-gesture-handler',
  '@react-native-picker/picker',
]
const pairs = []
const missingVers = []
for (const k of want) {
  if (!deps[k]) continue
  pairs.push(`${k}@${deps[k]}`)
  if (!shellDeps[k]) missingVers.push(`${k}: 壳未声明`)
  else if (String(shellDeps[k]) !== String(deps[k]))
    missingVers.push(`${k}: 壳=${shellDeps[k]} 业务=${deps[k]}`)
}
if (pairs.length === 0) {
  console.log('业务 package.json 中未包含上述对齐键，跳过。')
  process.exit(0)
}
console.log('=== rn-shell 建议对齐的原生依赖（与上层 client/package.json 一致）===\n')
console.log('cd client/rn-shell && yarn add ' + pairs.join(' '))
console.log('# 或: pnpm add ' + pairs.join(' '))
if (missingVers.length)
  console.log('\n[MISMATCH或未安装]\n' + missingVers.map((x) => ' - ' + x).join('\n'))
console.log('\niOS Pods: cd client/rn-shell/ios && bundle install && bundle exec pod install')
NODE
