#!/bin/bash
# 在服务器上迁移cards数据从wqt.db到cards.db

cd /opt/wqt-auth-backend/staging

echo "📊 检查数据库状态..."
echo "wqt.db中的cards数量:"
sqlite3 data/wqt.db "SELECT COUNT(*) FROM cards"

echo "cards.db中的cards数量:"
sqlite3 data/cards.db "SELECT COUNT(*) FROM cards"

echo "🔄 开始迁移数据..."
sqlite3 data/wqt.db <<EOF
ATTACH DATABASE 'data/cards.db' AS target;
INSERT INTO target.cards (id, key, safety_type, event, phase, options_json, status, version, created_at, updated_at, deleted_at)
SELECT id, key, safety_type, event, phase, options_json, status, version, created_at, updated_at, deleted_at
FROM main.cards;
DETACH DATABASE target;
EOF

echo "✅ 迁移完成！验证结果:"
sqlite3 data/cards.db "SELECT status, COUNT(*) as count FROM cards GROUP BY status"

echo "🔄 重启staging服务..."
pm2 restart wqt-staging-backend
