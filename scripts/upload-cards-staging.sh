#!/bin/bash
# 将本地的cards.db上传到staging服务器

echo "📤 上传本地cards.db到staging服务器..."

# 上传cards.db到服务器
scp data/cards.db root@8.210.121.92:/opt/wqt-auth-backend/staging/data/

echo "✅ 上传完成！"

echo "🔄 重启staging服务..."
ssh root@8.210.121.92 "cd /opt/wqt-auth-backend/staging && pm2 restart wqt-staging-backend && pm2 restart wqt-staging-admin"

echo "📊 验证cards数据..."
ssh root@8.210.121.92 "cd /opt/wqt-auth-backend/staging && sqlite3 data/cards.db 'SELECT status, COUNT(*) FROM cards GROUP BY status'"

echo "✅ 完成！请访问 http://8.210.121.92:8502 验证admin panel"
