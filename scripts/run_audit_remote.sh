#!/bin/bash
# 远程执行游戏数据审计脚本
# 用法:
#   bash scripts/run_audit_remote.sh              # 仅报告（生产）
#   bash scripts/run_audit_remote.sh --flag        # 自动标记可疑
#   bash scripts/run_audit_remote.sh --trash       # 自动标记垃圾
#   bash scripts/run_audit_remote.sh staging       # 审计 staging
#   bash scripts/run_audit_remote.sh staging --flag # staging + 标记

USER="root"
HOST="8.210.121.92"
SSH_KEY="C:/Users/BibbTwigs/.ssh/id_rsa_antigravity"
PROD_DIR="/home/admin/app/scoring_system"
STAGING_DIR="/home/admin/app/wqt-staging"

# 解析参数
ENV="prod"
EXTRA_ARGS=""
for arg in "$@"; do
  case "$arg" in
    staging) ENV="staging" ;;
    *) EXTRA_ARGS="$EXTRA_ARGS $arg" ;;
  esac
done

if [ "$ENV" = "staging" ]; then
  REMOTE_DIR="$STAGING_DIR"
  echo "🔍 审计目标: Staging ($STAGING_DIR)"
else
  REMOTE_DIR="$PROD_DIR"
  echo "🔍 审计目标: Production ($PROD_DIR)"
fi

# 上传脚本
echo "📤 上传审计脚本..."
scp -o StrictHostKeyChecking=no -i "$SSH_KEY" scripts/audit_game_data.py "$USER@$HOST:$REMOTE_DIR/scripts/"

# 远程执行
echo "🚀 开始审计..."
echo ""
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" \
  "cd $REMOTE_DIR && python3 scripts/audit_game_data.py --db ./data/wqt.db $EXTRA_ARGS"

echo ""
echo "✅ 审计完成"
