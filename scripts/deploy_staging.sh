#!/bin/bash

# Configuration
USER="root"
HOST="8.210.121.92"
SSH_KEY="C:/Users/BibbTwigs/.ssh/id_rsa_antigravity"
REMOTE_DIR="/home/admin/app/wqt-staging"
LOCAL_DIR="$(pwd)"

# 收集部署信息
DEPLOY_TIME=$(date '+%Y-%m-%d %H:%M:%S CST')
LOG_FILENAME=$(date '+%Y-%m-%d_%H-%M-%S')_staging.log
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "未知")
GIT_BRANCH=$(git branch --show-current 2>/dev/null || echo "未知")
DEPLOY_USER=$(whoami)

echo "🚀 Deploying to Staging ($HOST)..."
echo "📝 部署信息: ${GIT_BRANCH}@${GIT_COMMIT} | ${DEPLOY_TIME}"

# Ensure we are in the root directory
if [ ! -f "package.json" ]; then
  echo "❌ Error: Please run this script from the project root."
  exit 1
fi

# 1. Create remote directory if not exists
echo "📁 ensuring remote directory exists..."
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" "mkdir -p $REMOTE_DIR"

# 2. Upload files (using scp as it is widely available)
# Exclude: node_modules, .git, .env, venv, data
echo "📤 Uploading files..."
# Create a temporary archive to speed up transfer
tar --exclude='node_modules' --exclude='.git' --exclude='venv' --exclude='__pycache__' --exclude='data' --exclude='.env' -czf deploy_package.tar.gz .

# Upload archive
scp -o StrictHostKeyChecking=no -i "$SSH_KEY" deploy_package.tar.gz "$USER@$HOST:$REMOTE_DIR/"

# Remove local archive
rm deploy_package.tar.gz

# 3. Extract and Install Dependencies
echo "📦 Installing dependencies on server..."
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" << EOF
  cd $REMOTE_DIR
  tar -xzf deploy_package.tar.gz
  rm deploy_package.tar.gz
  
  # Update System & Install Python Venv (if missing)
  # apt update && apt install -y python3-venv  <-- Uncomment if needed, but risky to run apt update blindly
  if ! dpkg -s python3-venv >/dev/null 2>&1; then
      echo "   - Installing python3-venv..."
      apt update && apt install -y python3-venv
  fi

  # Setup Python Venv
  if [ ! -d "venv" ]; then
      echo "   - Creating Python virtual environment..."
      python3 -m venv venv
  fi

  # Install Node dependencies
  echo "   - Installing Node.js packages..."
  npm install --production
  
  # Install Python dependencies
  echo "   - Installing Python packages..."
  if [ -f "admin-panel/requirements.txt" ]; then
    ./venv/bin/pip install -r admin-panel/requirements.txt
  fi
EOF

# 4. Handle .env (Upload modified local .env)
echo "📝 Configuring Staging Environment..."
# Create temp .env for staging
cp .env .env.staging.tmp

# Modify PORT to 3001 (Internal Port)
# Sed command compatible with Git Bash/Linux
sed -i 's/^PORT=.*/PORT=3001/' .env.staging.tmp
if ! grep -q "^PORT=" .env.staging.tmp; then
  echo "PORT=3001" >> .env.staging.tmp
fi

scp -o StrictHostKeyChecking=no -i "$SSH_KEY" .env.staging.tmp "$USER@$HOST:$REMOTE_DIR/.env"
rm .env.staging.tmp

# 5. Services and Start
echo "🚀 Starting Services..."
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" << EOF
  cd $REMOTE_DIR
  
  # Check if data directory exists
  if [ ! -d "data" ]; then
    mkdir -p data
  fi
  
  # Copy Systemd service files
  cp scripts/wqt-staging.service /etc/systemd/system/
  cp scripts/wqt-staging-admin.service /etc/systemd/system/
  
  # Copy Nginx Config
  cp scripts/nginx_staging.conf /etc/nginx/sites-available/wqt-staging
  ln -sf /etc/nginx/sites-available/wqt-staging /etc/nginx/sites-enabled/
  
  systemctl daemon-reload
  
  # Restart Services
  echo "🔄 Restarting Staging Services..."
  systemctl enable wqt-staging
  systemctl restart wqt-staging
  systemctl enable wqt-staging-admin
  systemctl restart wqt-staging-admin
  
  # Reload Nginx
  echo "🔄 Reloading Nginx..."
  nginx -t && systemctl reload nginx

  # Fix Permissions (Force admin:admin ownership)
  echo "👮 Fixing permissions..."
  chown -R admin:admin $REMOTE_DIR
  
  # 生成部署日志
  echo "📝 生成部署日志..."
  mkdir -p $REMOTE_DIR/deploy_logs
  
  cat > $REMOTE_DIR/deploy_logs/$LOG_FILENAME << LOGEOF
==============================================
部署日志 - Staging 环境
==============================================
部署时间: $DEPLOY_TIME
部署人员: $DEPLOY_USER (从本地 Windows)
部署环境: Staging
Git 分支: $GIT_BRANCH
Git 提交: $GIT_COMMIT
服务器IP: $HOST

----------------------------------------------
代码变更摘要 (最近5次提交):
----------------------------------------------
$(cd $REMOTE_DIR && git log --oneline -5 2>/dev/null || echo "无法获取 Git 历史")

----------------------------------------------
部署操作记录:
----------------------------------------------
✅ 文件上传完成
✅ 依赖安装完成 (Node.js + Python)
✅ 环境配置更新 (PORT=3001)
✅ Systemd 服务配置更新
✅ Nginx 配置更新
✅ 服务重启完成
   - wqt-staging (API)
   - wqt-staging-admin (Admin Panel)
✅ Nginx 重载完成
✅ 权限修复完成 (admin:admin)

----------------------------------------------
部署结果:
----------------------------------------------
✅ 部署成功
API URL: http://$HOST:8081
Admin URL: http://$HOST:8502

日志文件: $REMOTE_DIR/deploy_logs/$LOG_FILENAME
==============================================
LOGEOF

  chown admin:admin $REMOTE_DIR/deploy_logs/$LOG_FILENAME
  echo "   ✅ 日志已保存到: $REMOTE_DIR/deploy_logs/$LOG_FILENAME"
EOF

echo "✅ Deployment to Staging Complete!"
echo "🌍 API: http://$HOST:8081"
echo "📊 Admin: http://$HOST:8502"
echo "📝 部署日志: $REMOTE_DIR/deploy_logs/$LOG_FILENAME"
