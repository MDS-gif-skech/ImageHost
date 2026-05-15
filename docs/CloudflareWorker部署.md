# Cloudflare Worker 部署

这份说明用于把图床改成不依赖 GitHub Actions 的版本。

## 一、准备 GitHub Token

打开：

```text
https://github.com/settings/personal-access-tokens/new
```

建议创建 fine-grained token。

配置如下：

```text
Token name: ImageHost Worker
Expiration: 建议 90 天、180 天，或按你的习惯设置
Repository access: Only select repositories
Selected repository: Ayayadaze/ImageHost
```

Repository permissions：

```text
Contents: Read and write
Metadata: Read-only
```

创建后复制 token，后面只会显示一次。

## 二、创建 Cloudflare Worker

打开 Cloudflare Dashboard：

```text
https://dash.cloudflare.com/
```

进入：

```text
Workers & Pages -> Create application -> Worker
```

名称建议：

```text
imagehost-uploader
```

创建后进入 Worker 编辑页面，把 `worker/src/worker.js` 的内容粘贴进去并保存。

## 三、配置 Worker 变量

进入 Worker：

```text
Settings -> Variables
```

添加普通变量：

```text
GITHUB_OWNER=Ayayadaze
GITHUB_REPO=ImageHost
GITHUB_BRANCH=main
PUBLIC_BASE_URL=https://ayayadaze.github.io/ImageHost
MAX_IMAGE_BYTES=10485760
ALLOW_ORIGIN=*
```

添加 Secret：

```text
GITHUB_TOKEN=刚刚创建的 GitHub Token
```

可选 Secret：

```text
UPLOAD_SECRET=你自己设置的上传密码
```

如果希望完全开放上传，可以不设置 `UPLOAD_SECRET`。

## 四、获取上传接口

Worker 保存部署后，会得到一个地址，例如：

```text
https://imagehost-uploader.xxx.workers.dev
```

上传接口就是：

```text
https://imagehost-uploader.xxx.workers.dev/upload
```

## 五、使用上传页

打开：

```text
https://ayayadaze.github.io/ImageHost/upload.html
```

填写 Worker 上传接口。

如果设置了 `UPLOAD_SECRET`，也填写上传密码。

然后选择图片并上传。

## 六、本地命令部署方式，可选

如果本机已安装 Node.js，也可以用命令部署：

```powershell
cd D:\Work\ImageHost\worker
npm install
npx wrangler login
npx wrangler secret put GITHUB_TOKEN
npx wrangler secret put UPLOAD_SECRET
npx wrangler deploy
```

如果不想设置上传密码，可以跳过：

```powershell
npx wrangler secret put UPLOAD_SECRET
```
