import sqlite3 from 'sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

// 一次性迁移：会员有效期新口径上线。
//   旧口径：valid_until = NULL 表示「永久有效」
//   新口径：valid_until = NULL 表示「未开通会员，拒绝登录」
// 为避免存量账号/组织被一刀切锁死，把现有 NULL 统一迁移成「永久会员」哨兵值。
// 幂等：跑第二次没有 NULL 可改，0 changes。

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dbPath = process.env.DB_PATH || path.join(__dirname, '../data/wqt.db');

const PERMANENT_UNTIL = 253402300799000; // 与 src/account.js 保持一致

const db = new sqlite3.Database(dbPath);

function run(sql, params = []) {
  return new Promise((resolve, reject) => {
    db.run(sql, params, function (err) {
      if (err) reject(err);
      else resolve(this);
    });
  });
}

async function migrate() {
  console.log(`🚀 会员有效期迁移开始：${dbPath}`);
  try {
    // 现有组织 NULL → 永久
    const orgRes = await run(
      "UPDATE organizations SET valid_until = ?, updated_at = ? WHERE valid_until IS NULL",
      [PERMANENT_UNTIL, Date.now()]
    );
    console.log(`✅ 组织：${orgRes.changes} 个 NULL → 永久会员`);

    // 现有独立用户 NULL → 永久（企业成员的 user.valid_until 被忽略，不动）
    const userRes = await run(
      "UPDATE users SET valid_until = ? WHERE valid_until IS NULL AND enterprise_id IS NULL",
      [PERMANENT_UNTIL]
    );
    console.log(`✅ 独立用户：${userRes.changes} 个 NULL → 永久会员`);

    console.log('🎉 迁移完成（新建账号/组织默认 NULL = 未开通，符合新口径）');
  } catch (e) {
    console.error('❌ 迁移失败：', e.message);
    process.exitCode = 1;
  } finally {
    db.close();
  }
}

migrate();
