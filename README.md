# ImageHost

长期图床仓库，基于 GitHub Pages + Cloudflare Worker。

当前不再依赖 GitHub Actions。图片上传由 Cloudflare Worker 接收，Worker 使用 GitHub API 把图片和索引写入本仓库，因此即使账号无法运行 GitHub Actions，也可以正常使用。

## 访问入口

图床首页：

```text
https://ayayadaze.github.io/ImageHost/
```

上传页面：

```text
https://ayayadaze.github.io/ImageHost/upload.html
```

图片 URL 格式：

```text
https://ayayadaze.github.io/ImageHost/images/YYYY/MM/filename.ext
```

## 支持格式

默认支持：

```text
png, jpg, jpeg, webp, gif
```

不建议开放 SVG，因为 SVG 可能包含脚本或外部资源。

## 工作流程

```text
用户打开 upload.html
-> 选择图片
-> 浏览器把图片 POST 到 Cloudflare Worker
-> Worker 调用 GitHub API
-> 图片写入 images/YYYY/MM/
-> 索引写入 data/images.json 和 data/images.csv
-> Worker 返回可访问 URL
```

## 仓库结构

```text
ImageHost/
  images/                 # 图片文件
  data/
    images.json           # 图片索引 JSON
    images.csv            # 图片索引 CSV
  worker/                 # Cloudflare Worker 上传服务
  docs/                   # 使用和部署说明
  upload.html             # 静态上传页面
  index.html              # 首页
```

## 部署说明

请看：

```text
docs/CloudflareWorker部署.md
```

## 安全建议

Worker 支持可选上传密码 `UPLOAD_SECRET`。如果只给自己或少数人使用，建议设置；如果希望完全开放，可以不设置。

公开图床不要上传隐私图片、证件、合同、账号截图等敏感内容。
