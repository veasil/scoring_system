/**
 * 迁移脚本：为历史场次回算得分率
 *
 * 逻辑：
 * 1. 为所有 card_groups 计算并填充 max_scores_json（若为空）
 * 2. 对所有已结束的 game_sessions，根据最后一次 card_choice 事件的 attributesAfter
 *    和默认卡牌组的 max_scores_json，回算得分率并更新 final_score + score_details_json
 *
 * 用法: node scripts/migrate_score_rate.js
 */

import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH = process.env.DB_PATH || path.join(__dirname, '..', 'data', 'wqt.db');
const CARDS_DB_PATH = process.env.CARDS_DB_PATH || path.join(__dirname, '..', 'data', 'cards.db');

const db = new Database(DB_PATH);
const cardsDb = new Database(CARDS_DB_PATH);

// 确保新列存在
try { db.exec("ALTER TABLE game_sessions ADD COLUMN score_details_json TEXT"); } catch (_) {}
try { db.exec("ALTER TABLE game_sessions ADD COLUMN card_group_id INTEGER"); } catch (_) {}
try { cardsDb.exec("ALTER TABLE card_groups ADD COLUMN max_scores_json TEXT"); } catch (_) {}

// Step 1: 为所有 card_groups 计算 max_scores_json
console.log("📊 Step 1: 计算所有卡牌组的 max_scores_json...");
const groups = cardsDb.prepare("SELECT id, released_ids_json, max_scores_json FROM card_groups").all();

for (const group of groups) {
  if (group.max_scores_json) continue; // 已有则跳过

  let ids = [];
  try { ids = JSON.parse(group.released_ids_json || "[]"); } catch (_) {}
  if (ids.length === 0) continue;

  const placeholders = ids.map(() => "?").join(",");
  const rows = cardsDb.prepare(`SELECT options_json FROM cards_released WHERE id IN (${placeholders})`).all(...ids);

  const maxScores = {};
  for (const row of rows) {
    let options;
    try { options = JSON.parse(row.options_json); } catch (_) { continue; }
    const cardMax = {};
    for (const optKey of Object.keys(options)) {
      const effects = options[optKey]?.attributeEffects;
      if (!effects) continue;
      for (const [attr, val] of Object.entries(effects)) {
        const v = Number(val) || 0;
        if (v > (cardMax[attr] || 0)) cardMax[attr] = v;
      }
    }
    for (const [attr, val] of Object.entries(cardMax)) {
      maxScores[attr] = (maxScores[attr] || 0) + val;
    }
  }

  if (Object.keys(maxScores).length > 0) {
    cardsDb.prepare("UPDATE card_groups SET max_scores_json = ? WHERE id = ?")
      .run(JSON.stringify(maxScores), group.id);
    console.log(`  ✅ 卡牌组 #${group.id}: ${JSON.stringify(maxScores)}`);
  }
}

// Step 2: 获取默认卡牌组的 max_scores
const defaultGroup = cardsDb.prepare("SELECT id, max_scores_json FROM card_groups WHERE is_default = 1 LIMIT 1").get();
if (!defaultGroup || !defaultGroup.max_scores_json) {
  console.log("⚠️ 无默认卡牌组或 max_scores 为空，无法回算历史数据。");
  process.exit(0);
}
const defaultMaxScores = JSON.parse(defaultGroup.max_scores_json);
console.log(`\n📊 Step 2: 使用默认卡牌组 #${defaultGroup.id} 的 max_scores 回算历史场次...`);
console.log(`  理论满分: ${JSON.stringify(defaultMaxScores)}`);

// Step 3: 回算所有已结束场次
const sessions = db.prepare(`
  SELECT s.id FROM game_sessions s
  WHERE s.ended_at IS NOT NULL AND s.score_details_json IS NULL
`).all();

console.log(`  共 ${sessions.length} 个待回算场次`);

const getLastEvent = db.prepare(`
  SELECT payload FROM game_events
  WHERE session_id = ? AND type = 'card_choice'
  ORDER BY ts DESC LIMIT 1
`);

const updateSession = db.prepare(`
  UPDATE game_sessions SET final_score = ?, score_details_json = ?, card_group_id = ?
  WHERE id = ?
`);

let updated = 0;
for (const session of sessions) {
  const lastEvent = getLastEvent.get(session.id);
  if (!lastEvent || !lastEvent.payload) continue;

  let payload;
  try { payload = JSON.parse(lastEvent.payload); } catch (_) { continue; }

  const attrs = payload.attributesAfter;
  if (!attrs || typeof attrs !== 'object') continue;

  // 计算得分率
  const details = {};
  let totalRate = 0;
  let dimCount = 0;
  for (const [dim, maxVal] of Object.entries(defaultMaxScores)) {
    const actual = Number(attrs[dim] || 0);
    const rate = maxVal > 0 ? Math.min(actual / maxVal, 1) : 0;
    details[dim] = { actual, max: maxVal, rate: Math.round(rate * 10000) / 10000 };
    totalRate += rate;
    dimCount++;
  }
  const scoreRate = dimCount > 0 ? Math.round((totalRate / dimCount) * 100) : 0;

  updateSession.run(scoreRate, JSON.stringify(details), defaultGroup.id, session.id);
  updated++;
}

console.log(`\n✅ 完成! 共回算 ${updated} 个场次。`);
db.close();
cardsDb.close();
