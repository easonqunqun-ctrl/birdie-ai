#!/usr/bin/env bash
# W10：幂等拉取 taro-native-shell（RN 0.70.x → 分支 0.70.0，见官方兼容表）。
# 用法：在 client/ 目录执行 bash scripts/bootstrap-rn-shell.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RN_SHELL="${CLIENT_DIR}/rn-shell"
REMOTE_URL="${RN_SHELL_REPO_URL:-https://github.com/NervJS/taro-native-shell.git}"
SHELL_BRANCH="${RN_SHELL_BRANCH:-0.70.0}"

warn() { printf '\033[33m[WARN]\033[0m %s\n' "$*" >&2; }

compare_rn_version() {
  export SHELL_PKG="$1"
  export CLIENT_PKG="$2"
  if ! command -v node >/dev/null 2>&1; then
    warn "node 不可用，跳过 react-native 版本比对"
    return 0
  fi
  node <<'NODE'
const fs = require('fs')
const shellPath = process.env.SHELL_PKG
const clientPath = process.env.CLIENT_PKG
const s = JSON.parse(fs.readFileSync(shellPath, 'utf8')).dependencies?.['react-native'] || ''
const c = JSON.parse(fs.readFileSync(clientPath, 'utf8')).dependencies?.['react-native'] || ''
const majMin = (v) => {
  const m = String(v).replace(/^[\^~=]/,'').match(/(\d+)\.(\d+)/)
  return m ? `${m[1]}.${m[2]}` : v
}
const ss = majMin(s)
const cc = majMin(c)
if (ss && cc && ss !== cc) {
  console.warn(`[WARN] rn-shell react-native (${s} → ${ss}) 与 client (${c} → ${cc}) 主次版本不一致，运行前请对齐（见 rn-shell/README.md）。`)
}
NODE
}

CLIENT_PKG_JSON="${CLIENT_DIR}/package.json"
SHELL_PKG_JSON="${RN_SHELL}/package.json"

if [[ -f "${SHELL_PKG_JSON}" ]]; then
  echo "✓ rn-shell 已存在（${RN_SHELL}），跳过克隆"
  compare_rn_version "${SHELL_PKG_JSON}" "${CLIENT_PKG_JSON}" || true
  exit 0
fi

# 仅占位 README（或空目录）时允许覆盖式克隆；否则拒绝以免误删
if [[ ! -d "${RN_SHELL}" ]]; then
  mkdir -p "${RN_SHELL}"
else
  if compgen -G "${RN_SHELL}/*" > /dev/null; then
    shopt -s nullglob dotglob
    entries=("${RN_SHELL}"/*)
    shopt -u dotglob
    non_readme=()
    for p in "${entries[@]+"${entries[@]}"}"; do
      base="$(basename "$p")"
      [[ "$base" == README.md ]] && continue
      non_readme+=("$p")
    done
    if ((${#non_readme[@]} > 0)); then
      echo "✗ ${RN_SHELL} 下已有除 README.md 之外的文件，请手动清理后再运行本脚本。"
      exit 1
    fi
  fi
  rm -f "${RN_SHELL}/README.md"
fi

TMP="$(mktemp -d)"
cleanup() { rm -rf "${TMP}"; }
trap cleanup EXIT

echo "=> 克隆 ${REMOTE_URL} 分支 ${SHELL_BRANCH}（浅克隆）…"
git clone --depth 1 --branch "${SHELL_BRANCH}" "${REMOTE_URL}" "${TMP}/checkout"
shopt -s dotglob nullglob
mv "${TMP}/checkout"/* "${RN_SHELL}/"
shopt -u dotglob nullglob

if [[ ! -f "${RN_SHELL}/package.json" ]]; then
  echo "✗ 克隆完成后仍未找到 rn-shell/package.json"
  exit 1
fi

echo "✓ rn-shell 已就绪：${RN_SHELL}"
compare_rn_version "${SHELL_PKG_JSON}" "${CLIENT_PKG_JSON}" || true
echo ""
echo "后续：cd rn-shell && 按 README 「Pods / 原生依赖」安装；业务侧执行 pnpm build:rn"
