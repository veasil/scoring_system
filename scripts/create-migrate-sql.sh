#!/bin/bash
# 迁移cards数据的SQL脚本

cat > /tmp/migrate_cards.sql <<'EOF'
ATTACH DATABASE 'data/cards.db' AS target;

INSERT INTO target.cards (
  id, key, safety_type, event, phase, options_json,
  status, version, created_at, updated_at, deleted_at
)
SELECT 
  id, key, safety_type, event, phase, options_json,
  status, version, created_at, updated_at, deleted_at
FROM main.cards;

DETACH DATABASE target;
EOF

echo "✅ SQL脚本已创建: /tmp/migrate_cards.sql"
echo "请SSH到服务器并执行："
echo "  cd /opt/wqt-auth-backend/staging"
echo "  sqlite3 data/wqt.db < /tmp/migrate_cards.sql"
echo "  pm2 restart wqt-staging-backend"
