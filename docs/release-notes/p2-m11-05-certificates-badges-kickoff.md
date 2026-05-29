# P2-M11-05 · 证书 / 勋章（金色系，对齐白皮书 §7.2）· 启动包（W32 起跑）

> 版本：v0.1（2026-05-25）
> 上游真源：[`docs/23 §7.5`](../23-二期可编码规格说明书.md#75-p2-m11-05--证书--勋章金色系对齐白皮书-72)
> 前置：[`p2-m11-04-stage-assessment-kickoff.md`](./p2-m11-04-stage-assessment-kickoff.md) + 一期 M5 海报合成

---

## 一、文档目的与边界

为 **P2-M11-05** 落地 W32-W35 客户端 + 后端 + 设计 SOP，实现"通关一阶段 → 颁发金色证书 → 一键分享"完整闭环。

### 边界（不做）

- 不实现非通关型勋章（连续打卡等，由 M5 一期承载）
- 不实现 NFT / 区块链类高级证书
- 不修改 docs/22/23 字段

---

## 二、现状盘点

- 一期 `/v1/shares/*` 海报合成已就位
- 一期 share-card 模板基于 SVG + Canvas
- M11-04 触发 `award_certificate` 已埋钩

### 缺口（vs docs/23 §7.5 FR）

5 个 FR 全部新增；需新 SVG 证书模板。

---

## 三、模块设计

### 3.1 新增

| 模块 | 路径 | 工程量 |
| --- | --- | --- |
| ORM model | M11-01 已含 course_certificates | — |
| Service | `services/course_certificate_service.py` | 0.5 PW |
| API | GET /v1/users/me/certificates + POST share-card | 0.3 PW |
| 证书 Tab UI | `pages/profile/certificates/` | 0.5 PW |
| 海报合成模板 | `services/share/certificate_template.py`（新） + SVG | 0.5 PW |
| 通关触发 hook | M11-04 hook 已埋；本任务实现 award | 0.2 PW |

**合计：~2 PW**

### 3.2 award_certificate 流程

```python
def award_certificate(user_id, course_id):
    cert = CourseCertificate(
        user_id=user_id, course_id=course_id,
        stage=course.stage,
        image_url=None,  # 异步生成
        payload={'awarded_at': now(), 'course_name': course.title}
    )
    db.add(cert); db.commit()
    enqueue_async_certificate_image(cert.id)
    notify_user(user_id, '🏆 恭喜通关「全挥杆基础」！')
```

### 3.3 证书 SVG 模板

- 主色：`--color-gold` (#c9a227)
- 副色：`--color-primary` (#1a237e)
- 元素：
  - 顶部 logo + 应用名
  - 中央阶段名 "全挥杆基础"
  - 用户名 + 通关日期
  - 底部"灵鸟golf · 第 N 阶通关证书"水印
- 视觉走查产品 + 设计双签（AC-3）

### 3.4 证书 Tab UI

```tsx
<Grid columns={2}>
  {certificates.map(c => (
    <CertificateCard image_url={c.image_url} stage={c.stage} onShare={...} />
  ))}
</Grid>
```

### 3.5 分享

复用 M5 share-card 链路 + 海报合成模板。

---

## 四、字段 v0.1

```
GET  /v1/users/me/certificates
POST /v1/users/me/certificates/{cert_id}/share-card
  Resp: { share_url, expires_at }
```

---

## 五、验证数据

- 通关 → 5s 内证书入库（image_url 生成 ≤5s 异步）（AC-1）
- 分享卡片到朋友圈成功（AC-2）
- 视觉走查通过（AC-3）

---

## 六、W32-W35 周计划

| 周 | 任务 |
| --- | --- |
| W32 | service + award + SVG 模板 |
| W33 | 证书 Tab UI |
| W34 | 分享 + M5 联调 |
| W35 | 视觉走查 + 灰度 |

---

## 七、责任 / 风险 / 验收

### 责任

| 角色 | 责任 |
| --- | --- |
| 后端 | service + 海报合成 |
| 客户端 | 证书 Tab + 分享 |
| 设计 | SVG 模板 + 视觉走查 |

### 风险

| ID | 风险 | 兜底 |
| --- | --- | --- |
| R-01 | 海报合成失败 | 异步重试 3 次；失败下次主动重生 |
| R-02 | 中文字体缺失 | 内置 Noto Sans CJK |
| R-03 | 通关推送疲劳 | 仅阶段通关推送 |
| R-04 | 证书伪造 | 二维码扫码回 cert_id 验真 |

### AC

- [ ] AC-1 通关自动颁发
- [ ] AC-2 海报可分享
- [ ] AC-3 视觉走查

---

## 八、附录

| 任务 | 关系 |
| --- | --- |
| P2-M11-01 schema | course_certificates |
| P2-M11-04 考核 | award 触发 |
| 一期 M5 海报 | 复用合成 |

---

## 九、变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-05-25 | 初版 |
