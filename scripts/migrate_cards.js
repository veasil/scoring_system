import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { initDb, dbRun, dbGet } from '../src/db.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CARDS_DATA_PATH = path.join(__dirname, '../public/cards-data.js');

async function migrate() {
    console.log('Starting migration...');

    // 1. Initialize DB (creates table if not exists)
    await initDb();

    // 2. Read cards data
    console.log(`Reading cards data from ${CARDS_DATA_PATH}...`);
    let content = fs.readFileSync(CARDS_DATA_PATH, 'utf-8');

    // Extract the array using regex or simple string manipulation
    // Assuming format: const CARD_DATA = [...];
    const match = content.match(/const\s+CARD_DATA\s*=\s*(\[[\s\S]*?\]);/);
    if (!match) {
        console.error('Could not find CARD_DATA array in file.');
        // Try to find without semicolon if it was omitted
        const match2 = content.match(/const\s+CARD_DATA\s*=\s*(\[[\s\S]*\])/);
        if (!match2) {
            console.error('Could not find CARD_DATA array in file (attempt 2).');
            process.exit(1);
        }
        content = match2[1];
    } else {
        content = match[1];
    }

    let cardData;
    try {
        // The file content is JS object literals, which valid JSON usually is, 
        // but keys might not be quoted in standard JS (though they are in the file I saw).
        // Let's safe-eval it using new Function if JSON.parse fails, 
        // or just use new Function which is easier for JS objects.
        // "return " + content
        const getCards = new Function(`return ${content}`);
        cardData = getCards();
    } catch (e) {
        console.error('Error parsing card data:', e);
        process.exit(1);
    }

    console.log(`Found ${cardData.length} cards.`);

    // 3. Insert into DB
    let inserted = 0;
    let skipped = 0;

    await dbRun('BEGIN TRANSACTION');

    try {
        for (const card of cardData) {
            const existing = await dbGet('SELECT id FROM cards WHERE key = ?', [card.key]);
            if (existing) {
                console.log(`Card key ${card.key} already exists. Skipping.`);
                skipped++;
                continue;
            }

            await dbRun(
                `INSERT INTO cards (key, safety_type, event, phase, options_json) VALUES (?, ?, ?, ?, ?)`,
                [
                    card.key,
                    card.safetyType, // Note: camelCase in JS, snake_case in DB
                    card.event,
                    card.phase,
                    JSON.stringify(card.options)
                ]
            );
            inserted++;
        }

        await dbRun('COMMIT');
        console.log(`Migration complete. Inserted: ${inserted}, Skipped: ${skipped}`);
    } catch (e) {
        await dbRun('ROLLBACK');
        console.error('Migration failed:', e);
        process.exit(1);
    }
}

migrate();
