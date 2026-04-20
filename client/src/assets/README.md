# assets

小程序静态资源目录。**TabBar 图标**需要放置：

```
assets/tab/
├── home.png            首页（普通态，81x81）
├── home_active.png     首页（选中态）
├── coach.png
├── coach_active.png
├── training.png
├── training_active.png
├── profile.png
└── profile_active.png
```

**临时方案**（W1）：先把 `app.config.ts` 中 `tabBar` 的 `iconPath/selectedIconPath` 字段去掉，
等 W2 设计师出图后再加回来。或者使用 emoji 字符代替（仅 H5/RN 可用，weapp 不支持）。
