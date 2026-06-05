// 导入 2026 卡牌包：读 cards_2026.json -> cards(active,workbench=2026版) + card_versions(v1)
//   -> 发布到 cards_released -> 建/更新「2026版」卡牌组（非默认，玩家用汉堡菜单切换）。
//
// 用法：
//   node scripts/import_2026_cards.mjs <cards_2026.json> [--dry-run] [--group-name 2026版]
//
// DB 目标由环境变量决定（与 server 一致）：
//   CARDS_SOURCE=sqlite CARDS_DB_PATH=./data/cards.db   本地 SQLite
//   CARDS_SOURCE=postgres CARDS_DATABASE_URL/DATABASE_URL=...   生产 PG
//
// 幂等：已存在相同 card_code 的卡会跳过（不重复建卡/发布）。

import 'dotenv/config';
import fs from 'fs';
import {
  initCardsDb, cardsDbRun, cardsDbGet, cardsDbAll
} from '../src/cards-db.js';

const args = process.argv.slice(2);
const jsonPath = args.find(a => !a.startsWith('--')) || './cards_2026.json';
const DRY = args.includes('--dry-run');
const groupName = (() => {
  const i = args.indexOf('--group-name');
  return i >= 0 && args[i + 1] ? args[i + 1] : '2026版';
})();

const DIMS = ['安全力', '脑波力', '实感力', '创心力', '沟通力'];

function computeMaxScores(cardsForGroup) {
  const maxScores = {};
  for (const c of cardsForGroup) {
    const opts = c.options || {};
    const cardMax = {};
    for (const k of Object.keys(opts)) {
      const eff = opts[k].attributeEffects || {};
      for (const d of DIMS) {
        const v = Number(eff[d] || 0);
        if (v > (cardMax[d] || 0)) cardMax[d] = v;
      }
    }
    for (const d of DIMS) maxScores[d] = (maxScores[d] || 0) + (cardMax[d] || 0);
  }
  return maxScores;
}

async function main() {
  const cards = JSON.parse(fs.readFileSync(jsonPath, 'utf-8'));
  console.log(`[import] 源文件 ${jsonPath}：${cards.length} 张卡  目标=${process.env.CARDS_SOURCE || 'postgres'}  dry-run=${DRY}`);

  await initCardsDb();

  // 起始 key = 现有 MAX(key)
  const maxRow = await cardsDbGet('SELECT MAX(key) AS k FROM cards');
  let nextKey = Number(maxRow?.k || 0);
  const now = Date.now();

  const releasedIds = [];
  let created = 0, skipped = 0;

  for (const c of cards) {
    const existing = await cardsDbGet('SELECT id, current_version_id FROM cards WHERE card_code = ?', [c.card_code]);
    if (existing) {
      skipped++;
      // 已存在：尝试复用其已发布快照加入卡牌组
      const snap = await cardsDbGet(
        'SELECT id FROM cards_released WHERE card_id = ? ORDER BY id DESC LIMIT 1', [existing.id]
      );
      if (snap) releasedIds.push(snap.id);
      console.log(`  skip  ${c.card_code}（已存在 card id=${existing.id}）`);
      continue;
    }

    nextKey += 1;
    const key = nextKey;
    const optionsJson = JSON.stringify(c.options);
    const trainerJson = c.trainer_material ? JSON.stringify(c.trainer_material) : null;

    if (DRY) {
      console.log(`  [dry] 建卡 ${c.card_code} key=${key} 「${c.title}」(${c.safety_type}/${c.phase})`);
      created++;
      continue;
    }

    // 1) cards (active, 2026版)
    const cardRow = await cardsDbRun(
      `INSERT INTO cards (key, safety_type, event, phase, options_json, status, version, created_at, updated_at,
         card_code, workbench, title, guide_text, subtopic, whitepaper_ref, trainer_material_json)
       VALUES (?, ?, ?, ?, ?, 'active', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [key, c.safety_type, c.event, c.phase, optionsJson, now, now,
        c.card_code, '2026版', c.title, c.guide_text, c.subtopic, c.whitepaper_ref, trainerJson]
    );
    const cardId = cardRow.lastID;

    // 2) card_versions v1
    const verRow = await cardsDbRun(
      `INSERT INTO card_versions (card_id, key, safety_type, event, phase, options_json, version, version_label, branch, created_at,
         card_code, workbench, title, guide_text, subtopic, whitepaper_ref, trainer_material_json)
       VALUES (?, ?, ?, ?, ?, ?, 1, 'v1-2026导入', 'main', ?, ?, ?, ?, ?, ?, ?, ?)`,
      [cardId, key, c.safety_type, c.event, c.phase, optionsJson, now,
        c.card_code, '2026版', c.title, c.guide_text, c.subtopic, c.whitepaper_ref, trainerJson]
    );
    await cardsDbRun('UPDATE cards SET current_version_id = ? WHERE id = ?', [verRow.lastID, cardId]);

    // 3) 发布到 cards_released
    const relRow = await cardsDbRun(
      `INSERT INTO cards_released (card_id, key, safety_type, event, phase, options_json, card_code, title, guide_text, version_label, from_version_id, released_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '2026导入发布', ?, ?)`,
      [cardId, key, c.safety_type, c.event, c.phase, optionsJson, c.card_code, c.title, c.guide_text, verRow.lastID, now]
    );
    releasedIds.push(relRow.lastID);
    created++;
    console.log(`  ok    ${c.card_code} -> card#${cardId} key=${key} released#${relRow.lastID}`);
  }

  // 卡牌组「2026版」
  const idsJson = JSON.stringify(releasedIds);
  const maxScores = computeMaxScores(cards);
  const maxScoresJson = JSON.stringify(maxScores);

  if (DRY) {
    console.log(`\n[dry] 将建/更新卡牌组「${groupName}」，含 ${releasedIds.length} 张；maxScores=${maxScoresJson}`);
  } else {
    const grp = await cardsDbGet('SELECT id FROM card_groups WHERE name = ?', [groupName]);
    if (grp) {
      await cardsDbRun(
        'UPDATE card_groups SET released_ids_json=?, max_scores_json=?, updated_at=? WHERE id=?',
        [idsJson, maxScoresJson, now, grp.id]
      );
      console.log(`\n[import] 更新卡牌组「${groupName}」(id=${grp.id})，含 ${releasedIds.length} 张`);
    } else {
      const ins = await cardsDbRun(
        `INSERT INTO card_groups (name, description, released_ids_json, max_scores_json, is_default, created_at, updated_at)
         VALUES (?, ?, ?, ?, 0, ?, ?)`,
        [groupName, '2026 精选卡牌包（45 张）', idsJson, maxScoresJson, now, now]
      );
      console.log(`\n[import] 新建卡牌组「${groupName}」(id=${ins.lastID})，含 ${releasedIds.length} 张`);
    }
  }

  console.log(`\n[import] 完成：新建 ${created} 张，跳过 ${skipped} 张，卡牌组含 ${releasedIds.length} 张快照。`);
  process.exit(0);
}

main().catch(e => { console.error('[import] 失败:', e); process.exit(1); });
