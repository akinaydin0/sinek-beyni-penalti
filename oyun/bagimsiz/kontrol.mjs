// [tur3 2026-10-22, delik 4] BAĞIMSIZ KONTROL: Python koduna hiç dokunmadan, belgedeki formüllerle
// (YENI_AKIS.md, "Formüller") kaymaları, beyin tohumunu ve kaleci seed'lerini yeniden hesaplar.
// Yalnız Node'un kendi crypto modülü; paket yok.  Kullanım:
//   node kontrol.mjs <beacon.json> <taahhut.json> [<penalty_log.json> <beyin_kararlari.json>]
// Büyük tamsayılar (62 bit seed'ler) JSON.parse'ta bozulmasın diye ham metinden okunur.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

const sha = (s) => createHash('sha256').update(s, 'utf8').digest();
const U = (a, e) => {                       // (SHA-256("a|e") ilk 7 bayt + 0,5) / 2^56
  const h = sha(`${a}|${e}`); let k = 0n;
  for (let i = 0; i < 7; i++) k = (k << 8n) | BigInt(h[i]);
  return (Number(k) + 0.5) / 2 ** 56;
};
const ints = (txt, key) => {                // "key": [ ... ] dizisini ham metinden BigInt olarak oku
  const m = txt.match(new RegExp(`"${key}"\\s*:\\s*\\[([^\\]]*)\\]`));
  return m ? m[1].split(',').map((s) => BigInt(s.trim())) : null;
};
const [bPath, tPath, logPath, decPath] = process.argv.slice(2);
if (!tPath) { console.log('kullanım: node kontrol.mjs <beacon.json> <taahhut.json> [<log> <karar>]'); process.exit(2); }
const bc = JSON.parse(readFileSync(bPath, 'utf8'));
const tTxt = readFileSync(tPath, 'utf8'); const t = JSON.parse(tTxt);
const R = bc.randomness.toLowerCase(), S = t.sha256.toLowerCase();
const ks = t.payload.config.keeper_shift, n = t.payload.config.beyin.n;
let ok = true;
const imza = createHash('sha256').update(Buffer.from(bc.signature, 'hex')).digest('hex') === R;
console.log(`randomness = SHA-256(signature): ${imza ? 'EVET' : 'HAYIR'}`); ok &&= imza;
const key = `${R}|${S}`, xs = [];
for (let k = 1; k <= n; k++) {
  const mag = ks.min_m + (ks.max_m - ks.min_m) * U(key, `kick${k}|kayma_buyukluk`);
  const sign = U(key, `kick${k}|kayma_yon`) < ks.p_positive ? 1 : -1;
  xs.push(Number((sign * mag).toFixed(ks.round_decimals)));
}
const sb = parseInt(sha(`${R}|${S}|beyin|seed_base`).toString('hex').slice(0, 8), 16) % 4000000000;
const kseeds = ints(tTxt, 'keeper_seeds').map((s) => BigInt('0x' + sha(`${s}|beacon|${R}`).toString('hex').slice(0, 15)));
console.log('kaymalar (m):', xs.join(', '));
console.log('beyin seed_base:', sb, '-> trial_seed', Array.from({ length: n }, (_, i) => sb + i + 1).join(', '));
console.log('kaleci seed\'leri (beacon karışmış):', kseeds.join(', '));
if (logPath && decPath) {
  const logTxt = readFileSync(logPath, 'utf8'), log = JSON.parse(logTxt), dec = JSON.parse(readFileSync(decPath, 'utf8'));
  const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const c1 = eq(log.kicks.map((k) => k.keeper.start_x), xs);
  const c2 = eq(dec.kicks.map((k) => k.scene.keeper_x), xs);
  const c3 = dec.seed_base === sb && eq(dec.kicks.map((k) => k.trial_seed), xs.map((_, i) => sb + i + 1));
  const c4 = eq(ints(logTxt, 'keeper_seeds').map(String), kseeds.map(String));
  console.log(`log keeper.start_x = kaymalar: ${c1 ? 'AYNI' : 'FARKLI'}`);
  console.log(`beyin scene.keeper_x = kaymalar: ${c2 ? 'AYNI' : 'FARKLI'}`);
  console.log(`beyin tohumları = beacon'dan: ${c3 ? 'AYNI' : 'FARKLI'}`);
  console.log(`log keeper_seeds = beacon'dan: ${c4 ? 'AYNI' : 'FARKLI'}`);
  ok &&= c1 && c2 && c3 && c4;
}
console.log(ok ? 'BAĞIMSIZ KONTROL: TUTUYOR' : 'BAĞIMSIZ KONTROL: TUTMUYOR');
process.exit(ok ? 0 : 1);
