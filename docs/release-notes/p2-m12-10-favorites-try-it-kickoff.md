# P2-M12-10 · 收藏 / "想试试看"一键生成训练任务 · 启动包（W34 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §8.10`](../23-二期可编码规格说明书.md#810-p2-m12-10--收藏--想试试看一键生成训练任务)
> 前置：P2-M11 课程 + 一期 M4 training_tasks

---

## 一、文档目的与边界

为 **P2-M12-10** 落地 W34-W37 客户端 + 后端 SOP，让用户收藏球手 clip + 一键生成"模仿球手挥杆"训练任务。

### 边界（不做）

- 不修改 docs/22/23/03 字段
- 不引入收藏 paywall

---

## 二、现状盘点

- M12-01 已建 user_pro_favorites 表（含 training_task_id）
- 一期 training_tasks 服务可调
- M11 已有学习路径

### 缺口

4 个 FR 全部新增。

---

## 三、模块设计

### 3.1 改造

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Service | `services/pro_favorites_service.py` | 0.7 PW |
| API | POST/DELETE /favorites + POST /try-it | 0.3 PW |
| Clip 详情"收藏" UI | `pages/pros/clips/[id].tsx` 加 ❤️ | 0.3 PW |
| "想试试看" 按钮 + 模板 | `pages/pros/clips/[id].tsx` + service | 0.5 PW |
| 单测 | tests | 0.2 PW |

**合计：~2 PW**

### 3.2 "想试试看"模板

```python
def create_try_it_task(user_id, pro_clip_id):
    clip = get_clip(pro_clip_id)
    task = create_training_task(
        user_id=user_id,
        title=f'对照 {clip.player_name_zh} 的挥杆拍一条自己的',
        description=f'参考 clip {clip.id}; 同 club_category 拍摄',
        deadline=now() + timedelta(days=3),
        source='pro_clip_try_it',
        reference={'pro_clip_id': pro_clip_id}
    )
    db.add(UserProFavorite(user_id=user_id, clip_id=pro_clip_id, training_task_id=task.id))
    return task
```

### 3.3 学员训练 Tab 区分

- "教练布置的任务"分组下，可见"对照球手训练" sub-section

---

## 四、字段 v0.1

```
POST   /v1/users/me/pros/favorites Body: { clip_id }
DELETE /v1/users/me/pros/favorites/{clip_id}
GET    /v1/users/me/pros/favorites
POST   /v1/users/me/pros/favorites/{clip_id}/try-it → 返 training_task_id
```

---

## 五、验证数据

- 收藏/取消/列表（AC-1）
- "想试试看" → 5s 内训练 Tab 出现（AC-2）
- 不与 M11 / M4 冲突（AC-3）

---

## 六、W34-W37 周计划

| 周 | 任务 |
| --- | --- |
| W34 | service + API |
| W35 | UI + 联调 |
| W36 | 训练 Tab 区分 |
| W37 | 灰度 + AC |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | service / API |
| 客户端 | UI |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 重复触发"想试试看" | 检查 training_task_id 已存在 |
| R-02 | 任务过多 | 同 clip 同用户 ≤1 个 active task |
| R-03 | clip 下架后任务残留 | 任务保留；UI 提示已下架 |

### AC

- [ ] AC-1 收藏链路
- [ ] AC-2 try-it → 训练 Tab
- [ ] AC-3 与 M11/M4 兼容

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M12-01 schema | user_pro_favorites |
| 一期 training_tasks | 任务来源 |
| P2-M11 | 课程兼容 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
