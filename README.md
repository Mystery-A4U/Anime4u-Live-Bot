# Anime4u Upload Bot

A Python Telegram upload/admin bot for Anime4u.Tamil.

## Database split

### MongoDB — Telegram file references only
Stores:
- anime_id
- season
- episode
- chat_id
- message_id
- file_id
- file_name
- file_size
- media_type
- uploaded_at

### Turso — Anime4u metadata
Stores:
- anime
- seasons
- episodes
- synopsis/poster/type/year/language metadata

The Telegram file ID is intentionally NOT stored in Turso.

## Environment variables

Set these in deployment:

BOT_TOKEN=...
MONGODB_URI=...
TURSO_DATABASE_URL=...
TURSO_AUTH_TOKEN=...
ADMIN_IDS=...

Never commit `.env`.

## Run locally

pip install -r requirements.txt
python bot.py

## Current workflow

1. /add
2. Send an existing Anime ID from Turso
3. Send season
4. Send episode
5. Send Telegram video/document
6. Bot saves Telegram reference in MongoDB
7. Bot creates/updates season and episode metadata in Turso

Episodes are initially unpublished.
