# 微信小程序「深度合成 - AI 问答」类目 — 可公开获取的佐证材料

本目录下的 **PDF / PNG 仅覆盖「第三方技术方（DeepSeek）官网公开说明」**，便于与贵司其它材料一并装订。

**装订稿封面表**已写入（与仓库配置一致，提交前请与公众平台再核一次）：

- 认证主体：**北京思无界控股有限公司**（`docs/release-notes/W9-tencent-cloud-purchase-list.md`）
- 小程序 AppID：**wx045feb5e244fffae**（`client/project.config.json`）
- 展示名：**领翼golf 高尔夫智能教练**（`project.config.json` → `description`，若与后台「基本设置」不一致以**后台为准**，并改 HTML 后重导 PDF）

## 本目录文件

| 文件 | 说明 |
|------|------|
| `appendix-deepseek-public-materials.zh.html` | 可编辑源稿（封面主体/AppID + DeepSeek 公示摘录 + 须自证清单） |
| `appendix-deepseek-public-materials.zh.pdf` | 由本地 Chrome headless 导出的装订版 PDF（按需打开 HTML 微调后重生成） |
| `deepseek-model-algorithm-disclosure-screenshot.png` | 《模型原理与训练方法说明》整页长截图（CDN 原页） |

## 仍须贵司自行准备的材料（我方无法代劳）

- 微信公众平台该类目审核页要求的 **后台截图**（以当期界面为准）。
- 与 DeepSeek 开放平台（或合法授权渠道）的 **协议 / 订单关键页**（含双方主体信息），按审核要求盖章或电子签。
- 若审核人员要求 **网信办备案系统** 等可追溯页面截屏，须在 **官方指定系统** 登录后截取。
- 小程序端的 **AI 生成标识、隐私政策与《用户隐私保护指引》字段** 与产品实际行为一致。

## 重新导出 PDF（可选）

```bash
HTML="/ABS/PATH/TO/docs/wechat-mp-audit-ai-category/appendix-deepseek-public-materials.zh.html"
PDF="${HTML%.html}.pdf"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$PDF" "file://$HTML"
```

原始公开来源：https://cdn.deepseek.com/policies/zh-CN/model-algorithm-disclosure.html

开放平台服务协议（佐证 API 技术服务关系）：  
https://cdn.deepseek.com/policies/zh-CN/deepseek-open-platform-terms-of-service.html
