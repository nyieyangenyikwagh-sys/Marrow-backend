import fs from 'node:fs';
import crypto from 'node:crypto';
if (fs.existsSync('.env')) throw new Error('.env already exists; keeping existing secrets');
const hex = () => crypto.randomBytes(32).toString('hex');
fs.writeFileSync('.env', `DATABASE_URL=postgresql+asyncpg://banking:banking@localhost:5432/banking_core\nREDIS_URL=redis://localhost:6379/0\nSECRET_KEY=${hex()}\nENCRYPTION_KEY=${crypto.randomBytes(32).toString('base64url')}=\nCORS_ORIGINS=http://localhost:3000\nENVIRONMENT=development\nDB_PASSWORD=${hex()}\nREDIS_PASSWORD=${hex()}\n`);
console.log('Created .env with random local secrets.');
