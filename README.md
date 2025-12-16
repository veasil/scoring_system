# 伍力全开｜登录 + 数据库（本地可跑模板）

## 1) 运行
```bash
cd wqt-auth-backend
cp .env.example .env
npm i
npm run dev
```

打开： http://localhost:3000

> 注意：你原项目里还有 `styles.css / cards-data.js / global-state.js ...` 等文件。
> 需要把它们一起放到 `public/` 目录下，保持相对路径不变（例如 `public/styles.css`）。

## 2) 已实现能力
- 右上角「登录/退出」 + 登录弹窗（账号登录/注册）
- 未登录时「新游戏」按钮不可点击；点了会提示先登录
- SQLite 数据库：保存用户、游戏开始事件、游戏结束数据
- 把“生成故事”的 LLM 请求改成走后端 `/api/llm/story`，避免 Key 暴露在浏览器

## 3) 微信登录
模板里预留了：
- `GET /api/auth/wechat/qr` 返回二维码 & sessionId
- `GET /api/auth/wechat/poll?sessionId=...` 轮询登录结果

但「真正可用」取决于你选的微信登录场景（电脑网页扫码 / 微信内网页授权 / 小程序登录），需要你填 `.env` 中的微信参数并完善回调处理逻辑。
