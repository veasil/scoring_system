#!/bin/bash

# Configuration
USER="root"
HOST="8.210.121.92"
SSH_KEY="C:/Users/BibbTwigs/.ssh/id_rsa_antigravity"
STAGING_DIR="/home/admin/app/wqt-staging"
PROD_DIR="/home/admin/app/scoring_system"

# Info
SYNC_TIME=$(date '+%Y-%m-%d %H:%M:%S CST')
LOG_FILENAME=$(date '+%Y-%m-%d_%H-%M-%S')_sync_data.log

echo "🚀 Syncing Game Data (wqt.db) from Production to Staging..."
echo "📅 Time: $SYNC_TIME"
echo "📂 Source: $PROD_DIR/data/wqt.db"
echo "📂 Dest:   $STAGING_DIR/data/wqt.db"

echo "⚠️  WARNING: This will OVERWRITE the Staging database with Production data."
read -p "   Are you sure? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Sync aborted by user."
    exit 1
fi

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$USER@$HOST" << EOF
  echo "🛑 Stopping Staging Service..."
  systemctl stop wqt-staging

  echo "📦 Backing up current Staging database..."
  # Check if file exists first
  if [ -f "$STAGING_DIR/data/wqt.db" ]; then
    cp "$STAGING_DIR/data/wqt.db" "$STAGING_DIR/data/wqt.db.bak_\$(date +%F_%H-%M-%S)"
    echo "   ✅ Backup created."
  else
    echo "   ⚠️ No existing wqt.db found in staging to backup."
  fi

  echo "🔄 Copying Production database to Staging..."
  if [ -f "$PROD_DIR/data/wqt.db" ]; then
    cp "$PROD_DIR/data/wqt.db" "$STAGING_DIR/data/wqt.db"
    echo "   ✅ Database copied."
  else
    echo "   ❌ ERROR: Production database not found at $PROD_DIR/data/wqt.db"
    exit 1
  fi

  echo "👮 Fixing permissions..."
  chown admin:admin "$STAGING_DIR/data/wqt.db"

  echo "🚀 Restarting Staging Service..."
  systemctl start wqt-staging
  
  echo "✅ Sync Complete!"
EOF

echo "🎉 Done! Staging data is now synced with Production."
