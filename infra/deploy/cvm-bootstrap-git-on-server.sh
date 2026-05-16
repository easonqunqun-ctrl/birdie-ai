#!/usr/bin/env bash
# 在 CVM 上执行：把「散装 / rsync 树」迁入「正式 git clone」目录，沿用原 $DEPLOY_REPO 路径，
# 以便后续本机只须 git push → make release-cvm。
#
# 使用前：
#   - 你已在本机建好远端仓库（GitHub / GitLab / 腾讯云工蜂等），且 CVM 能 clone（HTTPS 可用 token；
#     或 SSH deploy key）。
#   - 当前云上代码在 $DEPLOY_REPO（默认 ~/lingniao-golf）。
#
# 用法（在云服务器 ubuntu shell，仓库尚未 clone 时使用本脚本自带的副本；第一次若目录里还没有此脚本，
#       可先本机：scp infra/deploy/cvm-bootstrap-git-on-server.sh ubuntu@CVM:~ && bash ~/cvm-bootstrap-git-on-server.sh）：
#
#   export GIT_REPO_URL='https://github.com/ORG/lingniao-golf.git'
#   # 或 SSH：export GIT_REPO_URL='git@github.com:ORG/lingniao-golf.git'
#   export GIT_BRANCH="${GIT_BRANCH:-main}"
#   bash infra/deploy/cvm-bootstrap-git-on-server.sh
#
# 可选环境变量：
#   DEPLOY_REPO     默认 $HOME/lingniao-golf
#   GIT_REPO_URL    必填，远端 clone 地址
#   GIT_SSH_COMMAND  非必填；若不设且存在 $HOME/.ssh/id_ed25519_lingniao_git_read，
#                     会自动用于 clone（云上「只读 Deploy key」）。
#   LINGNIAO_CLONE_KEY 覆盖上述私钥路径
#
# 成功后：备份目录形如 ${DEPLOY_REPO}.bak.<时间戳>；随后在 Mac 正常 push，再 make release-cvm。
set -euo pipefail

DEPLOY_REPO="${DEPLOY_REPO:-$HOME/lingniao-golf}"
DEPLOY_REPO="${DEPLOY_REPO/#\~/$HOME}"
GIT_BRANCH="${GIT_BRANCH:-main}"
GIT_REPO_URL="${GIT_REPO_URL:-}"

die() {
  echo "✗ $*" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || die "未安装 git，请先 sudo apt install -y git"

[[ -n "$GIT_REPO_URL" ]] || die "请导出 GIT_REPO_URL=… 再执行"

LINGNIAO_CLONE_KEY="${LINGNIAO_CLONE_KEY:-$HOME/.ssh/id_ed25519_lingniao_git_read}"
if [[ -z "${GIT_SSH_COMMAND:-}" ]] && [[ -f "$LINGNIAO_CLONE_KEY" ]]; then
  export GIT_SSH_COMMAND="ssh -i ${LINGNIAO_CLONE_KEY} -o IdentitiesOnly=yes"
fi

REMOTE_HEAD=""
REMOTE_HEAD="$(git ls-remote "$GIT_REPO_URL" "refs/heads/${GIT_BRANCH}" 2>/dev/null || true)"
[[ -n "$REMOTE_HEAD" ]] || die "远端暂无分支 refs/heads/${GIT_BRANCH}。请先在 Mac 执行：git push -u origin ${GIT_BRANCH}"

if [[ -d "${DEPLOY_REPO}/.git" ]]; then
  echo "✓ ${DEPLOY_REPO} 已是 git 克隆（存在 .git），无需重复 bootstrap。"
  cd "$DEPLOY_REPO" && git remote -v && git status -sb
  exit 0
fi

TS="$(date +%Y%m%d%H%M%S)"
BACKUP="${DEPLOY_REPO}.bak.${TS}"

if [[ -d "${DEPLOY_REPO}" ]]; then
  echo "→ 将现有目录移动到备份：${DEPLOY_REPO} → ${BACKUP}"
  mv "${DEPLOY_REPO}" "${BACKUP}"
else
  echo "⚠ 未找到 ${DEPLOY_REPO}，将只做全新 clone"
  BACKUP=""
fi

mkdir -p "$(dirname "$DEPLOY_REPO")"
echo "→ git clone -b ${GIT_BRANCH} ${GIT_REPO_URL} → ${DEPLOY_REPO}"
git clone -b "${GIT_BRANCH}" "${GIT_REPO_URL}" "${DEPLOY_REPO}"

restore_if_exists() {
  local name="$1"
  [[ -n "$BACKUP" ]] || return 0
  [[ -f "${BACKUP}/${name}" ]] || return 0
  cp -a "${BACKUP}/${name}" "${DEPLOY_REPO}/${name}"
  echo "  ✓ 已恢复 ${name}"
}

restore_dir_if_nonempty() {
  local rel="$1"
  [[ -n "$BACKUP" ]] || return 0
  [[ -d "${BACKUP}/${rel}" ]] || return 0
  mkdir -p "${DEPLOY_REPO}/$(dirname "$rel")"
  cp -a "${BACKUP}/${rel}" "${DEPLOY_REPO}/${rel}"
  echo "  ✓ 已恢复目录 ${rel}/"
}

cd "${DEPLOY_REPO}"

restore_if_exists .env.local
restore_if_exists docker-compose.wechat-pay-key.yml

# 自签或同步进仓库目录的 PEM（Let's Encrypt 若只在宿主机 /etc，不必在此）
restore_dir_if_nonempty infra/test/certs

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ CVM Git bootstrap 完成"
[[ -n "$BACKUP" ]] && echo "    备份：${BACKUP}"
echo "    克隆：${DEPLOY_REPO}  branch=${GIT_BRANCH}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "下一步（在 Mac 仓库根）："
echo "  1）git push origin ${GIT_BRANCH}"
echo "  2）make release-cvm          # GIT_BRANCH=${GIT_BRANCH} 时会拉该分支（默认已在脚本写明）"
echo ""
echo "云上一次整包复核（任选）："
echo "  cd '${DEPLOY_REPO}' && bash infra/deploy/release-cvm-on-server.sh"
