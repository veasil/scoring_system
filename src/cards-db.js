import sqlite3 from "sqlite3";
import fs from "fs";
import path from "path";

/**
 * 卡牌数据源接口定义
 * 所有数据源（SQLite, Feishu等）必须实现以下方法
 */
class ICardsSource {
    async init() { throw new Error("Method not implemented"); }
    async run(sql, params) { throw new Error("Method not implemented"); }
    async get(sql, params) { throw new Error("Method not implemented"); }
    async all(sql, params) { throw new Error("Method not implemented"); }
}

/**
 * SQLite 数据源实现
 */
class SQLiteCardsSource extends ICardsSource {
    constructor(dbPath) {
        super();
        this.dbPath = dbPath;
        this.db = null;
    }

    async init() {
        const dir = path.dirname(this.dbPath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

        this.db = new sqlite3.Database(this.dbPath);

        // Schema 定义
        await this.run(`
      CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key INTEGER UNIQUE NOT NULL,
        safety_type TEXT NOT NULL,
        event TEXT NOT NULL,
        phase TEXT,
        options_json TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        version INTEGER DEFAULT 1,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')*1000),
        updated_at INTEGER,
        deleted_at INTEGER
      );
    `);

        // 创建卡牌历史版本表
        await this.run(`
      CREATE TABLE IF NOT EXISTS card_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id INTEGER NOT NULL,
        key INTEGER NOT NULL,
        safety_type TEXT NOT NULL,
        event TEXT NOT NULL,
        phase TEXT,
        options_json TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        version INTEGER DEFAULT 1,
        version_label TEXT,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')*1000)
      );
    `);

        // 向后兼容：添加可能缺失的列
        const missingColumns = [
            { name: 'status', def: 'TEXT DEFAULT "pending"' },
            { name: 'version', def: 'INTEGER DEFAULT 1' },
            { name: 'updated_at', def: 'INTEGER' },
            { name: 'deleted_at', def: 'INTEGER' },
            { name: 'branch', def: 'TEXT DEFAULT "release"' },
            { name: 'online_id', def: 'TEXT' },
            { name: 'parent_id', def: 'INTEGER' },
            { name: 'notes', def: 'TEXT' },
            { name: 'version_label', def: 'TEXT' },
            { name: 'audio_url', def: 'TEXT' }
        ];

        for (const col of missingColumns) {
            try {
                await this.run(`ALTER TABLE cards ADD COLUMN ${col.name} ${col.def}`);
            } catch (e) {
                // 列已存在，忽略错误
            }
        }

        console.log(`✅ [SQLite] Cards database initialized: ${this.dbPath}`);
    }

    run(sql, params = []) {
        return new Promise((resolve, reject) => {
            this.db.run(sql, params, function (err) {
                if (err) reject(err);
                else resolve({ lastID: this.lastID, changes: this.changes });
            });
        });
    }

    get(sql, params = []) {
        return new Promise((resolve, reject) => {
            this.db.get(sql, params, (err, row) => {
                if (err) reject(err);
                else resolve(row);
            });
        });
    }

    all(sql, params = []) {
        return new Promise((resolve, reject) => {
            this.db.all(sql, params, (err, rows) => {
                if (err) reject(err);
                else resolve(rows);
            });
        });
    }
}

/**
 * 飞书多维表格数据源实现 (占位符)
 */
class FeishuCardsSource extends ICardsSource {
    constructor(appId, appSecret, appToken, tableId) {
        super();
        this.appId = appId;
        this.appSecret = appSecret;
        this.appToken = appToken;
        this.tableId = tableId;
        this.tenantAccessToken = null;
    }

    async init() {
        console.log(`✅ [Feishu] Initializing connection to Base: ${this.appToken}`);
        // TODO: 实现飞书认证和连接
    }

    async run(sql, params) {
        // TODO: 解析SQL并转换为飞书API调用 (增删改)
        console.log("[Feishu] Mock run:", sql, params);
        return { lastID: 0, changes: 1 };
    }

    async get(sql, params) {
        // TODO: 解析SQL并转换为飞书API调用 (查询单条)
        console.log("[Feishu] Mock get:", sql, params);
        return null;
    }

    async all(sql, params) {
        // TODO: 解析SQL并转换为飞书API调用 (查询列表)
        console.log("[Feishu] Mock all:", sql, params);
        return [];
    }
}

// --- 工厂模式 & 单例 ---

let currentSource = null;

export async function initCardsDb() {
    const sourceType = process.env.CARDS_SOURCE || 'sqlite'; // 'sqlite' or 'feishu'

    if (sourceType === 'feishu') {
        currentSource = new FeishuCardsSource(
            process.env.FEISHU_APP_ID,
            process.env.FEISHU_APP_SECRET,
            process.env.FEISHU_APP_TOKEN,
            process.env.FEISHU_TABLE_ID
        );
    } else {
        const dbPath = process.env.CARDS_DB_PATH || "./data/cards.db";
        currentSource = new SQLiteCardsSource(dbPath);
    }

    await currentSource.init();
}

// 导出与旧接口兼容的方法
export function cardsDbRun(sql, params) { return currentSource.run(sql, params); }
export function cardsDbGet(sql, params) { return currentSource.get(sql, params); }
export function cardsDbAll(sql, params) { return currentSource.all(sql, params); }
