import fetch from 'node-fetch';

const BASE_URL = 'http://127.0.0.1:8082';
const USERNAME = 'dev_user'; // You might need to adjust this based on your dev user setup or register one
const PASSWORD = 'dev123456';

async function test() {
    console.log('🚀 Starting Card Generation Workflow Test...');

    // 1. Login to get token
    console.log('\n🔐 Logging in...');
    let token;
    try {
        // Try login first
        let res = await fetch(`${BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: USERNAME, password: PASSWORD })
        });

        if (res.status === 401) {
            console.log('Login failed, trying to register...');
            // Try register
            res = await fetch(`${BASE_URL}/api/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: USERNAME, password: PASSWORD })
            });
        }

        if (!res.ok) {
            throw new Error(`Auth failed: ${res.status} ${await res.text()}`);
        }

        const data = await res.json();
        token = data.token;
        console.log('✅ Login successful. Token obtained.');
    } catch (e) {
        console.error('❌ Auth Error:', e);
        process.exit(1);
    }

    // 2. Generate Card
    console.log('\n🧠 Generating Card from LLM...');
    const topic = '校园霸凌：高年级学生抢低年级学生的零花钱';
    let generatedCard;

    try {
        const res = await fetch(`${BASE_URL}/api/admin/generate-card`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ topic })
        });

        if (!res.ok) {
            throw new Error(`Generation failed: ${res.status} ${await res.text()}`);
        }

        const data = await res.json();
        generatedCard = data.card;
        console.log('✅ Card Generated!');
        console.log('Preview:', JSON.stringify(generatedCard, null, 2).slice(0, 200) + '...');
    } catch (e) {
        console.error('❌ Generation Error:', e);
        process.exit(1);
    }

    // 3. Save Card
    console.log('\n💾 Saving Card to Database...');
    try {
        const res = await fetch(`${BASE_URL}/api/cards`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(generatedCard)
        });

        if (!res.ok) {
            throw new Error(`Save failed: ${res.status} ${await res.text()}`);
        }

        const data = await res.json();
        console.log(`✅ Card Saved! ID: ${data.id}, Key: ${data.key}`);
    } catch (e) {
        console.error('❌ Save Error:', e);
        process.exit(1);
    }

    console.log('\n🎉 Test Completed Successfully!');
}

test();
