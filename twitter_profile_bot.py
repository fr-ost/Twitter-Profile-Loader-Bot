import os
import re
import logging
import traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
 
# ── Config ──────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8753831619:AAGBJy_iSJ4s_zQ-Inmx_zyEXS4Zs8bMnBE")
 
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
 
# Disable link previews to avoid Telegram embed issues
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)
 
 
# ── Helpers ─────────────────────────────────────────────────────────
 
def build_profile_keyboard(profiles, idx):
    """Build the inline keyboard for a given profile index."""
    total = len(profiles)
    current_url = profiles[idx]
    username = current_url.rstrip("/").split("/")[-1]
 
    keyboard = [
        [InlineKeyboardButton(f"🔗 Open @{username}", url=current_url)],
    ]
 
    # Navigation row
    nav_buttons = []
    if idx > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="prev"))
    if idx < total - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data="next"))
    if nav_buttons:
        keyboard.append(nav_buttons)
 
    # Jump buttons for large queues
    if total > 10:
        jump_buttons = []
        if idx > 1:
            jump_buttons.append(InlineKeyboardButton("⏮ First", callback_data="first"))
        if idx < total - 2:
            jump_buttons.append(InlineKeyboardButton("⏭ Last", callback_data="last"))
        if jump_buttons:
            keyboard.append(jump_buttons)
 
    return InlineKeyboardMarkup(keyboard), username
 
 
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
        link_preview_options=NO_PREVIEW,
    )
 
 
async def handle_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extract Twitter/X links from any message."""
    if not context.user_data.get("collecting", True):
        await update.message.reply_text(
            "You've already finished collecting. "
            "Type /reset to start a new queue, or /done to see the buttons again.",
            link_preview_options=NO_PREVIEW,
        )
        return
 
    if "profiles" not in context.user_data:
        context.user_data["profiles"] = []
        context.user_data["index"] = 0
        context.user_data["collecting"] = True
 
    text = update.message.text or ""
    matches = TWITTER_URL_RE.findall(text)
 
    if not matches:
        raw_urls = re.findall(
            r"https?://(?:www\.)?(?:twitter\.com|x\.com)/\S+", text
        )
        for url in raw_urls:
            clean = url.rstrip("/,;.!?)\"'")
            username = clean.rstrip("/").split("/")[-1]
            normalized = f"https://x.com/{username}"
            if normalized not in context.user_data["profiles"]:
                context.user_data["profiles"].append(normalized)
 
        if raw_urls:
            count = len(context.user_data["profiles"])
            await update.message.reply_text(
                f"✅ Got it! Total profiles queued: *{count}*\n"
                f"Keep sending or type /done when finished.",
                parse_mode="Markdown",
                link_preview_options=NO_PREVIEW,
            )
        else:
            await update.message.reply_text(
                "🤔 I didn't find any Twitter/X links in that message.\n"
                "Send links like: https://x.com/username",
                link_preview_options=NO_PREVIEW,
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
        link_preview_options=NO_PREVIEW,
    )
 
 
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop collecting and show the first profile button."""
    try:
        profiles = context.user_data.get("profiles", [])
 
        if not profiles:
            await update.message.reply_text(
                "You haven't sent any links yet! Send some Twitter/X profile URLs first.",
                link_preview_options=NO_PREVIEW,
            )
            return
 
        context.user_data["collecting"] = False
        context.user_data["index"] = 0
 
        total = len(profiles)
        reply_markup, username = build_profile_keyboard(profiles, 0)
 
        await update.message.reply_text(
            f"🎯 *Queue ready — {total} profiles loaded!*\n\n"
            f"Profile *1* of *{total}*: @{username}\n\n"
            f"Tap the link to open, then tap Next.",
            parse_mode="Markdown",
            reply_markup=reply_markup,
            link_preview_options=NO_PREVIEW,
        )
        logger.info(f"/done successful — {total} profiles queued")
    except Exception as e:
        logger.error(f"Error in /done handler: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(
            f"❌ Something went wrong: {e}\nTry /reset and start over.",
            link_preview_options=NO_PREVIEW,
        )
 
 
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all navigation button presses."""
    query = update.callback_query
    await query.answer()
 
    profiles = context.user_data.get("profiles", [])
    if not profiles:
        await query.edit_message_text(
            "No profiles in queue. Type /start to begin.",
            link_preview_options=NO_PREVIEW,
        )
        return
 
    action = query.data
    idx = context.user_data.get("index", 0)
    total = len(profiles)
 
    if action == "next":
        idx = min(idx + 1, total - 1)
    elif action == "prev":
        idx = max(idx - 1, 0)
    elif action == "first":
        idx = 0
    elif action == "last":
        idx = total - 1
 
    context.user_data["index"] = idx
    reply_markup, username = build_profile_keyboard(profiles, idx)
 
    try:
        await query.edit_message_text(
            f"Profile *{idx + 1}* of *{total}*: @{username}",
            parse_mode="Markdown",
            reply_markup=reply_markup,
            link_preview_options=NO_PREVIEW,
        )
    except Exception as e:
        logger.error(f"Error updating message: {e}")
 
 
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current queue status."""
    profiles = context.user_data.get("profiles", [])
    idx = context.user_data.get("index", 0)
    collecting = context.user_data.get("collecting", True)
 
    if not profiles:
        await update.message.reply_text(
            "Queue is empty. Send some links!",
            link_preview_options=NO_PREVIEW,
        )
        return
 
    state = "📥 Collecting" if collecting else "▶️ Browsing"
    await update.message.reply_text(
        f"*Queue Status*\n\n"
        f"State: {state}\n"
        f"Total profiles: *{len(profiles)}*\n"
        f"Current position: *{idx + 1}*",
        parse_mode="Markdown",
        link_preview_options=NO_PREVIEW,
    )
 
 
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear everything."""
    context.user_data.clear()
    context.user_data["profiles"] = []
    context.user_data["index"] = 0
    context.user_data["collecting"] = True
 
    await update.message.reply_text(
        "🔄 Queue cleared! Send new Twitter/X profile links.",
        link_preview_options=NO_PREVIEW,
    )
 
 
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Exception while handling an update: {context.error}")
    logger.error(traceback.format_exc())
 
 
# ── Main ────────────────────────────────────────────────────────────
 
def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("⚠️  Please set your bot token!")
        print("   Either replace YOUR_BOT_TOKEN in the script,")
        print("   or set the env var: export TELEGRAM_BOT_TOKEN=your_token")
        return
 
    app = Application.builder().token(BOT_TOKEN).build()
 
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_links))
    app.add_error_handler(error_handler)
 
    print("🤖 Bot is running! Press Ctrl+C to stop.")
    app.run_polling()
 
 
if __name__ == "__main__":
    main()
