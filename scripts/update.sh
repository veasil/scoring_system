#!/bin/bash

# Simple update script for WQT Backend
# Usage: ./scripts/update.sh

echo "⬇️  Pulling latest code..."
git pull

echo "📦 Installing dependencies..."
npm install

echo "✅ Update complete!"
echo "⚠️  Don't forget to restart your server process in screen:"
echo "   Ctrl+C then 'npm run dev'"
