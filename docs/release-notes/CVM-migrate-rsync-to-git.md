# CVM：从 rsync/scp 树 → 云上 Git clone（一次迁移）

迁移完成后日常发版：**本机 `git push` → `make release-cvm`**（见 **`CVM-canonical-deploy.md`** 主干）。

---

## 1. 前提

| 项 | 说明 |
|----|------|
| 远端有可拉代码 | **`GIT_REPO_URL`** + **`GIT_BRANCH`**（默认 **`main`**）上已有你从 Mac **`git push`** 的提交；**不要**在云上用「空克隆」顶替仍对外服务的目录。Mac 尚无 **`origin`** 时照下文小节补一次 **`git remote add`** + **`git push`**。 |
| CVM 能 `git clone` | HTTPS：可用带 token 的 URL 或配置了凭据；SSH：在云上加 **Deploy key**，或使用已能 **`git ls-remote`** 的密钥。 |
| 路径沿用 | **`$DEPLOY_REPO`**（通常 **`~/lingniao-golf`**），与原 compose / 文档路径一致。**Docker volume 数据不会因目录更名而清空**（卷在 Docker 宿主存储）。 |

### Mac：`origin` 尚未配置时（一次）

```bash
cd ~/Documents/灵鸟golf   # 按你本机仓库路径为准
git remote add origin git@github.com:你的组织/lingniao-golf.git   # URL 与同云上一致
git branch -M main
git push -u origin main
```

---

## 2. 迁移命令（在云服务器上以 `ubuntu` 执行）

### 第一次：云上还没有「带脚本的克隆」怎么办？

任选其一：

- **若还能 rsync：** 先在 Mac **`make publish-backend-cvm`** 一次，确保云上已有最新 **`infra/deploy/cvm-bootstrap-git-on-server.sh`**；再 SSH。
- **或** 在本机：**`scp infra/deploy/cvm-bootstrap-git-on-server.sh ubuntu@你的CVM:~/`** → SSH：**`chmod +x ~/cvm-bootstrap-git-on-server.sh`** → 设 **`GIT_REPO_URL`** → **`bash ~/cvm-bootstrap-git-on-server.sh`**（与下放「仅 home 脚本」同效：会备份原 **`~/lingniao-golf`** 再 **`git clone`**）。

**推荐整块迁移**（将把现有散装目录改名为 `*.bak.<时间戳>`，再在原路径 **`git clone`**）：

```bash
export GIT_REPO_URL='git@github.com:你的组织/lingniao-golf.git'   # 或 https://...
export GIT_BRANCH=main
bash ~/lingniao-golf/infra/deploy/cvm-bootstrap-git-on-server.sh
```

仅在云上有 **`~/cvm-bootstrap-git-on-server.sh`**、尚无仓库内脚本副本时：

```bash
cd ~
export GIT_REPO_URL='git@github.com:你的组织/灵鸟golf.git'
export GIT_BRANCH=main
bash ./cvm-bootstrap-git-on-server.sh
```

⚠️ 若云上 **`~/lingniao-golf`** 仍存在且 **不是 git 仓库**，脚本会先把 **`~/lingniao-golf`** 整体 **`mv` 成 `~/lingniao-golf.bak.<时间戳>`**，再在 **`~/lingniao-golf`** 新路径执行 **`git clone`**。迁移窗口内 Compose 不可用数分钟为正常；可先接受短暂停机或使用维护窗口。

---

## 3. 脚本自动恢复的文件

从备份目录 **`*.bak.<时间戳>`** 复制的常见项：

- **`.env.local`**（云上密钥单侧真源，不入库的那份）
- **`docker-compose.wechat-pay-key.yml`**（若你曾经放在该路径）
- **`infra/test/certs/`**（若在仓库树下有自签/同步 PEM；Let's Encrypt **仅宿主 `/etc`** 的路径不在此复制范围内）

没有的项会跳过。**商户 PEM、仅宿主机挂载**的路径请自行对照 **`CVM-canonical-deploy.md`** 核验。

---

## 4. 迁移后自检

在云 **`$DEPLOY_REPO`**：

```bash
git status && git remote -v
bash infra/deploy/check-cvm-pay-mount.sh .env.local
```

在 Mac：

```bash
make release-cvm                    # SSH 远端 release-cvm-on-server.sh → pull → compose → alembic
# 按需
make cvm-smoke DOMAIN=api.birdieai.cn TOKEN=…
```

日常 **不必**再走 **`publish-backend-cvm`**（除非你临时要「不传 git、只拷目录」兜底）。

---

## 5. 回滚思路

克隆失败或未就绪时：停 compose；将 **`~/lingniao-golf.bak.<时间戳>`** 移回 **`~/lingniao-golf`**；再按旧 rsync 流程恢复。

---

脚本源码：**`infra/deploy/cvm-bootstrap-git-on-server.sh`**。
