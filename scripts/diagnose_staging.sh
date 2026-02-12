#!/bin/bash
# 诊断并修复测试服初始化失败问题

USER="root"
HOST="8.210.121.92"
SSH_KEY="C:/Users/BibbTwigs/.ssh/id_rsa_antigravity"
REMOTE_DIR="/home/admin/app/wqt-staging"

echo "🔍 诊断测试服初始化失败问题..."
echo ""

# 1. 检查服务状态
echo "1️⃣ 检查服务运行状态..."
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" << 'EOF'
echo "  - wqt-staging 状态:"
systemctl status wqt-staging --no-pager -l | head -20
echo ""
echo "  - wqt-staging-admin 状态:"
systemctl status wqt-staging-admin --no-pager -l | head -20
EOF

echo ""

# 2. 检查数据库文件
echo "2️⃣ 检查数据库文件..."
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" << EOF
if [ -d "$REMOTE_DIR/data" ]; then
  echo "  ✅ data 目录存在"
  ls -lh $REMOTE_DIR/data/
else
  echo "  ❌ data 目录不存在"
fi

if [ -f "$REMOTE_DIR/data/cards.db" ]; then
  echo "  ✅ cards.db 文件存在"
  echo "  文件大小: \$(du -h $REMOTE_DIR/data/cards.db | cut -f1)"
else
  echo "  ❌ cards.db 文件不存在"
fi

if [ -f "$REMOTE_DIR/data/wqt.db" ]; then
  echo "  ✅ wqt.db 文件存在"  
  echo "  文件大小: \$(du -h $REMOTE_DIR/data/wqt.db | cut -f1)"
else
  echo "  ❌ wqt.db 文件不存在"
fi
EOF

echo ""

# 3. 测试API端点
echo "3️⃣ 测试 API 端点..."
echo "  测试 /api/cards (内部端口3001):"
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" << 'EOF'
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" http://localhost:3001/api/cards)
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS/d')
echo "  HTTP状态码: $HTTP_STATUS"
if [ "$HTTP_STATUS" = "200" ]; then
  echo "  响应内容前200字符:"
  echo "$BODY" | head -c 200
  echo ""
  CARD_COUNT=$(echo "$BODY" | grep -o '"id"' | wc -l)
  echo "  卡牌数量: $CARD_COUNT"
else
  echo "  ❌ API返回错误"
  echo "$BODY"
fi
EOF

echo ""

# 4. 检查public目录文件
echo "4️⃣ 检查 public 目录关键文件..."
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" << EOF
cd $REMOTE_DIR/public
echo "  关键JS文件:"
for file in global-state.js index.html; do
  if [ -f "\$file" ]; then
    echo "    ✅ \$file 存在 (\$(du -h \$file | cut -f1))"
  else
    echo "    ❌ \$file 缺失"
  fi
done
EOF

echo ""
echo "========================================" 
echo "诊断完成!"
echo "========================================"
echo ""
echo "💡 修复建议:"
echo "  1. 如果 cards.db 缺失,运行: bash scripts/fix_staging_db.sh"
echo "  2. 如果服务未运行,运行: ssh root@$HOST 'systemctl restart wqt-staging'"
echo "  3. 如果API返回错误,查看日志: ssh root@$HOST 'journalctl -u wqt-staging -n 100'"
