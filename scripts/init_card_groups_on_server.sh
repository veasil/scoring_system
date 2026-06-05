#!/bin/bash
# 在服务器项目目录下执行：bash scripts/init_card_groups_on_server.sh
# 功能：用 cards-data.js 的 45 个 key 创建初版默认组 + 1.1版组

cd "$(dirname "$0")/.." || exit 1
DB="data/cards.db"

if [ ! -f "$DB" ]; then
  echo "❌ 找不到 $DB，请在项目根目录运行"
  exit 1
fi

sqlite3 "$DB" <<'SQL'
CREATE TABLE IF NOT EXISTS card_groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  released_ids_json TEXT NOT NULL,
  is_default INTEGER DEFAULT 0,
  created_by INTEGER,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')*1000),
  updated_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_card_groups_default ON card_groups(is_default);

DELETE FROM card_groups WHERE name IN ('初版卡牌', '1.1版卡牌');

-- 初版：cards-data.js 的 45 个 key，每个取最早快照
INSERT INTO card_groups (name, description, released_ids_json, is_default, updated_at)
SELECT
  '初版卡牌',
  '对应 cards-data.js 的原始 45 张卡牌',
  '[' || group_concat(id) || ']',
  1,
  strftime('%s','now')*1000
FROM (
  SELECT id FROM cards_released r1
  WHERE key IN (1,2,3,4,5,6,7,8,9,10,11,12,14,15,16,17,18,21,22,23,25,26,27,28,29,30,31,32,33,34,35,36,37,40,41,42,43,45,46,47,48,49,50,51,52)
    AND released_at = (SELECT MIN(released_at) FROM cards_released r2 WHERE r2.key = r1.key)
  ORDER BY key
);

-- 1.1版：所有 key 取最新快照
INSERT INTO card_groups (name, description, released_ids_json, is_default, updated_at)
SELECT
  '1.1版卡牌',
  '含新发布卡牌的版本',
  '[' || group_concat(id) || ']',
  0,
  strftime('%s','now')*1000
FROM (
  SELECT id FROM cards_released r1
  WHERE released_at = (SELECT MAX(released_at) FROM cards_released r2 WHERE r2.key = r1.key)
  ORDER BY key
);

-- 确保 default 正确
UPDATE card_groups SET is_default = 0 WHERE name != '初版卡牌';
UPDATE card_groups SET is_default = 1 WHERE name = '初版卡牌';

SELECT id, name, is_default, json_array_length(released_ids_json) AS card_count FROM card_groups ORDER BY id;
SQL

echo ""
echo "✅ 卡牌组初始化完成！前端默认使用「初版卡牌」"
