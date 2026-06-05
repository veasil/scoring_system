#!/bin/bash

# Configuration
USER="root"
HOST="8.210.121.92"
SSH_KEY="C:/Users/BibbTwigs/.ssh/id_rsa_antigravity"
STAGING_DIR="/home/admin/app/wqt-staging"
PROD_DIR="/home/admin/app/scoring_system"

# 收集部署信息
DEPLOY_TIME=$(date '+%Y-%m-%d %H:%M:%S CST')
LOG_FILENAME=$(date '+%Y-%m-%d_%H-%M-%S')_production.log
DEPLOY_USER=$(whoami)

echo "🚀 Syncing Staging to Production ($HOST)..."
echo "📝 同步信息: Staging → Production | ${DEPLOY_TIME}"

# Database Migration Check
echo "⚠️  DATABASE CHECK:"
echo "   Is there any schema change involved in this update?"
echo "   If YES, please run migration commands manually after sync."
read -p "   Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Sync aborted by user."
    exit 1
fi

# ── Pre-deploy smoke test ──────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo ""
echo "🧪 Running staging smoke tests..."
python "$SCRIPT_DIR/test_staging.py" --skip-browser --cleanup
TEST_EXIT=$?

if [ $TEST_EXIT -ne 0 ]; then
    echo ""
    echo "❌ Staging smoke tests FAILED. Fix issues before promoting."
    read -p "   Override and continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Sync aborted."
        exit 1
    fi
    echo "⚠️  Continuing despite test failures (user override)."
fi
echo ""

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" << EOF
  echo "🔄 Syncing files..."
  # Sync Staging to Prod
  # Exclude .env (Prod has its own), data (keep Prod data), venv (recreate for path consistency), node_modules (re-install/sync)
  # using rsync to copy everything except excluded
  
  rsync -av --delete --exclude '.env' --exclude 'data' --exclude 'venv' --exclude 'node_modules' $STAGING_DIR/ $PROD_DIR/
  
  echo "📦 Ensuring dependencies..."
  cd $PROD_DIR
  
  # Setup Python Venv if missing
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
  
  # Copy Systemd service files (updates if changed)
  # Ensure they are in scripts/ folder in Prod dir (synced from staging)
  cp scripts/wqt-prod.service /etc/systemd/system/
  cp scripts/wqt-prod-admin.service /etc/systemd/system/
  systemctl daemon-reload
  
  echo "🔄 Restarting Production Services..."
  systemctl enable wqt-prod
  systemctl restart wqt-prod
  systemctl enable wqt-prod-admin
  systemctl restart wqt-prod-admin

  # Fix Permissions (Force admin:admin ownership)
  echo "👮 Fixing permissions..."
  chown -R admin:admin $PROD_DIR
  
  # 生成部署日志
  echo "📝 生成部署日志..."
  mkdir -p $PROD_DIR/deploy_logs
  
  # 获取 Staging 的 Git 信息
  STAGING_GIT_COMMIT=\$(cd $STAGING_DIR && git rev-parse --short HEAD 2>/dev/null || echo "未知")
  STAGING_GIT_BRANCH=\$(cd $STAGING_DIR && git branch --show-current 2>/dev/null || echo "未知")
  PROD_GIT_COMMIT=\$(cd $PROD_DIR && git rev-parse --short HEAD 2>/dev/null || echo "未知")
  
  cat > $PROD_DIR/deploy_logs/$LOG_FILENAME << LOGEOF
==============================================
部署日志 - Production 环境
==============================================
同步时间: $DEPLOY_TIME
操作人员: $DEPLOY_USER (从本地 Windows)
部署环境: Production
同步来源: Staging → Production
Staging 分支: \${STAGING_GIT_BRANCH}
Staging 提交: \${STAGING_GIT_COMMIT}
Production 提交: \${PROD_GIT_COMMIT}
服务器IP: $HOST

----------------------------------------------
代码变更摘要 (Production 最近5次提交):
----------------------------------------------
\$(cd $PROD_DIR && git log --oneline -5 2>/dev/null || echo "无法获取 Git 历史")

----------------------------------------------
同步操作记录:
----------------------------------------------
⚠️  数据库迁移: 已确认 (用户手动确认)
✅ 文件同步完成 (Staging → Production)
   - 排除: .env, data, venv, node_modules
✅ 依赖安装完成 (Node.js + Python)
✅ Systemd 服务配置更新
✅ 服务重启完成
   - wqt-prod (API)
   - wqt-prod-admin (Admin Panel)
✅ 权限修复完成 (admin:admin)

----------------------------------------------
部署结果:
----------------------------------------------
✅ 同步成功
API URL: http://$HOST:8080 (Nginx Proxy: www.ai5000days.com)
Admin URL: http://$HOST:8501

日志文件: $PROD_DIR/deploy_logs/$LOG_FILENAME
==============================================
LOGEOF

  chown admin:admin $PROD_DIR/deploy_logs/$LOG_FILENAME
  echo "   ✅ 日志已保存到: $PROD_DIR/deploy_logs/$LOG_FILENAME"

EOF

echo "✅ Sync to Production Complete!"
echo "🌍 API: http://$HOST:8080"
echo "📊 Admin: http://$HOST:8501"
echo "📝 部署日志: $PROD_DIR/deploy_logs/$LOG_FILENAME"
