"""
Twitter Profile Queue Bot for Telegram
=======================================
Paste Twitter/X profile links into the chat, then press "Next Profile"
to cycle through them one by one.

Setup:
  1. pip install python-telegram-bot
  2. Get a bot token from @BotFather on Telegram
  3. Replace YOUR_BOT_TOKEN below (or set env var TELEGRAM_BOT_TOKEN)
  4. Run: python twitter_profile_bot.py
"""

import os
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ── Config ──────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Regex that matches twitter.com or x.com profile URLs
TWITTER_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)/?(?:\s|$)",
    re.MULTILINE,
)


# ── Handlers ────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Introduce the bot."""
    context.user_data["profiles"] = []
    context.user_data["index"] = 0
    context.user_data["collecting"] = True

    await update.message.reply_text(
        "👋 *Twitter Profile Queue Bot*\n\n"
        "Send me Twitter/X profile links — as many as you want.\n"
        "You can send them all at once or in multiple messages.\n\n"
        "When you're done, type /done and I'll give you a button "
        "to visit each profile one by one.\n\n"
        "Commands:\n"
        "  /start  — Reset and start over\n"
        "  /done   — Finish collecting links\n"
        "  /status — See how many links are queued\n"
        "  /reset  — Clear everything and start fresh",
        parse_mode="Markdown",
    )


async def handle_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extract Twitter/X links from any message."""
    if not context.user_data.get("collecting", True):
        await update.message.reply_text(
            "You've already finished collecting. "
            "Type /reset to start a new queue."
        )
        return

    # Initialize if needed
    if "profiles" not in context.user_data:
        context.user_data["profiles"] = []
        context.user_data["index"] = 0
        context.user_data["collecting"] = True

    text = update.message.text or ""
    matches = TWITTER_URL_RE.findall(text)

    # Also catch plain lines like "@username" or just "username"
    # but only if no URLs were found — prioritize full URLs
    if not matches:
        # Try to find raw URLs that might have slight format differences
        raw_urls = re.findall(
            r"https?://(?:www\.)?(?:twitter\.com|x\.com)/\S+", text
        )
        for url in raw_urls:
            clean = url.rstrip("/,;.!?)\"'")
            if clean not in context.user_data["profiles"]:
                context.user_data["profiles"].append(clean)

        if raw_urls:
            count = len(context.user_data["profiles"])
            await update.message.reply_text(
                f"✅ Got it! Total profiles queued: *{count}*\n"
                f"Keep sending or type /done when finished.",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "🤔 I didn't find any Twitter/X links in that message.\n"
                "Send links like: https://twitter.com/username"
            )
        return

    added = 0
    for username in matches:
        url = f"https://x.com/{username}"
        if url not in context.user_data["profiles"]:
            context.user_data["profiles"].append(url)
            added += 1

    count = len(context.user_data["profiles"])
    await update.message.reply_text(
        f"✅ Added *{added}* profile(s). Total queued: *{count}*\n"
        f"Keep sending or type /done when finished.",
        parse_mode="Markdown",
    )


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop collecting and show the first profile button."""
    profiles = context.user_data.get("profiles", [])

    if not profiles:
        await update.message.reply_text(
            "You haven't sent any links yet! Send some Twitter/X profile URLs first."
        )
        return

    context.user_data["collecting"] = False
    context.user_data["index"] = 0

    total = len(profiles)
    current_url = profiles[0]
    username = current_url.rstrip("/").split("/")[-1]

    keyboard = [
        [InlineKeyboardButton(f"🔗 Open @{username}", url=current_url)],
        [InlineKeyboardButton(f"➡️ Next Profile (1/{total})", callback_data="next")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🎯 *Queue ready — {total} profiles loaded!*\n\n"
        f"Profile *1* of *{total}*: @{username}\n\n"
        f"Tap the link button to open the profile, then tap Next.",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def next_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Advance to the next profile when the button is pressed."""
    query = update.callback_query
    await query.answer()

    profiles = context.user_data.get("profiles", [])
    if not profiles:
        await query.edit_message_text("No profiles in queue. Type /start to begin.")
        return

    # Advance index
    idx = context.user_data.get("index", 0) + 1

    if idx >= len(profiles):
        await query.edit_message_text(
            "🏁 *All done!* You've gone through all "
            f"*{len(profiles)}* profiles.\n\n"
            "Type /start to load a new batch.",
            parse_mode="Markdown",
        )
        return

    context.user_data["index"] = idx
    total = len(profiles)
    current_url = profiles[idx]
    username = current_url.rstrip("/").split("/")[-1]

    keyboard = [
        [InlineKeyboardButton(f"🔗 Open @{username}", url=current_url)],
        [InlineKeyboardButton(f"➡️ Next Profile ({idx + 1}/{total})", callback_data="next")],
    ]

    # Add a "Previous" button too
    if idx > 0:
        keyboard.append(
            [InlineKeyboardButton("⬅️ Previous", callback_data="prev")]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Profile *{idx + 1}* of *{total}*: @{username}",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def prev_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to the previous profile."""
    query = update.callback_query
    await query.answer()

    profiles = context.user_data.get("profiles", [])
    idx = max(0, context.user_data.get("index", 0) - 1)
    context.user_data["index"] = idx

    total = len(profiles)
    current_url = profiles[idx]
    username = current_url.rstrip("/").split("/")[-1]

    keyboard = [
        [InlineKeyboardButton(f"🔗 Open @{username}", url=current_url)],
        [InlineKeyboardButton(f"➡️ Next Profile ({idx + 1}/{total})", callback_data="next")],
    ]
    if idx > 0:
        keyboard.append(
            [InlineKeyboardButton("⬅️ Previous", callback_data="prev")]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Profile *{idx + 1}* of *{total}*: @{username}",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current queue status."""
    profiles = context.user_data.get("profiles", [])
    idx = context.user_data.get("index", 0)
    collecting = context.user_data.get("collecting", True)

    if not profiles:
        await update.message.reply_text("Queue is empty. Send some links!")
        return

    state = "📥 Collecting" if collecting else "▶️ Browsing"
    await update.message.reply_text(
        f"*Queue Status*\n\n"
        f"State: {state}\n"
        f"Total profiles: *{len(profiles)}*\n"
        f"Current position: *{idx + 1}*",
        parse_mode="Markdown",
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear everything."""
    context.user_data.clear()
    context.user_data["profiles"] = []
    context.user_data["index"] = 0
    context.user_data["collecting"] = True

    await update.message.reply_text(
        "🔄 Queue cleared! Send new Twitter/X profile links."
    )


# ── Main ────────────────────────────────────────────────────────────

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("⚠️  Please set your bot token!")
        print("   Either replace YOUR_BOT_TOKEN in the script,")
        print("   or set the env var: export TELEGRAM_BOT_TOKEN=your_token")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("reset", reset))

    # Button callbacks
    app.add_handler(CallbackQueryHandler(next_profile, pattern="^next$"))
    app.add_handler(CallbackQueryHandler(prev_profile, pattern="^prev$"))

    # Message handler for links (catches everything that's not a command)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_links))

    print("🤖 Bot is running! Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
