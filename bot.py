import os
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient
import libsql
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("anime4u-upload-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
}

missing = []
for name, value in {
    "BOT_TOKEN": BOT_TOKEN,
    "MONGODB_URI": MONGODB_URI,
    "TURSO_DATABASE_URL": TURSO_DATABASE_URL,
    "TURSO_AUTH_TOKEN": TURSO_AUTH_TOKEN,
}.items():
    if not value:
        missing.append(name)
if not ADMIN_IDS:
    missing.append("ADMIN_IDS")
if missing:
    raise RuntimeError("Missing environment variables: " + ", ".join(missing))

mongo = MongoClient(MONGODB_URI)
mongo_db = mongo["anime4u"]
files_col = mongo_db["telegram_files"]

turso = libsql.connect(
    TURSO_DATABASE_URL,
    auth_token=TURSO_AUTH_TOKEN
)

def init_turso():
    turso.executescript("""
    CREATE TABLE IF NOT EXISTS anime (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        synopsis TEXT,
        poster_url TEXT,
        type TEXT NOT NULL,
        release_year INTEGER,
        language TEXT,
        published INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS seasons (
        id TEXT PRIMARY KEY,
        anime_id TEXT NOT NULL,
        season_number INTEGER NOT NULL,
        title TEXT,
        UNIQUE(anime_id, season_number),
        FOREIGN KEY(anime_id) REFERENCES anime(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS episodes (
        id TEXT PRIMARY KEY,
        anime_id TEXT NOT NULL,
        season_id TEXT NOT NULL,
        episode_number INTEGER NOT NULL,
        title TEXT,
        synopsis TEXT,
        published INTEGER NOT NULL DEFAULT 0,
        UNIQUE(season_id, episode_number),
        FOREIGN KEY(anime_id) REFERENCES anime(id) ON DELETE CASCADE
    );
    """)
    turso.commit()

init_turso()

ANIME_ID, SEASON, EPISODE = range(3)

def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in ADMIN_IDS)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ You are not authorized.")
        return
    await update.message.reply_text(
        "🎬 Anime4u Upload Bot\n\n"
        "/add — add an episode file\n"
        "/cancel — cancel the current upload"
    )

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ You are not authorized.")
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text(
        "1/3 — Send the Anime ID from Turso."
    )
    return ANIME_ID

async def receive_anime_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    anime_id = update.message.text.strip()

    row = turso.execute(
        "SELECT id, title FROM anime WHERE id = ?",
        (anime_id,)
    ).fetchone()

    if not row:
        await update.message.reply_text(
            "❌ Anime ID was not found in Turso.\n"
            "Create the anime metadata first."
        )
        return ANIME_ID

    context.user_data["anime_id"] = anime_id
    context.user_data["anime_title"] = row[1]

    await update.message.reply_text(
        f"Anime: {row[1]}\n\n"
        "2/3 — Send the season number."
    )
    return SEASON

async def receive_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    try:
        season = int(update.message.text.strip())
        if season < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a positive number, e.g. 1")
        return SEASON

    context.user_data["season"] = season
    await update.message.reply_text("3/3 — Send the episode number.")
    return EPISODE

async def receive_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    try:
        episode = int(update.message.text.strip())
        if episode < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please send a positive number, e.g. 1")
        return EPISODE

    anime_id = context.user_data["anime_id"]
    season = context.user_data["season"]

    season_id = f"{anime_id}-s{season}"
    turso.execute(
        """
        INSERT INTO seasons (id, anime_id, season_number, title)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(anime_id, season_number)
        DO UPDATE SET title = excluded.title
        """,
        (season_id, anime_id, season, f"Season {season}")
    )
    turso.commit()

    context.user_data["season_id"] = season_id
    context.user_data["episode"] = episode
    context.user_data["waiting_for_file"] = True

    await update.message.reply_text(
        f"Now send Episode {episode} video/document.\n"
        f"Anime: {context.user_data['anime_title']}\n"
        f"Season: {season}"
    )
    return ConversationHandler.END

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not context.user_data.get("waiting_for_file"):
        return

    msg = update.message

    if msg.document:
        file_id = msg.document.file_id
        file_name = msg.document.file_name
        file_size = msg.document.file_size
        media_type = "document"
    elif msg.video:
        file_id = msg.video.file_id
        file_name = getattr(msg.video, "file_name", None)
        file_size = msg.video.file_size
        media_type = "video"
    else:
        await msg.reply_text("Please send a video or document file.")
        return

    anime_id = context.user_data["anime_id"]
    season = context.user_data["season"]
    episode = context.user_data["episode"]
    season_id = context.user_data["season_id"]

    # MongoDB: Telegram file reference only.
    mongo_doc = {
        "anime_id": anime_id,
        "season": season,
        "episode": episode,
        "chat_id": msg.chat_id,
        "message_id": msg.message_id,
        "file_id": file_id,
        "file_name": file_name,
        "file_size": file_size,
        "media_type": media_type,
        "uploaded_at": datetime.now(timezone.utc),
    }

    files_col.update_one(
        {"anime_id": anime_id, "season": season, "episode": episode},
        {"$set": mongo_doc},
        upsert=True
    )

    # Turso: episode metadata only. No Telegram file ID is stored here.
    episode_id = f"{anime_id}-s{season}-e{episode}"
    turso.execute(
        """
        INSERT INTO episodes
            (id, anime_id, season_id, episode_number, title, published)
        VALUES (?, ?, ?, ?, ?, 0)
        ON CONFLICT(season_id, episode_number)
        DO UPDATE SET title = excluded.title
        """,
        (
            episode_id,
            anime_id,
            season_id,
            episode,
            f"Episode {episode}"
        )
    )
    turso.commit()

    context.user_data.clear()

    await msg.reply_text(
        "✅ Upload registered!\n\n"
        "Turso → anime/season/episode metadata\n"
        "MongoDB → Telegram file_id + message reference\n\n"
        "The episode is currently unpublished."
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ANIME_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_anime_id)
            ],
            SEASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_season)
            ],
            EPISODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_episode)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conversation)
    app.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.ALL, receive_file)
    )

    log.info("Anime4u Upload Bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
