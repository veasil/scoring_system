#!/bin/bash

# Configuration
NGINX_CONF="scripts/nginx_admin.conf"
DEST_CONF="/etc/nginx/sites-available/wqt-admin"
LINK_CONF="/etc/nginx/sites-enabled/wqt-admin"

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "🚀 Setting up Admin Domains..."

# 1. Copy Nginx Config
if [ ! -f "$NGINX_CONF" ]; then
    echo "❌ Error: $NGINX_CONF not found. Please run from project root."
    exit 1
fi

echo "📋 Copying Nginx config..."
cp "$NGINX_CONF" "$DEST_CONF"

# 2. Enable Site
echo "🔗 Enabling site..."
ln -sf "$DEST_CONF" "$LINK_CONF"

# 3. Test & Reload Nginx
echo "Testing Nginx config..."
nginx -t

if [ $? -eq 0 ]; then
    echo "🔄 Reloading Nginx..."
    systemctl reload nginx
    echo "✅ Admin domains configured!"
    echo "   - http://admin.ai5000days.com -> 8501"
    echo "   - http://admin-test.ai5000days.com -> 8502"
    
    echo ""
    echo "🔒 To enable HTTPS (Recommended):"
    echo "   certbot --nginx -d admin.ai5000days.com -d admin-test.ai5000days.com"
else
    echo "❌ Nginx config test failed!"
    exit 1
fi
