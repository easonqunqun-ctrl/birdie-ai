# W8-T2 · tabBar 占位图标说明

> 本文档描述 W8 内测期 tabBar 图标的占位方案与 W9 上线前的替换流程。

## 现状（W8 内测）

设计师尚未出正式 tabBar 图标，为了让团队白名单真机扫码内测时 tab 栏能正常显示（微信规定 tabBar 图标 **必填**，缺失会整条底栏不渲染），我们用脚本生成了 8 张纯色几何形状 PNG 作为临时占位。

- 尺寸：**81×81 px**（微信推荐上限；`cover-view` 下自动缩放）
- 格式：**PNG RGBA**（透明背景）
- 颜色：
  - 默认态 `#9ca3af`（中性灰，与 `color: '#6b7280'` 的文字搭配）
  - 激活态 `#0f3d2e`（品牌深绿，与 `selectedColor: '#0f3d2e'` 一致）
- 形状（仅用于 4 个 tab 彼此视觉区分，**不代表最终视觉稿**）：

| Tab      | pagePath                | 形状         |
|----------|-------------------------|--------------|
| 首页     | `pages/index/index`     | 实心圆       |
| AI 教练  | `pages/coach/index`     | 实心正方形   |
| 训练     | `pages/training/index`  | 实心等腰三角 |
| 我的     | `pages/profile/index`   | 实心菱形     |

## 生成脚本

```
python3 scripts/gen_tab_icons.py
```

脚本纯标准库（`struct` + `zlib`），不依赖 PIL/Pillow，CI 机器无需额外环境即可跑。输出路径固定为 `client/src/assets/tab/`。

## 构建流程

- `client/config/index.ts::copy.patterns` 里声明：
  ```
  { from: 'src/assets/tab/', to: 'dist/assets/tab/' }
  ```
  每次 `pnpm build:weapp` / `pnpm build:weapp:test` 构建时，会把 8 张 PNG 同步到 `dist/assets/tab/` 下（与 `miniprogramRoot` 一致）。
- `client/src/app.config.ts::tabBar.list` 里以相对路径 `assets/tab/home.png` 形式引用，微信运行时即能找到。

## 设计师替换流程（W9 上线前）

**替换方式：直接覆盖同名 PNG 即可，零代码改动。**

1. 拿到设计稿（8 张；建议输出 81×81 的 `@3x` 位图）
2. 保持以下文件名（不得改）：
   ```
   home.png            home_active.png
   coach.png           coach_active.png
   training.png        training_active.png
   profile.png         profile_active.png
   ```
3. 放到 `client/src/assets/tab/` 覆盖占位版本
4. 提交前删除 `scripts/gen_tab_icons.py` 也可以（或保留作为后续快速占位工具）
5. 重新 `pnpm build:weapp:prod` 出包；用开发者工具预览，确认 4 个 tab 视觉一致

## 注意事项

- 微信要求 **图标 < 40KB**。占位图平均 < 300 B；设计稿实际约 1~5 KB。若超过 40 KB，tabBar 会不显示图标，需让设计师压缩。
- `iconPath` 不能是 HTTP URL 或本地绝对路径，**只能**是 `miniprogramRoot` 下的相对路径。
- 小程序 tabBar **同时只允许 2-5 个 tab**，新增/删除 tab 需一起改 `app.config.ts::tabBar.list` 和 `pages` 数组（tabBar 页必须同时出现在 pages 里）。
