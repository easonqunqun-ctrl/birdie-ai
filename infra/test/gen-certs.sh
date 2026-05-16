#!/usr/bin/env bash
# =====================================================
# W8-T4：测试环境自签 HTTPS 证书生成脚本
# =====================================================
# 输出：
#   infra/test/certs/server.crt   （自签 X.509 证书）
#   infra/test/certs/server.key   （RSA 2048 私钥）
#
# 用法（在 CVM 上首次部署前执行）：
#   bash infra/test/gen-certs.sh <test-host>
# 示例：
#   bash infra/test/gen-certs.sh test.birdieai.example.com
#   bash infra/test/gen-certs.sh 123.45.67.89   # 直接 IP 也行
#
# 设计取舍：
#   - 自签证书有效期 365 天；W9 上正式 LET'S ENCRYPT 后替换
#   - SAN 字段同时支持 DNS:$HOST 和 IP:$HOST，方便用 IP 直连
#   - 微信开发者工具需勾选「不校验合法域名/HTTPS 证书」才能预览
#     （详见 docs/release-notes/W8-test-env-runbook.md）
# =====================================================
set -euo pipefail

HOST="${1:-}"
if [[ -z "$HOST" ]]; then
    echo "用法：$0 <test-host>" >&2
    echo "  示例：$0 test.birdieai.example.com" >&2
    echo "  示例：$0 123.45.67.89" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="$SCRIPT_DIR/certs"
mkdir -p "$CERTS_DIR"

# 判断 HOST 是 IP 还是域名（极简：纯数字 + 点 = IP）
if [[ "$HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    SAN="IP:$HOST"
else
    SAN="DNS:$HOST"
fi

CONF="$(mktemp)"
trap 'rm -f "$CONF"' EXIT

cat > "$CONF" <<EOF
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
req_extensions     = req_ext

[dn]
C  = CN
ST = Beijing
L  = Beijing
O  = Xiaoniao AI (Test)
CN = $HOST

[req_ext]
subjectAltName = $SAN
EOF

openssl req \
    -x509 \
    -newkey rsa:2048 \
    -nodes \
    -days 365 \
    -keyout "$CERTS_DIR/server.key" \
    -out    "$CERTS_DIR/server.crt" \
    -config "$CONF" \
    -extensions req_ext

chmod 600 "$CERTS_DIR/server.key"
chmod 644 "$CERTS_DIR/server.crt"

# nginx 配置固定读 fullchain.pem / privkey.pem（LE 与自签共用文件名）
cp -f "$CERTS_DIR/server.crt" "$CERTS_DIR/fullchain.pem"
cp -f "$CERTS_DIR/server.key" "$CERTS_DIR/privkey.pem"
chmod 644 "$CERTS_DIR/fullchain.pem"
chmod 600 "$CERTS_DIR/privkey.pem"

echo ""
echo "✓ 自签证书已生成："
echo "  - $CERTS_DIR/server.crt"
echo "  - $CERTS_DIR/server.key"
echo "  - $CERTS_DIR/fullchain.pem  （nginx TLS）"
echo "  - $CERTS_DIR/privkey.pem    （nginx TLS）"
echo ""
echo "下一步："
echo "  1. 把 server.crt 拷到客户端机器（开发者工具勾"不校验合法域名"也能跳过）"
echo "  2. make deploy-test  起栈"
echo "  3. curl -k https://$HOST/v1/health  自检"
