import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}

if not BOT_TOKEN or not MONGODB_URI or not ADMIN_IDS:
    raise RuntimeError("Set BOT_TOKEN, MONGODB_URI and ADMIN_IDS in .env")

mongo = MongoClient(MONGODB_URI)
files_col = mongo["anime4u"]["telegram_files"]

ANIME_ID, SEASON, EPISODE = range(3)

def admin(update):
    return update.effective_user and update.effective_user.id in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin(update):
        return await update.message.reply_text("⛔ Not authorized.")
    await update.message.reply_text("🎬 Anime4u Upload Bot\n\nUse /add to save an episode file.")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin(update):
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text("Send the Anime ID from Turso.")
    return ANIME_ID

async def anime_id(update, context):
    context.user_data["anime_id"] = update.message.text.strip()
    await update.message.reply_text("Send the season number.")
    return SEASON

async def season(update, context):
    try:
        context.user_data["season"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Send a number, e.g. 1")
        return SEASON
    await update.message.reply_text("Send the episode number.")
    return EPISODE

async def episode(update, context):
    try:
        context.user_data["episode"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Send a number, e.g. 1")
        return EPISODE
    context.user_data["waiting_for_file"] = True
    await update.message.reply_text("Now send the episode video/document.")
    return ConversationHandler.END

async def save_file(update, context):
    if not admin(update) or not context.user_data.get("waiting_for_file"):
        return

    m = update.message
    if m.document:
        f = m.document
        file_id, file_name, file_size, media_type = f.file_id, f.file_name, f.file_size, "document"
    elif m.video:
        f = m.video
        file_id, file_name, file_size, media_type = f.file_id, getattr(f, "file_name", None), f.file_size, "video"
    else:
        return await m.reply_text("Send a video or document file.")

    doc = {
        "anime_id": context.user_data["anime_id"],
        "season": context.user_data["season"],
        "episode": context.user_data["episode"],
        "chat_id": m.chat_id,
        "message_id": m.message_id,
        "file_id": file_id,
        "file_name": file_name,
        "file_size": file_size,
        "media_type": media_type,
        "uploaded_at": datetime.now(timezone.utc),
    }
    files_col.update_one(
        {"anime_id": doc["anime_id"], "season": doc["season"], "episode": doc["episode"]},
        {"$set": doc},
        upsert=True
    )
    context.user_data.clear()
    await m.reply_text("✅ Telegram file reference saved to MongoDB.")

async def cancel(update, context):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(ConversationHandler(
    entry_points=[CommandHandler("add", add)],
    states={
        ANIME_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, anime_id)],
        SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, season)],
        EPISODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, episode)],
    },
    fallbacks=[CommandHandler("cancel", cancel)]
))
app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, save_file))

if __name__ == "__main__":
    app.run_polling(allowed_updates=Update.ALL_TYPES)
