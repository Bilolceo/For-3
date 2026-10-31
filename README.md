# LoveBot 🤍

Ikki kishi uchun yozilgan shaxsiy Telegram bot. Begona odam yozsa — `403 Forbidden: bu yurak band`.

| Bo'lim | Nima qiladi |
|---|---|
| 📅 **Bugungi kun** | 30 kunlik kalendar: u birinchi `/start` bosgan kundan boshlab har kuni ertalab yangi xat ochiladi, kelajakdagilari 🔒 |
| 💌 **Xatlar** | "Xafa bo'lsang och", "Sog'insang och"… — vaziyat xatlari (+ ixtiyoriy ovozli xabar). Birinchi marta ochganda senga xabar keladi |
| 💝 **Bugungi sabab** | Har kuni ertalab `reasons.txt` dan tartib bilan bittadan yuboriladi |
| 🎟 **Kuponlar** | "Bitta quchoq", "Oxirgi so'z seniki"… U ishlatsa — senga xabar, hisob DB da |
| ⏳ **Taymer** | "Biz birgamiz: X kun, Y soat, Z daqiqa" + keyingi uchrashuvgacha countdown |
| 🎮 **Viktorina** | Savollar bankidan har o'yinda 6 ta tasodifiy; birinchi g'alaba — sovg'a joylashuvi (xarita), keyingilari — 🏆 + bonus |
| 🌤 **Kayfiyat** | Har kuni kechqurun so'rov; "Charchadim" bossa — unga dalda, senga signal |
| 💌 **Soatlik xabarlar** | `content/hourly/` dagi 3 mavzu (sevgi, dalda, muammolarni birga hal qilish) — har soat, faqat 09:00–23:00, takrorlanmasdan |
| 💬 **Ikkalamiz** | Bot ikkalangizga bitta savol yuboradi; javoblar faqat ikkalangiz yozgandan keyin ochiladi |
| 🎬 **Kino kechasi** | Telegram Mini App: sinxron pleyer (biri bossa — ikkalasida), yonida WebRTC kameralar. mp4 / m3u8 / YouTube. `PUBLIC_URL` kerak |
| 🙃 **Hazillar** | `/sudo sev_meni` → *Permission granted ❤️*, `/git_log`, `/whoami`, `/ping` |
| 🛠 **Admin** (faqat sen) | `/stats`, `/send_reason`, `/send_mood`, `/preview_letters` |

## 1. O'rnatish (lokal)

