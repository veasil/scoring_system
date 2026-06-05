/**
 * SQLite → PostgreSQL 数据迁移
 *
 * 用法（PowerShell）：
 *   $env:DATABASE_SSL="true"
 *   node scripts/migrate_sqlite_to_pg.mjs "postgres://user:pass@host:5432/wqt" ./_migration/wqt.db ./_migration/cards.db
 *
 * 步骤：
 *   1. 用 initDb() + initCardsDb() 在目标 PG 建好全部表结构（幂等）
 *   2. 逐表把 sqlite 行复制进 PG，仅迁移「sqlite 列 ∩ PG 列」交集，连同显式 id（保留外键关系）
 *   3. 重置每张表的 IDENTITY 序列到 max(id)+1，避免后续自增主键冲突
 *
 * 幂等：ON CONFLICT DO NOTHING，可重复运行。
 */
import sqlite3pkg from "sqlite3";
import pg from "pg";

const sqlite3 = sqlite3pkg.verbose();

const [, , connArg, wqtPath = "./_migration/wqt.db", cardsPath = "./_migration/cards.db"] = process.argv;
const CONN = connArg || process.env.DATABASE_URL;
if (!CONN) {
  console.error("❌ 缺少连接串。用法: node scripts/migrate_sqlite_to_pg.mjs <DATABASE_URL> [wqt.db] [cards.db]");
  process.exit(1);
}
process.env.DATABASE_URL = CONN;

// 要迁移的表（按外键依赖顺序）。wqt 库的空遗留 cards 表与 sqlite_sequence 不迁。
const WQT_TABLES = [
  "users", "organizations", "game_sessions", "game_events",
  "activities", "activity_sessions", "invite_codes", "sms_codes",
  "system_settings", "user_feedback", "user_sessions",
  "watcher_level_applications", "watcher_level_logs",
];
const CARDS_TABLES = ["cards", "card_versions", "cards_released", "card_groups"];

// 个别列类型不兼容，跳过让 PG 用默认值
const EXCLUDE_COLS = {
  system_settings: new Set(["updated_at"]), // sqlite 文本 vs PG timestamptz，交给 now() 默认
};

function openSqlite(path) {
  return new Promise((resolve, reject) => {
    const db = new sqlite3.Database(path, sqlite3.OPEN_READONLY, (err) =>
      err ? reject(err) : resolve(db)
    );
  });
}
function sqliteAll(db, sql) {
  return new Promise((resolve, reject) =>
    db.all(sql, [], (err, rows) => (err ? reject(err) : resolve(rows)))
  );
}
function sqliteTableExists(db, table) {
  return sqliteAll(db, `SELECT name FROM sqlite_master WHERE type='table' AND name='${table}'`).then(
    (r) => r.length > 0
  );
}

// Zeabur 公网 TCP 代理会随机掐断连接，所有查询走重试包装（最多 6 次，递增退避）
async function q(pool, text, params) {
  let lastErr;
  for (let attempt = 1; attempt <= 6; attempt++) {
    try {
      return await pool.query(text, params);
    } catch (e) {
      lastErr = e;
      const transient =
        /terminated unexpectedly|ECONNRESET|Connection terminated|timeout|ETIMEDOUT|EPIPE/i.test(
          e.message || ""
        );
      if (!transient) throw e;
      await new Promise((r) => setTimeout(r, 400 * attempt));
    }
  }
  throw lastErr;
}

async function pgColumns(pool, table) {
  const r = await q(
    pool,
    `SELECT column_name FROM information_schema.columns WHERE table_name = $1`,
    [table]
  );
  return new Set(r.rows.map((x) => x.column_name));
}

async function migrateTable(sdb, pool, table) {
  if (!(await sqliteTableExists(sdb, table))) {
    console.log(`  - ${table}: 源表不存在，跳过`);
    return 0;
  }
  const rows = await sqliteAll(sdb, `SELECT * FROM ${table}`);
  if (rows.length === 0) {
    console.log(`  - ${table}: 0 行`);
    return 0;
  }
  const pgCols = await pgColumns(pool, table);
  const exclude = EXCLUDE_COLS[table] || new Set();
  const cols = Object.keys(rows[0]).filter((c) => pgCols.has(c) && !exclude.has(c));
  if (cols.length === 0) {
    console.log(`  - ${table}: 无交集列，跳过`);
    return 0;
  }

  const colList = cols.map((c) => `"${c}"`).join(", ");
  const placeholders = cols.map((_, i) => `$${i + 1}`).join(", ");
  const insertSql = `INSERT INTO "${table}" (${colList}) VALUES (${placeholders}) ON CONFLICT DO NOTHING`;

  let n = 0;
  for (const row of rows) {
    await q(pool, insertSql, cols.map((c) => row[c]));
    n++;
  }

  // 重置自增序列（仅当表有 id 列）
  if (pgCols.has("id")) {
    await q(
      pool,
      `SELECT setval(pg_get_serial_sequence('${table}','id'),
              GREATEST((SELECT COALESCE(MAX(id),0) FROM "${table}"), 1))`
    );
  }
  console.log(`  ✓ ${table}: ${n} 行`);
  return n;
}

async function main() {
  console.log(`🎯 目标 PG: ${CONN.replace(/:[^:@/]+@/, ":****@")}`);

  // 1) 建表结构
  const { initDb } = await import("../src/db.js");
  const { initCardsDb } = await import("../src/cards-db.js");
  console.log("📐 初始化目标库表结构 ...");
  for (let attempt = 1; ; attempt++) {
    try {
      await initDb();
      await initCardsDb();
      break;
    } catch (e) {
      if (attempt >= 6) throw e;
      console.warn(`  建表重试 ${attempt}（${e.message}）...`);
      await new Promise((r) => setTimeout(r, 500 * attempt));
    }
  }

  const pool = new pg.Pool({
    connectionString: CONN,
    ssl: process.env.DATABASE_SSL === "true" ? { rejectUnauthorized: false } : false,
  });

  // 2) 迁移主库
  console.log(`\n📦 迁移主库 ${wqtPath}`);
  const wdb = await openSqlite(wqtPath);
  for (const t of WQT_TABLES) await migrateTable(wdb, pool, t);
  wdb.close();

  // 3) 迁移卡牌库
  console.log(`\n🎴 迁移卡牌库 ${cardsPath}`);
  const cdb = await openSqlite(cardsPath);
  for (const t of CARDS_TABLES) await migrateTable(cdb, pool, t);
  cdb.close();

  await pool.end();
  console.log("\n✅ 迁移完成");
  process.exit(0);
}

main().catch((e) => {
  console.error("❌ 迁移失败:", e);
  process.exit(1);
});
