# 「小鸟 AI」Git 协作规范

> 版本：v1.0
> 日期：2026 年 4 月 20 日
> 适用范围：本仓库所有贡献者（含 AI 编码助手）

---

## 一、分支模型

采用轻量级 **trunk-based** 模式：

| 分支 | 说明 | 谁能推 |
|------|------|--------|
| `main` | 可随时可发布；**受保护** | 仅通过 PR 合入 |
| `feat/<模块>-<简述>` | 新功能开发 | 本人 |
| `fix/<简述>` | Bug 修复 | 本人 |
| `chore/<简述>` | 工程/依赖/配置/文档小改 | 本人 |
| `docs/<简述>` | 仅改文档 | 本人 |
| `refactor/<简述>` | 不改外部行为的重构 | 本人 |

**命名示例**：
```
feat/m1-wechat-login
feat/m2-analysis-upload
fix/report-radar-empty
chore/bump-taro-3.6.33
docs/visual-spec-v1.1
```

**禁止**：
- 直接 push 到 `main`。
- 以个人名字命名分支（如 `zhangsan/dev`），**以任务** 为粒度。
- 长期分支（> 2 周未合入），超过 2 周应拆任务或 rebase。

---

## 二、Commit 规范（Conventional Commits）

**格式**：`<type>(<scope>): <subject>`

| type | 使用场景 |
|------|---------|
| `feat` | 新功能（用户可见） |
| `fix` | Bug 修复 |
| `docs` | 仅文档 |
| `style` | 代码格式/空白，不影响逻辑 |
| `refactor` | 重构（不改行为、不修 bug） |
| `test` | 新增/修改测试 |
| `chore` | 工程杂项（依赖、脚本、CI、配置） |

**scope**（可选）建议值：`client / backend / ai-engine / docs / infra / m1 / m2 / ...`

**示例**：
```
feat(client): 接入微信一键登录与新用户引导
fix(backend): 修复 JWT 过期时间按秒误算为毫秒
docs: 视觉规范统一为深绿+白+金
chore(client): 升级 Taro 至 3.6.33
refactor(backend): 把 userService 分片到 services/user/
test(backend): 补全 wechat-login 的 mock 路径单元测试
```

**正文**（可选）：一段话说明「为什么」；若关联 issue 或文档，用 `Refs: docs/01-...md §3.1`。

---

## 三、PR 流程

1. **拉最新 main**：`git fetch && git rebase origin/main`。
2. **一件事一 PR**：避免「一 PR 改 30 个文件、跨 3 个模块」。
3. **PR 标题** 也用 Conventional Commits 格式（与 squash 后 commit 保持一致）。
4. **填写模板**（`.github/pull_request_template.md`），尤其 **自测记录** 与 **文档同步**。
5. **自测通过**：
   - 客户端：`pnpm type-check && pnpm lint`，至少在微信开发者工具里走通主路径。
   - 后端：`make backend-lint && make backend-test`。
6. **评审**：至少 1 人 review；涉及 API / 数据库 schema / 视觉规范变更的，需对应负责人额外 review。
7. **合并策略**：默认 **Squash Merge**，PR 标题即最终 commit message。
8. **合并后**：删除远程分支；本地 `git branch -d <branch>`。

---

## 四、与文档同步

代码与文档 **双向锁定**：

| 代码变更 | 必须同步的文档 |
|----------|-----------------|
| 新接口 / 改字段 / 改错误码 | `docs/02-API接口设计文档.md` |
| 数据库表结构变更 | `docs/03-数据库设计文档.md` + Alembic revision |
| 视觉 / Token / 配色变更 | 《产品设计白皮书》§7.2 + `client/src/app.scss` |
| 模块验收标准调整 | `docs/01-MVP功能需求规格说明书.md` |
| 工程规范变更（工具链/目录） | `docs/04-项目工程规范文档.md` |

**文档未同步的 PR 一律不予合并**。

---

## 五、禁止事项

- `git push --force` 到共享分支。
- `git commit --amend` / `git rebase` **已推送**的共享分支（私人未推分支不限）。
- 提交：`.env.local`、密钥、证书（`*.p8`、`*.key`、`*.mobileprovision`）、大文件（> 10MB 的视频/模型权重）。
- 在 main 上打未经确认的 tag。
- 跳过 `pre-commit` / CI（若后续接入）。

---

## 六、常用命令备忘

```bash
# 新建分支
git switch -c feat/m1-wechat-login origin/main

# 同步 main（rebase 风格）
git fetch origin
git rebase origin/main

# 放弃本地改动
git restore .
git restore --staged .

# 整理提交历史（仅限本地未推分支）
git rebase -i HEAD~3

# 撤销刚才的合并（未推送时）
git reset --hard HEAD@{1}
```
