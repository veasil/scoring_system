#!/bin/bash
# 修复测试服数据库文件缺失问题

USER="root"
HOST="8.210.121.92"
SSH_KEY="C:/Users/BibbTwigs/.ssh/id_rsa_antigravity"
REMOTE_DIR="/home/admin/app/wqt-staging"
LOCAL_DIR="$(pwd)"

echo "🔧 修复测试服数据库文件..."

# 确保本地数据库文件存在
if [ ! -f "$LOCAL_DIR/data/cards.db" ]; then
  echo "❌ 错误:本地 data/cards.db 文件不存在!"
  echo "请先在本地生成卡牌数据库"
  exit 1
fi

echo "📤 上传数据库文件到测试服..."

# 创建远程data目录
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" "mkdir -p $REMOTE_DIR/data"

# 上传cards.db
echo "  上传 cards.db..."
scp -o StrictHostKeyChecking=no -i "$SSH_KEY" "$LOCAL_DIR/data/cards.db" "$USER@$HOST:$REMOTE_DIR/data/"

# 如果wqt.db也不存在,创建空数据库
echo "  检查并创建 wqt.db..."
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" << EOF
cd $REMOTE_DIR

# 如果wqt.db不存在,由node应用初始化
if [ ! -f "data/wqt.db" ]; then
  echo "    初始化 wqt.db..."
  # 服务启动时会自动初始化
fi

# 修复权限
echo "  修复文件权限..."
chown -R admin:admin $REMOTE_DIR/data
chmod 755 $REMOTE_DIR/data
chmod 644 $REMOTE_DIR/data/*.db

# 重启服务
echo "  重启 staging 服务..."
systemctl restart wqt-staging
systemctl restart wqt-staging-admin

# 等待服务启动
sleep 3

# 检查服务状态
echo "  检查服务状态..."
systemctl is-active wqt-staging
systemctl is-active wqt-staging-admin
EOF

echo ""
echo "✅ 修复完成!"
echo ""
echo "🔍 验证修复结果..."
echo "运行: bash scripts/diagnose_staging.sh"
