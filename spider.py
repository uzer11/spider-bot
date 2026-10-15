import os, random, asyncio, logging
from datetime import datetime, timedelta
import aiosqlite
from telethon import TelegramClient, events, errors
from telethon.tl.functions.channels import InviteToChannelRequest

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler('bot.log', encoding='utf-8'), logging.StreamHandler()])
api_id, api_hash = 31638003, '1de53002e59bf5bf4239c21f4ff939fe'

# Прямое подключение в облаке (сессия и база лежат в корне папки проекта)
client = TelegramClient('spider_session', api_id, api_hash)

DONOR_CHAT_USERNAME, TARGET_GROUP_USERNAME = "ekapusta_official", "cap_advisor_chat"
DB_PATH = 'spider_main.db'
LINKS_POOL = ["https://t.me", "https://t.me"]

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, progrev_sent INTEGER DEFAULT 0)')
        await db.execute('CREATE TABLE IF NOT EXISTS invites (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
        await db.commit()
    logging.info("База данных успешно проверена.")

@client.on(events.NewMessage(incoming=True))
async def handle_admin_commands(event):
    if not event.is_private: return
    text = event.raw_text.strip().lower()
    
    if text == "1отчет1":
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT COUNT(*) FROM leads") as c: r = await c.fetchone(); total_leads = r[0] if r else 0
                async with db.execute("SELECT COUNT(*) FROM leads WHERE progrev_sent = 1") as c: r = await c.fetchone(); total_progrev = r[0] if r else 0
                async with db.execute("SELECT COUNT(*) FROM invites WHERE date(timestamp) = date('now', 'localtime')") as c: r = await c.fetchone(); today_invites = r[0] if r else 0
            
            report = f"📊 **ПАНЕЛЬ УПРАВЛЕНИЯ HOLDING TG-SPIDER (RAILWAY CLOUD)**\n\n🔓 Авторизация: Успешно\n🔥 Лидов в базе СУБД: **{total_leads}**\n🔄 Дожимов отправлено: **{total_progrev}**\n📈 Инвайтов сегодня: **{today_invites}**\n\n🤖 Все модули перешли в облачный автономный режим."
            await event.reply(report)
        except Exception as e:
            await event.reply(f"❌ Ошибка СУБД: {str(e)}")

@client.on(events.NewMessage)
async def catch_leads(event):
    if event.is_private:
        text = event.raw_text.strip().lower()
        if text != "1отчет1":
            current_link = random.choice(LINKS_POOL)
            if os.path.exists('msg.txt'):
                with open('msg.txt', 'r', encoding='utf-8') as f: msg_text = f.read().strip()
            else: msg_text = f"Здравствуйте! Проверенные варианты МФО в нашем канале холдинга: {current_link}"
            await asyncio.sleep(random.randint(45, 95))
            try: await event.reply(msg_text)
            except Exception: pass
        return
    text_lower = event.raw_text.lower()
    if any(word in text_lower for word in ["займ", "в долг", "кредит", "микрозайм"]):
        sender = await event.get_sender()
        if not sender or not sender.id: return
        username = sender.username if sender.username else "NoUsername"
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT id FROM leads WHERE user_id = ?", (sender.id,)) as cursor: exists = await cursor.fetchone()
            if exists: return
            await db.execute("INSERT INTO leads (user_id, username, text, progrev_sent) VALUES (?, ?, ?, 0)", (sender.id, username, event.raw_text))
            await db.commit()

async def autonomous_inviter():
    while True:
        if not client.is_connected(): await asyncio.sleep(10); continue
        try:
            if not (9 <= datetime.now().hour <= 21): await asyncio.sleep(1800); continue
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT COUNT(*) FROM invites WHERE date(timestamp) = date('now', 'localtime')") as cursor: r = await cursor.fetchone(); today_count = r[0] if r else 0
            if today_count >= random.randint(9, 12): await asyncio.sleep(3600); continue
            donor_entity = await client.get_entity(DONOR_CHAT_USERNAME)
            target_entity = await client.get_entity(TARGET_GROUP_USERNAME)
            participants = await client.get_participants(donor_entity, limit=100)
            for user in participants:
                if user.bot or not user.username: continue
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT id FROM invites WHERE user_id = ?", (user.id,)) as cursor: already_invited = await cursor.fetchone()
                if already_invited: continue
                try:
                    await client(InviteToChannelRequest(target_entity, [user]))
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("INSERT INTO invites (user_id, username) VALUES (?, ?)", (user.id, user.username))
                        await db.commit()
                    await asyncio.sleep(random.randint(660, 1380)); break
                except errors.FloodWaitError as e: await asyncio.sleep(e.seconds + 60); break
                except Exception: await asyncio.sleep(60)
            await asyncio.sleep(900)
        except Exception: await asyncio.sleep(60)

async def autonomous_progrev():
    while True:
        try:
            current_link = random.choice(LINKS_POOL)
            two_days_ago = (datetime.utcnow() - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT id, user_id, username FROM leads WHERE progrev_sent = 0 AND timestamp <= ?", (two_days_ago,)) as cursor: leads_to_progrev = await cursor.fetchall()
            for lead_id, user_id, username in leads_to_progrev:
                try:
                    await client.send_message(user_id, f"Здравствуйте! Базы МФО обновились, выдача под 0% тут: {current_link}")
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("UPDATE leads SET progrev_sent = 1 WHERE id = ?", (lead_id,)); await db.commit()
                    await asyncio.sleep(random.randint(60, 150))
                except Exception:
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("UPDATE leads SET progrev_sent = 1 WHERE id = ?", (lead_id,)); await db.commit()
            await asyncio.sleep(1800)
        except Exception: await asyncio.sleep(60)

async def main():
    await init_db()
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logging.error("Критическая ошибка: Сессия не авторизована!")
            return
        asyncio.create_task(autonomous_inviter())
        asyncio.create_task(autonomous_progrev())
        logging.info("Система Holding TG-SPIDER успешно запущенна в вечном облаке.")
        await client.run_until_disconnected()
    except Exception as e: logging.error(f"Сбой сети: {e}")

if __name__ == '__main__':
    asyncio.run(main())
