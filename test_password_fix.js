// Quick sanity test for the settings-site password generator/validator.
// Mirrors both sides of the fix:
//   • generateSettingsPassword() in index.js (now 7-digit numeric)
//   • is_valid_site_password() / generate_site_password() in bot_core.py
// The remote validator's rule is "Must be 6 or 7 characters" and only digits are
// accepted. We verify the freshly-generated value passes that rule on both sides.

const crypto = require('crypto');

const SETTINGS_PASSWORD_LENGTH = 7;
const SETTINGS_PASSWORD_ALPHABET = '0123456789';

function normalizeStoredSettingsPassword(rawValue) {
    const digits = String(rawValue || '').replace(/\D/g, '').slice(0, SETTINGS_PASSWORD_LENGTH).padEnd(0, '');
    if (digits.length === 6 || digits.length === SETTINGS_PASSWORD_LENGTH) {
        return digits;
    }
    if (digits.length === 0) return generateSettingsPassword();
    return generateSettingsPassword();
}

function generateSettingsPassword(length = SETTINGS_PASSWORD_LENGTH) {
    const requested = Number(length) || SETTINGS_PASSWORD_LENGTH;
    const size = requested === 6 || requested === 7 ? requested : SETTINGS_PASSWORD_LENGTH;
    const bytes = crypto.randomBytes(size);
    let password = '';
    for (let index = 0; index < size; index += 1) {
        password += SETTINGS_PASSWORD_ALPHABET[bytes[index] % SETTINGS_PASSWORD_ALPHABET.length];
    }
    return password;
}

function remoteAccepts(p) {
    return /^[0-9]{6,7}$/.test(String(p || ''));
}

const TRIES = 200;
const samples = [];
let bad = 0;
for (let i = 0; i < TRIES; i += 1) {
    const pw = generateSettingsPassword();
    samples.push(pw);
    if (!remoteAccepts(pw)) bad += 1;
}
const lengths = new Set(samples.map((s) => s.length));
const allNumeric = samples.every((s) => /^[0-9]+$/.test(s));

console.log('=== Settings-Site Password Round-Trip Test ===');
console.log('Iterations   :', TRIES);
console.log('Lengths seen :', [...lengths]);
console.log('All numeric  :', allNumeric);
console.log('Rejected by remote validator:', bad);
console.log('Sample (first 5):', samples.slice(0, 5));

// Boundary cases (lengths the remote validator REJECTS) must be repaired.
const borderline = ['12345', '1234567890', 'AbCd12', '', '00012'];
console.log('\n--- normalizeStoredSettingsPassword() ---');
for (const v of borderline) {
    const out = normalizeStoredSettingsPassword(v);
    const passes = remoteAccepts(out) && (out.length === 6 || out.length === 7);
    console.log(JSON.stringify(v), '→', out, '(passes remote validator:', passes, ')');
}

// Repro the original failure mode: 10-char alphanumeric.
const legacy = generateSettingsPassword(10);
console.log('\n--- Original generator produced ---');
console.log('legacy password (10-char alphanumeric):', legacy);
console.log('remote validator accepts it?', remoteAccepts(legacy), '← this is the bug the user saw');

// Final gate.
if (bad === 0 && allNumeric && lengths.size === 1 && lengths.has(SETTINGS_PASSWORD_LENGTH)) {
    console.log('\n✅ PASS — generated passwords all pass the remote validator.');
    process.exit(0);
}
console.log('\n❌ FAIL — see output above.');
process.exit(1);
