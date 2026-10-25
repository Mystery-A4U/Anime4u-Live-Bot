# Anime4u Upload Bot

MongoDB stores Telegram file references only.
Turso will store anime metadata in the next stage.

Setup:
1. Copy `.env.example` to `.env`
2. Add BOT_TOKEN, MONGODB_URI and ADMIN_IDS
3. `pip install -r requirements.txt`
4. `python bot.py`

Never commit `.env` or expose the bot token/MongoDB password.

Commands:
- /start
- /add
- /cancel
