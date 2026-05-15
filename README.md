# ImageHost

长期图床仓库，基于 GitHub Issues + GitHub Actions + GitHub Pages。

当前主流程不需要 Cloudflare：用户在 GitHub Issue 里贴图，GitHub Actions 自动把图片保存进仓库，生成长期 URL，并把 URL 回复到 issue 里。

## 访问入口

图床首页：

```text
https://mds-gif-skech.github.io/ImageHost/
```

上传入口：

```text
https://github.com/MDS-gif-skech/ImageHost/issues/new/choose
```

图片 URL 格式：

```text
https://mds-gif-skech.github.io/ImageHost/images/YYYY/MM/filename.ext
```

## 使用方式

1. 打开上传入口。
2. 选择 `Upload image`。
3. 把图片拖进 issue 文本框，等 Markdown 里出现 `![...](https://github.com/user-attachments/assets/...)`。
4. 点击 `Create`。
5. 等待 Actions 自动回复图片 URL。

## 支持格式

```text
png, jpg, jpeg, webp, gif
```

## 自动索引

每次成功上传后，仓库会自动更新：

```text
data/images.json
data/images.csv
```

## 备用方案

`worker/` 目录保留 Cloudflare Worker 版本。如果某天 GitHub Actions 又不可用，可以切回 Worker 上传方案。
