import sqlite3 from 'sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const dbPath = path.join(__dirname, '../data/wqt.db');

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
    console.log('🚀 Starting Migration v2: Card Lifecycle...');

    try {
        // 1. Add new columns
        const columns = [
            { name: 'status', type: "TEXT DEFAULT 'pending'" }, // Default to pending for safety
            { name: 'version', type: "INTEGER DEFAULT 1" },
            { name: 'updated_at', type: "INTEGER" },
            { name: 'deleted_at', type: "INTEGER" }
        ];

        for (const col of columns) {
            try {
                await run(`ALTER TABLE cards ADD COLUMN ${col.name} ${col.type}`);
                console.log(`✅ Added column: ${col.name}`);
            } catch (e) {
                if (e.message.includes('duplicate column name')) {
                    console.log(`ℹ️ Column ${col.name} already exists. Skipping.`);
                } else {
                    throw e;
                }
            }
        }

        // 2. Data Fix: Set ID 1-45 (Original) to 'active'
        console.log('🔄 Updating status for original cards (1-45)...');
        await run("UPDATE cards SET status = 'active' WHERE id <= 45");

        // 3. Data Fix: Set ID > 45 (Generated) to 'pending' if status is default
        // We can just explicitly set them to pending to be sure (or leave as default)
        // Let's ensure anything else is pending
        await run("UPDATE cards SET status = 'pending' WHERE id > 45 AND status IS NULL");

        console.log('✅ Migration v2 Completed Successfully!');
        process.exit(0);

    } catch (e) {
        console.error('❌ Migration Failed:', e);
        process.exit(1);
    }
}

migrate();
