#!/usr/bin/env bash
# 在任意联网机器上对「小程序 request 域名」做 TLS / 业务探测（不涉及微信公众平台登录）。
#
# 用法（仓库根目录）：
#   bash infra/deploy/verify-weapp-https-readiness.sh api.example.com
#   DOMAIN=api.example.com make verify-weapp-https
#
# 环境变量：
#   STRICT_HEALTH=1  — 若 https://域名/v1/health 非 2xx 则整体失败（默认仅告警）
#
set -euo pipefail

_health=""
trap '[ -n "${_health}" ] && rm -f "${_health}"' EXIT

RAW="${1:-${DOMAIN:-}}"
if [[ -z "${RAW}" ]]; then
  echo "用法：bash $0 <域名>" >&2
  echo "  例：bash $0 api.example.com" >&2
  echo "或：DOMAIN=api.example.com make verify-weapp-https" >&2
  exit 1
fi

DOMAIN="${RAW#https://}"
DOMAIN="${DOMAIN%%/*}"
DOMAIN="${DOMAIN%%:*}"

fail() {
  echo "✗ $*" >&2
  exit 1
}

warn() {
  echo "⚠ $*" >&2
}

ok() {
  echo "✓ $*"
}

echo "── 域名（规范化）: ${DOMAIN}"
echo ""

echo "── DNS（A 记录）"
if command -v dig >/dev/null 2>&1; then
  ips=$(dig +short A "${DOMAIN}" | grep -E '^[0-9.]+$' || true)
  ips=$(echo "${ips}" | tr '\n' ' ' | sed 's/[[:space:]]*$//')
  if [[ -z "${ips}" ]]; then
    warn "未解析到 IPv4 A 记录（DNS 延迟或未指向服务器）；跳过"
  else
    ok "${ips}"
  fi
else
  warn "未找到 dig，跳过 DNS"
fi
echo ""

echo "── TLS（443，校验证书链；须系统信任）"
PEM=$(echo | openssl s_client -connect "${DOMAIN}:443" -servername "${DOMAIN}" 2>/dev/null | openssl x509 2>/dev/null) \
  || fail "无法建立 TLS 或未取得证书（检查 443 / 防火墙 / 域名是否指向本服务）"

issuer=$(echo "${PEM}" | openssl x509 -noout -issuer 2>/dev/null || true)
subject=$(echo "${PEM}" | openssl x509 -noout -subject 2>/dev/null || true)
echo "    ${issuer}"
echo "    ${subject}"
dates=$(echo "${PEM}" | openssl x509 -noout -dates 2>/dev/null || true)
echo "    ${dates}"

if [[ -z "${issuer}" || -z "${subject}" ]]; then
  fail "openssl 解析 issuer/subject 失败"
fi

# openssl 输出分别为 issuer=… / subject=…，须去掉前缀再比 DN（否则自签永远判不出来）
issuer_dn="${issuer#issuer=}"
subject_dn="${subject#subject=}"
if [[ "${issuer_dn}" == "${subject_dn}" ]]; then
  fail "issuer 与 subject 的 DN 相同 → 多为自签证书；微信小程序真机常见 errcode:-207，请换 Let's Encrypt 等公信 CA（见 infra/deploy/README.md）"
fi

if [[ "${issuer}" == *"Let's Encrypt"* ]] || [[ "${issuer}" == *"R3"* ]]; then
  ok "issuer 含 Let's Encrypt / R3（典型 LE 链路）"
else
  warn "issuer 未见 Let's Encrypt；若为腾讯云 SSL / DigiCert / GlobalSign 等公信 CA，仍可被小程序信任，请以真机实测为准"
fi
echo ""

echo "── HTTPS 业务探测: GET https://${DOMAIN}/v1/health"
_health=$(mktemp /tmp/xiaoniao-health.XXXXXX)
set +e
code=$(curl -sS -o "${_health}" -w "%{http_code}" --max-time 20 "https://${DOMAIN}/v1/health")
curl_ec=$?
set -e
if [[ "${curl_ec}" -ne 0 ]]; then
  warn "curl 失败 (exit ${curl_ec})；后端未就绪或路径不同"
  if [[ "${STRICT_HEALTH:-}" == "1" ]]; then
    fail "STRICT_HEALTH=1：健康检查失败"
  fi
elif [[ "${code}" =~ ^2 ]]; then
  ok "HTTP ${code}"
  head -c 240 "${_health}" | tr -d '\r' | sed 's/^/    /' || true
  echo ""
else
  warn "HTTP ${code}（期望 2xx）；确认 nginx → backend 已启且路由为 /v1/health"
  if [[ "${STRICT_HEALTH:-}" == "1" ]]; then
    fail "STRICT_HEALTH=1：健康检查非 2xx"
  fi
fi
echo ""

echo "── HTTP ACME 预留（80 → /.well-known/acme-challenge/）"
set +e
ac=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 15 "http://${DOMAIN}/.well-known/acme-challenge/" 2>/dev/null)
set -e
if [[ "${ac}" =~ ^[23] ]] || [[ "${ac}" == "403" ]] || [[ "${ac}" == "404" ]]; then
  ok "HTTP ${ac}（nginx 能对 challenge 路径响应即可；404/403 在无 token 文件时常见）"
else
  warn "HTTP ${ac:-000} — 申请 Let's Encrypt 前须保证公网 80 可达且 location /.well-known/ 已配置（见 infra/test/nginx.conf）"
fi

echo ""
echo "✓ TLS 自检通过。微信公众平台「服务器域名」须在后台手动保存（我无法代登录）；格式示例 request：https://${DOMAIN}"
