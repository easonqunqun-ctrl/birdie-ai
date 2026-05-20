# W8 · tabBar 图标说明（**2026-05-20 已升级为正式版**）

> 本文档原为 W8 内测期 **占位图标** 的方案；2026-05-20 已用代设计师产出的「正式版」覆盖：
> 形状从「圆 / 方 / 三角 / 菱形」升级为「房屋 / 对话气泡 / 球场旗杆 / 人形」；
> 激活色从「深绿 #0f3d2e」修正为「靛蓝 #1a237e」，与 `app.config.ts::selectedColor`、
> `app.scss::--color-primary` 三处同源。

## 现状（2026-05-20 起）

- 尺寸：**81×81 px**（微信推荐上限；`cover-view` 下自动缩放）
- 格式：**PNG RGBA**（透明背景）+ **4× 超采样抗锯齿**（边缘平滑过渡）
- 颜色（**与三处同源**：[`client/src/app.config.ts::tabBar`](../../client/src/app.config.ts) / [`client/src/app.scss::--color-primary`](../../client/src/app.scss) / 本仓库白皮书 §7.2）：
  - 默认态 `#888888`（与 `tabBar.color` 完全一致）
  - 激活态 `#1a237e`（与 `tabBar.selectedColor` / `--color-primary` 完全一致）
- 形状（**正式版语义**）：

| Tab      | pagePath                | 形状（语义）                            |
|----------|-------------------------|-----------------------------------------|
| 首页     | `pages/index/index`     | **房屋**（屋顶 + 屋身 + 门洞，"家"）    |
| AI 教练  | `pages/coach/index`     | **对话气泡**（圆角矩形 + 左下尾巴）     |
| 训练     | `pages/training/index`  | **球场旗杆 + 三角旗 + 底座**（高尔夫）  |
| 我的     | `pages/profile/index`   | **人形**（圆头 + 半圆肩膀 + 分离缝）    |

## 生成脚本

```bash
python3 scripts/gen_tab_icons.py
```

脚本纯标准库（`struct` + `zlib`），不依赖 PIL/Pillow，CI 机器无需额外环境即可跑。
**4× 超采样**（每像素 16 子样本）让斜边 / 圆弧抗锯齿，整次生成约 ~0.5 秒。
输出路径固定为 `client/src/assets/tab/`。

## 构建流程

- [`client/config/index.ts::copy.patterns`](../../client/config/index.ts) 里声明：
  ```
  { from: 'src/assets/tab/', to: 'dist/assets/tab/' }
  ```
  每次 `pnpm build:weapp` / `pnpm build:weapp:test` 构建时，会把 8 张 PNG 同步到
  `dist/assets/tab/` 下（与 `miniprogramRoot` 一致）。
- [`client/src/app.config.ts::tabBar.list`](../../client/src/app.config.ts) 里以相对路径
  `assets/tab/home.png` 形式引用，微信运行时即能找到。

## 设计稿替换流程（若后续设计师出更高质感的稿）

**替换方式：直接覆盖同名 PNG 即可，零代码改动。**

1. 拿到设计稿（8 张；建议输出 81×81 的 `@3x` 位图）
2. 保持以下文件名（不得改）：
   ```
   home.png            home_active.png
   coach.png           coach_active.png
   training.png        training_active.png
   profile.png         profile_active.png
   ```
3. 放到 `client/src/assets/tab/` 覆盖现有版本
4. 删除 `scripts/gen_tab_icons.py` 也可以（或保留作快速兜底工具）
5. 重新 `pnpm build:weapp:prod` 出包；用开发者工具预览，确认 4 个 tab 视觉一致

## 注意事项

- 微信要求 **图标 < 40KB**。当前 8 张 PNG 平均 < 500 B（远低于上限）；设计稿实际约 1~5 KB 也安全。
- `iconPath` 不能是 HTTP URL 或本地绝对路径，**只能**是 `miniprogramRoot` 下的相对路径。
- 小程序 tabBar **同时只允许 2-5 个 tab**，新增/删除 tab 需一起改 `app.config.ts::tabBar.list` 和 `pages` 数组（tabBar 页必须同时出现在 pages 里）。

## CI 守护

[`/.github/workflows/tab-icons-guard.yml`](../../.github/workflows/tab-icons-guard.yml) 在改到以下任一文件时自动触发，确保**脚本 / PNG / app.config.ts** 三者永远同步：

- `scripts/gen_tab_icons.py`
- `client/src/assets/tab/**`
- `client/src/app.config.ts`

守护断言两条：

1. **PNG bit-exact**：跑一次 \`python3 scripts/gen_tab_icons.py\` → \`git diff --exit-code client/src/assets/tab/\` 必须无差异。改脚本但忘重生成、或手 P 图但脚本未同步，CI 红。
2. **图标色与文字色同源**：\`app.config.ts::tabBar.color\` 必须 == \`gen_tab_icons.py::FILL_DEFAULT\`；\`tabBar.selectedColor\` 必须 == \`FILL_ACTIVE\`。误改其一就 CI 红。

## 历史

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04（W8） | **占位版** | 圆 / 方 / 三角 / 菱形几何图形；激活色 `#0f3d2e` 深绿；为 W8 真机白名单内测让 tab 栏能正常显示 |
| 2026-05-20 | **正式版（当前）** | 形状升级为房屋 / 气泡 / 旗杆 / 人形；激活色修正为 `#1a237e` 靛蓝（与品牌系统三处同源）；加 4× 超采样抗锯齿 |
