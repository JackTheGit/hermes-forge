import asyncio
import subprocess
import os
import time
from collections import defaultdict
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from dotenv import load_dotenv
from playwright.async_api import async_playwright

# =========================
# 🔐 LOAD ENV FIRST
# =========================
load_dotenv(".runtime_env")

TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE_URL = os.getenv("APP_URL_BASE")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN missing")

if not BASE_URL:
    raise ValueError("❌ APP_URL_BASE missing")

# =========================
# 📁 PATHS 
# =========================
BASE_DIR = "/home/hermes/.hermes/skills/hermes-forge-build-app"
OUTPUT_DIR = f"{BASE_DIR}/outputs"
FORGE_SCRIPT = f"{BASE_DIR}/hermes_forge.py"

os.makedirs(OUTPUT_DIR, exist_ok=True)

SCREENSHOT_PATH = f"{OUTPUT_DIR}/preview.png"

async def generate_screenshot(html_file):
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )

            page = await browser.new_page(
                viewport={"width": 1200, "height": 800}
            )

            file_url = f"file://{html_file}?t={int(time.time())}"
            print("📸 Screenshot loading:", file_url)

            await page.goto(file_url)
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1200)

            screenshot_path = f"{OUTPUT_DIR}/preview.png"
            await page.screenshot(path=screenshot_path)

            await browser.close()

        return screenshot_path

    except Exception as e:
        print("❌ Screenshot failed:", e)
        return None

# =========================
# 🧠 USER STATE
# =========================
user_state = defaultdict(lambda: {
    "last_prompt": "",
    "history": [],
    "last_logs": "",
    "last_file": "",
    "user_mode": None
})

# =========================
# 🔥 RUN FORGE
# =========================
async def run_forge(prompt, message, user_id):
    print("🔥 run_forge started")

    proc = await asyncio.create_subprocess_exec(
        "python3",
        FORGE_SCRIPT,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    proc.stdin.write(prompt.encode())
    await proc.stdin.drain()
    proc.stdin.close()

    logs = ""
    output_file = None
    progress = 0

    while True:
        line = await proc.stdout.readline()
        if not line:
            break

        decoded = line.decode(errors="ignore")
        logs += decoded
        print(decoded.strip())

        # 🔥 detect OUTPUT_FILE
        if "OUTPUT_FILE:" in decoded:
            try:
                candidate = decoded.split("OUTPUT_FILE:")[-1].strip()
                candidate = os.path.abspath(candidate)

                if os.path.exists(candidate):
                    output_file = candidate
                    print("📂 Detected file:", output_file)
            except Exception as e:
                print("⚠️ Parse error:", e)

        # progress updates
        status = ""
        if "Generating" in decoded:
            status = "🧠 Planning..."
            progress = max(progress, 1)

        elif "Success" in decoded:
            status = "⚙️ Building..."
            progress = max(progress, 2)

        elif "Saved" in decoded:
            status = "📦 Packaging..."
            progress = max(progress, 3)

        bar = "🟩" * progress + "⬜" * (3 - progress)

        try:
            await message.edit_text(f"🚧 Crafting your app...\n\n{bar}\n\n{status}")
        except:
            pass

    # 🔥 fallback if needed
    if not output_file:
        print("⚠️ Using fallback file")
        try:
            files = sorted(
                Path(OUTPUT_DIR).glob("app_*.html"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            if files:
                output_file = str(files[0])
                print("📂 Fallback file:", output_file)
        except Exception as e:
            print("❌ Fallback failed:", e)

    user_state[user_id]["last_logs"] = logs
    user_state[user_id]["last_file"] = output_file

    return logs, output_file

# =========================
# 🎯 SEND RESULT
# =========================
async def send_result(update, context, prompt, logs, output_file):
    user_id = update.effective_user.id
    state = user_state[user_id]

    state["last_prompt"] = prompt
    state["history"].append(prompt)

    if not output_file:
        await update.effective_message.reply_text("❌ Failed to generate app.")
        return

    filename = os.path.basename(output_file)

    # 🔥 cache busting
    app_url = f"{BASE_URL}/outputs/{filename}?t={int(time.time())}"

    text = f"""🎨 *Your app is ready!*

🧠 *Idea:*  
_{prompt}_

🚀 *Launch it:*  
👉 Tap below or open in browser
"""

    keyboard = [
        [InlineKeyboardButton("🚀 Open App", web_app=WebAppInfo(url=app_url))],
        [InlineKeyboardButton("🌐 Open in Browser", url=app_url)],
        [
            InlineKeyboardButton("🔄 Regenerate", callback_data="regen"),
            InlineKeyboardButton("✨ Improve", callback_data="improve"),
        ],
        [
            InlineKeyboardButton("⚡ Auto Improve x5", callback_data="auto"),
        ],
        [
            InlineKeyboardButton("📜 History", callback_data="history"),
            InlineKeyboardButton("📄 Logs", callback_data="logs"),
        ],
        [InlineKeyboardButton("💡 New Idea", callback_data="new")],
    ]

    # =========================
    # 📸 PREVIEW GENERATION
    # =========================
    preview_msg = await update.effective_message.reply_text("🎨 Generating preview...")

    screenshot = await generate_screenshot(output_file)

    try:
        await preview_msg.delete()
    except:
        pass

    if screenshot and Path(screenshot).exists():
        await update.effective_message.reply_photo(
            photo=open(screenshot, "rb"),
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.effective_message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )


# =========================
# 💬 MESSAGE HANDLER
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_state[user_id]
    text = update.message.text

    if state.get("user_mode") == "improve":
        state["user_mode"] = None
        prompt = f"{state['last_prompt']}\n\nImprove this:\n{text}"
    else:
        prompt = text

    msg = await update.message.reply_text("🚀 Starting build...")

    logs, output_file = await run_forge(prompt, msg, user_id)

    await msg.edit_text("🎉 Finalizing...")
    await asyncio.sleep(0.5)

    await send_result(update, context, prompt, logs, output_file)

# =========================
# 🔘 CALLBACK HANDLER
# =========================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    state = user_state[user_id]
    data = query.data

    if data == "regen":
        prompt = state["last_prompt"]
        msg = await query.message.reply_text("🔄 Regenerating...")
        logs, output_file = await run_forge(prompt, msg, user_id)
        await send_result(update, context, prompt, logs, output_file)

    elif data == "improve":
        state["user_mode"] = "improve"
        await query.message.reply_text("✨ What should I improve?")

    elif data == "auto":
        prompt = state["last_prompt"]
        msg = await query.message.reply_text("⚡ Auto improving x5...")

        for i in range(5):
            await msg.edit_text(f"⚡ Auto improving... {i+1}/5")
            prompt = f"{prompt}\n\nImprove UI, UX, polish features."
            logs, output_file = await run_forge(prompt, msg, user_id)

        await send_result(update, context, prompt, logs, output_file)

    elif data == "logs":
        logs = state.get("last_logs", "")[-3000:]
        await query.message.reply_text(f"```{logs}```", parse_mode="Markdown")

    elif data == "history":
        history = state["history"][-10:]
        text = "📜 Your ideas:\n\n" + "\n".join(f"• {h}" for h in history)
        await query.message.reply_text(text)

    elif data == "new":
        await query.message.reply_text("💡 Send a new idea!")

# =========================
# 🚀 START
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🚀 Telegram bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
