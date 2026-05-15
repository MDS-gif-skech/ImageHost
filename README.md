# ImageHost

长期图床仓库，基于 GitHub Issues、GitHub Actions 和 GitHub Pages。

## 使用方式

1. 打开本仓库的 Issues。
2. 新建一个 `Upload image` issue，或者在已有 issue 评论中粘贴图片。
3. 等待 GitHub Actions 自动处理。
4. Action 会把图片保存到 `images/YYYY/MM/`，并在 issue 里回复最终图片 URL。
5. 图片记录会自动写入：
   - `data/images.json`
   - `data/images.csv`

## 图片 URL

GitHub Pages URL 格式：

```text
https://Ayayadaze.github.io/ImageHost/images/YYYY/MM/filename.ext
```

如果后续绑定自定义域名，例如 `https://img.example.com`，只需要修改仓库变量 `PUBLIC_BASE_URL`。

## 支持格式

默认支持：

```text
png, jpg, jpeg, webp, gif
```

出于安全考虑，默认不接收 `svg`。如确实需要，可在 workflow 中加入白名单，但不建议让外部用户上传 SVG。

## 权限控制

默认只允许以下用户上传：

- 仓库 owner
- collaborator
- member

如需放开给指定用户，请在仓库变量 `ALLOWED_UPLOADERS` 中填写 GitHub 用户名，多个用户用英文逗号分隔：

```text
alice,bob,charlie
```

## 管理命令

如果想在 issue 评论里手动触发，可以评论：

```text
/upload
```

只要评论里包含图片附件，workflow 就会处理。

## 重要限制

- GitHub Pages 适合个人和项目图床，不适合超大流量商业 CDN。
- 建议单张图片控制在 10MB 内。
- 请不要上传敏感图片，因为 Pages 发布后是公开访问的。