```bash
cd "for <3"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Sozlash

1. **Token** — [@BotFather](https://t.me/BotFather) → `/newbot` → tokenni `.env` dagi `BOT_TOKEN` ga.
2. **O'z ID ing** — [@userinfobot](https://t.me/userinfobot) ga yoz → `MY_ID`.
3. **Uning ID si** — ikki yo'l:
   - u ham @userinfobot ga yozsin (lekin sovg'a sirligi buziladi), **yoki**
   - `HER_ID=0` qoldirib botni ishga tushir → bu **setup rejimi**: bot unga faqat ID sini ko'rsatadi, sen uni `.env` ga yozib, qayta ishga tushirasan. (Setup rejimida kunlik xabarlar yuborilmaydi.)
4. `TOGETHER_SINCE`, `NEXT_DATE`, `GIFT_LAT/LON` (Google Maps → joyni bos → koordinata) ni to'ldir.
5. Tekshir:

```bash
python -m lovebot check
```

## 3. Kontent — eng muhim qism

Hammasi `content/` papkasida — xohlagan payting o'zgartirsang bo'ladi, kod tegmaydi.

```
content/
├── letters/
│   ├── xafa_bolsang.txt      ← 1-qator: sarlavha, qolgani: xat (HTML: <b> <i> <u> ruxsat)
│   ├── xafa_bolsang.ogg      ← ixtiyoriy: ovozli xabar, xat bilan birga ketadi
│   └── ...                   ← fayl nomi = buyruq: /xafa_bolsang (faqat a-z 0-9 _)
├── reasons.txt               ← har qatorda bitta sabab (oddiy matn, <3 ham bo'laveradi)
├── comfort.txt               ← "Charchadim" bosilganda tasodifiy bittasi
├── coupons.json              ← id, emoji, title, description, limit (0 = cheksiz)
├── quiz.json                 ← question, options[], answer (0 dan indeks), hint
├── hourly/
│   ├── sevgi.txt             ← har qatorda bitta soatlik xabar; fayl nomi = mavzu
│   ├── dalda.txt             ← (yangi mavzu qo'shish: shunchaki yangi .txt fayl)
│   └── birgalikda.txt
├── game.txt                  ← "Ikkalamiz" savollari, har qatorda bitta
├── days/
│   ├── 01.txt … 30.txt       ← kalendar: 1-qator sarlavha, qolgani xat; raqamlar uzluksiz
│   ├── 07.ogg                ← ixtiyoriy ovoz (fayl nomi kun raqami bilan bir xil)
│   └── 07.jpg                ← ixtiyoriy rasm — xat shu rasm bilan keladi
├── start.jpg                 ← /start da yuboriladigan rasm (start.txt yonida bo'lsin)
└── gallery/                  ← 📸 "Bizning rasmlar": 01.jpg, 02.jpg … (nomi bo'yicha tartib)
    └── captions.txt          ← `01.jpg | rasm ostidagi so'z`
```

**Rasmlar:** `letters/xafa_bolsang.jpg`, `days/12.jpg` — xat yonida shu nomdagi rasm bo'lsa, xat rasm bilan yuboriladi (`.jpg`, `.jpeg`, `.png`). Galereyaga sizning rasmlaringizni tashla, `captions.txt` da har biriga so'z yoz. Telegram'da rasm 10 MB gacha.

`.env` da: `LOVE_INTERVAL_MINUTES` (5…240) va `LOVE_WINDOW=09:00-23:00` — soatlik xabarlar; `CALENDAR_TIME=09:00` — kalendar xati; `QUIZ_PER_GAME=6` — viktorinada savollar soni.

**Sovg'a kunidan oldin** `data/lovebot.db` ni o'chir — test paytidagi hisoblar (ochilgan xatlar, kuponlar, kalendar) tozalanadi va u haqiqatan 1-kundan boshlaydi.

Ovozli xabar: Telegram'da o'zingga voice yuborib, faylni yuklab ol (`.ogg`) va xat nomi bilan bir xil qilib qo'y.

Kontentni o'zgartirgach botni qayta ishga tushir (`python -m lovebot check` bilan tekshirib).

## 4. Ishga tushirish

```bash
python -m lovebot
```

Botga `/start` yoz → `/preview_letters` bilan hamma xatni o'zingga ko'rib chiqasan, `/send_reason` va `/send_mood` bilan kunlik xabarlarni sinab ko'rasan.

## 5. Deploy (24/7)

Render'ning tekin tarifi uxlab qoladi — bunday bot uchun **kichik VPS** ($4–5/oy) eng ishonchli.

**Variant A — systemd (VPS):**
```bash
sudo useradd -r -m lovebot
sudo mkdir -p /opt/lovebot && sudo chown lovebot:lovebot /opt/lovebot
# loyihani /opt/lovebot ga ko'chir (git clone yoki scp), .env ni ham
sudo -u lovebot bash -c 'cd /opt/lovebot && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt'
sudo cp deploy/lovebot.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now lovebot
journalctl -u lovebot -f
```

**Variant B — Docker:**
```bash
docker compose up -d --build
docker compose logs -f
```

**Variant C — Railway (GitHub'dan avtomatik deploy):**
1. [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo** → `Bilolceo/For-3`. Railway `Dockerfile` va `railway.json` ni o'zi topadi.
2. Service → **Variables** → `.env.example` dagi hamma o'zgaruvchini qo'sh (`BOT_TOKEN`, `MY_ID`, `HER_ID`, `MY_NAME`, `HER_NAME`, `TOGETHER_SINCE`, `GIFT_LAT`, `GIFT_LON`, `GIFT_TITLE`, `GIFT_ADDRESS`, `TZ`, vaqtlar). `DB_PATH` ni **yozma** — Dockerfile'da `/app/data/lovebot.db` turibdi.
3. Service → **Settings → Volumes → Add Volume** → mount path: `/app/data`. Busiz har deploy'da baza (kuponlar, kalendar kuni, ochilgan xatlar) o'chib ketadi.
4. **Settings → Networking** — hech narsa qo'shma (bot polling ishlaydi, port kerak emas). **Replicas = 1** bo'lsin — ikkita nusxa bo'lsa Telegram "Conflict" beradi.
5. Deploy → **Logs** da `Run polling for bot @for_aida_bot` chiqsa — tayyor. Har `git push` da Railway qayta deploy qiladi.

Railway'ga ko'chirgach **lokal botni to'xtat** — bir vaqtda ikkita polling bo'lmasin.

Ikkala holda ham DB `data/lovebot.db` da — uni yo'qotma (kuponlar, xatlar tarixi shu yerda).

## 🎬 Kino kechasi qanday ishlaydi

Bot bilan bir jarayonda kichik veb-server (aiohttp) ko'tariladi — `PUBLIC_URL` (Railway domeni) ko'rsatilgan bo'lsa.

- **Kirish:** Telegram `initData` imzosi bot tokeni bilan tekshiriladi; faqat `MY_ID`/`HER_ID`. "Brauzerda ochish" havolasi 12 soatlik imzolangan token bilan.
- **Sinxron:** WebSocket orqali `source / play / pause / seek`; server holatni (url, pozitsiya, vaqt) saqlaydi, kech kirgan tomon shu holatga ulanadi; har 5 s da og'ish tekshiriladi.
- **Kameralar:** WebRTC brauzerdan brauzerga (perfect negotiation), signaling — o'sha WebSocket. STUN (Google) + tekin TURN (Open Relay); o'zingizniki bo'lsa `TURN_URL/USER/PASS`.
- **Manba:** to'g'ridan-to'g'ri `.mp4` / `.m3u8` (hls.js) yoki YouTube havolasi. Streaming saytlarni (Netflix va h.k.) qo'yib bo'lmaydi.
- **Telegram ichida kamera** iOS'da ko'pincha ochilmaydi — shuning uchun "Brauzerda ochish" bor; kompyuter brauzerida eng yaxshi ishlaydi.

## Testlar

```bash
pip install -r requirements-dev.txt
pytest
```

## Tuzilma

```
lovebot/
├── __main__.py      run / check
├── config.py        .env → Settings (validatsiya bilan)
├── content.py       content/ ni o'qish va tekshirish
├── db.py            SQLite (aiosqlite)
├── keyboards.py     tugmalar, CallbackData
├── middlewares.py   whitelist + setup rejimi
├── services.py      taymer, sabab, xat yuborish — toza mantiq
├── scheduler.py     APScheduler: kunlik sabab va kayfiyat
└── handlers/        start, letters, reasons, coupons, timer, quiz, mood, admin
```

## Bir maslahat

Unga **oldindan ayt**: "Charchadim" desang menga xabar keladi. Bu g'amxo'rlik — lekin bilmasa kuzatuvdek tuyulishi mumkin.
