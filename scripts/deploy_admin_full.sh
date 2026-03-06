#!/bin/bash

# Configuration
USER="root"
HOST="8.210.121.92"
SSH_KEY="C:/Users/BibbTwigs/.ssh/id_rsa_antigravity"
REMOTE_DIR="/home/admin/app/wqt-staging"

echo "🚀 Deploying Admin Panel Configurations to $HOST..."

# 1. Upload scripts
echo "📤 Uploading configuration files..."
scp -o StrictHostKeyChecking=no -i "$SSH_KEY" scripts/nginx_admin.conf "$USER@$HOST:$REMOTE_DIR/scripts/"
scp -o StrictHostKeyChecking=no -i "$SSH_KEY" scripts/setup_admin_domains.sh "$USER@$HOST:$REMOTE_DIR/scripts/"

# 2. Execute Setup
echo "🔧 Executing setup on server..."
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" << EOF
  cd $REMOTE_DIR
  chmod +x scripts/setup_admin_domains.sh
  ./scripts/setup_admin_domains.sh
EOF

echo "✅ Deployment script finished."
echo "👉 Check http://admin.ai5000days.com and http://admin-test.ai5000days.com"
