# P2-M10-03 · 个人 yardage book · 启动包（W30 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §6.3`](../23-二期可编码规格说明书.md#63-p2-m10-03--个人-yardage-book)
> 前置：P2-M9-02 装备清单 + 一期 M5 海报合成

---

## 一、文档目的与边界

为 **P2-M10-03** 落地 W30-W34 客户端 + 后端 SOP，提供"每根杆我能打多远"清单 + 历史反推算法。

### 边界（不做）

- 不修改 docs/22/23 字段
- 不引入 GPS / 高精度测距（用户自报 + 历史反推）

---

## 二、现状盘点

- M9-02 已建 `user_clubs.avg_yards / std_yards`
- 一期分析时填的"目标距离"在 swing_analyses.target_yardage（一期已有 ；如未有则需先补此字段）

### 缺口（vs docs/23 §6.3 FR）

5 个 FR 全部新增。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| Service | `services/yardage_book_service.py` | 1 PW |
| API | GET/PUT /v1/users/me/yardage-book | 0.5 PW |
| UI | `pages/profile/yardage-book/index.tsx` | 1 PW |
| 反推算法 | `services/yardage_inference.py`（新） | 1 PW |
| 分享卡片 | 复用 M5 海报 | 0.5 PW |

**合计：~4 PW**

### 3.2 反推算法

```python
def infer_yardage(user_id, club_type):
    samples = db.query(SwingAnalysis).filter(
        SwingAnalysis.user_id == user_id,
        SwingAnalysis.club_type == club_type,
        SwingAnalysis.target_yardage.isnot(None)
    ).order_by(SwingAnalysis.created_at.desc()).limit(50).all()
    if len(samples) < 5:
        return None  # 采样不足
    return {
        'avg': mean([s.target_yardage for s in samples]),
        'std': stdev([s.target_yardage for s in samples]),
        'sample_count': len(samples)
    }
```

### 3.3 UI 行

```
| 杆 | 品牌 | loft | my_yards | std | 样本 |
| 1W | Titleist TSi3 | 9.0° | 240yd | ±15 | 12 |
| 7i | Mizuno JPX 923 | 34° | 145yd | ±5 | 8 |
| PW | (未填) | - | 采样不足 | - | 3 |
```

### 3.4 分享卡片

复用 M5 海报合成；自定义 yardage_book 模板。

---

## 四、字段 v0.1

```
GET /v1/users/me/yardage-book
Response: { clubs: [{ club_id, brand, model, loft, my_yards, std_yards, sample_count, source: 'self' | 'inferred' }] }
```

---

## 五、验证数据

- 装备清单每杆可见（AC-1）
- 修订生效（AC-2）
- ≥5 段才统计（AC-3）

---

## 六、W30-W34 周计划

| 周 | 任务 |
| --- | --- |
| W30 | service + API |
| W31 | 反推算法 + 单测 |
| W32 | UI |
| W33 | 分享卡片 |
| W34 | 灰度 + AC 验收 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 客户端 | UI + 分享 |
| 后端 | 反推 + API |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | target_yardage 一期未填 | 增 "我打几码" prompt；老数据仅看自报 |
| R-02 | 反推偏差大 | 仅 ≥5 段才显示；UI 提示 "估算" |
| R-03 | 用户隐私 | 分享卡片可隐藏精确码数（仅 std 等级） |

### AC

- [ ] AC-1 每杆可见
- [ ] AC-2 修订生效
- [ ] AC-3 ≥5 段才统计

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M9-02 装备 | 数据源 |
| 一期 swing_analyses | 反推源 |
| 一期 M5 海报 | 分享 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
