# 部署指南 (Screen + 双环境)

本文档介绍如何在服务器上配置**正式服 (Production)** 和 **测试服 (Staging)** 双环境并行运行的方案。

## 架构概览

我们通过创建两个独立的文件夹来隔离环境，利用不同端口和域名进行访问。

| 环境 | 目录 (建议) | 端口 | 域名 (示例) | Screen 会话名 |
| :--- | :--- | :--- | :--- | :--- |
| **正式服** | `~/wqt-auth-backend` | `8080` | `game.yourdomain.com` | `wqt-prod` |
| **测试服** | `~/wqt-auth-backend-test` | `8081` | `test.yourdomain.com` | `wqt-test` |

---

## 🚀 首次初始化 (仅需做一次)

### 1. 准备正式服
假设您已经拉取了代码在 `~/wqt-auth-backend`。
确保 `.env` 配置正确 (PORT=8080)。

启动正式服：
```bash
screen -S wqt-prod
cd ~/wqt-auth-backend
npm run dev
# 按 Ctrl+A, D 挂起
```

### 2. 准备测试服
复制一份代码作为测试环境（或者重新 git clone）：

```bash
cd ~
cp -r wqt-auth-backend wqt-auth-backend-test
# 或者: git clone <repo_url> wqt-auth-backend-test
```

**关键配置**:
修改测试目录下的 `.env` 文件，将端口改为 **8081**，并建议使用独立的测试数据库：

```bash
nano ~/wqt-auth-backend-test/.env
```
修改内容：
```properties
PORT=8081
DB_PATH=./data/wqt_test.db
```

启动测试服：
```bash
screen -S wqt-test
cd ~/wqt-auth-backend-test
npm run dev
# 按 Ctrl+A, D 挂起
```

---

## 🔄 日常更新流程

### 更新测试服 (开发自测)
1. 进入测试目录：`cd ~/wqt-auth-backend-test`
2. 运行更新脚本：
   ```bash
   sh scripts/update.sh
   ```
3. 进入 Screen 重启服务：
   ```bash
   screen -r wqt-test
   # 按 Ctrl+C 停止当前进程
   npm run dev
   # 按 Ctrl+A, D 再次挂起
   ```

### 更新正式服 (发布上线)
确认测试服没问题后，再更新正式服。
1. 进入正式目录：`cd ~/wqt-auth-backend`
2. 运行更新脚本：
   ```bash
   sh scripts/update.sh
   ```
3. 进入 Screen 重启服务：
   ```bash
   screen -r wqt-prod
   # 按 Ctrl+C 停止当前进程
   npm run dev
   # 按 Ctrl+A, D 再次挂起
   ```

---

## 🌐 Nginx 配置参考 (域名绑定)

如果您使用 Nginx，可以添加两个 `server` 块分别反向代理到 8080 和 8081。

### 正式服配置 (game.yourdomain.com)
```nginx
server {
    listen 80;
    server_name game.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }
}
```

### 测试服配置 (test.yourdomain.com)
```nginx
server {
    listen 80;
    server_name test.yourdomain.com;

    # 建议加上简单的密码保护 (可选)
    # auth_basic "Restricted Content";
    # auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8081; # 指向测试端口
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }
}
```
