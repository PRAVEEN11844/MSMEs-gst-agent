# backend/telegram_bot.py
# Telegram bot integration for MSME GST Assistant.
# Shares the same MongoDB collections as the website dashboard.

import os
import re
import base64
import traceback
import httpx
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv
from database import gst_invoices_collection
from gst_engine import extract_gst_invoice
from gst_routes import clean_gstin, parse_num, GSTIN_REGEX

import pathlib as _pathlib
load_dotenv(next(
    (p for p in [
        _pathlib.Path(__file__).parent / ".env",
        _pathlib.Path(__file__).parent.parent / ".env",
    ] if p.exists()),
    None
))


TOKEN       = os.getenv("TELEGRAM_BOT_TOKEN", "")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


# ─── /start ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📤 Upload Invoice",     callback_data="help_upload")],
        [InlineKeyboardButton("💬 Ask About Finances", callback_data="help_ask")],
        [InlineKeyboardButton("📊 GST Summary",        callback_data="gst_summary")],
        [InlineKeyboardButton("🧾 Recent Invoices",    callback_data="recent_invoices")],
    ]
    await update.message.reply_text(
        "👋 Welcome to *MSME GST Assistant*!\n\n"
        "I can help you:\n"
        "• 📸 Extract GST data from invoice photos\n"
        "• 💬 Answer questions about your finances\n"
        "• 📊 Show your GST summary\n"
        "• 📥 Add data directly to your dashboard\n\n"
        "*Just send me an invoice photo to get started!*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ─── /summary ─────────────────────────────────────────────────────────────────

async def gst_summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_gst_summary(update.message)


async def send_gst_summary(message):
    try:
        invoices = (
            list(gst_invoices_collection.find({}, {"_id": 0}))
            if gst_invoices_collection is not None and hasattr(gst_invoices_collection, 'find')
            else []
        )

        if not invoices:
            await message.reply_text(
                "📭 No invoices found.\n\nSend me an invoice photo to get started!",
                parse_mode="Markdown",
            )
            return

        total_revenue = sum(inv.get("taxable_value") or 0 for inv in invoices)
        total_cgst    = sum(inv.get("cgst")          or 0 for inv in invoices)
        total_sgst    = sum(inv.get("sgst")          or 0 for inv in invoices)
        total_igst    = sum(inv.get("igst")          or 0 for inv in invoices)
        total_gst     = total_cgst + total_sgst + total_igst
        warnings      = sum(1 for inv in invoices if inv.get("tax_warning"))
        ocr_fallbacks = sum(1 for inv in invoices if inv.get("fallback_used"))

        text = (
            f"📊 *GST Monthly Summary*\n"
            f"{'─' * 28}\n"
            f"🧾 Invoices Processed: *{len(invoices)}*\n"
            f"💰 Total Revenue:      *₹{total_revenue:,.2f}*\n"
            f"📋 GST Liability:      *₹{total_gst:,.2f}*\n"
            f"  ├ CGST: ₹{total_cgst:,.2f}\n"
            f"  ├ SGST: ₹{total_sgst:,.2f}\n"
            f"  └ IGST: ₹{total_igst:,.2f}\n"
            f"{'─' * 28}\n"
        )
        if warnings:
            text += f"⚠️ *{warnings} invoice(s) have tax warnings*\n"
        if ocr_fallbacks:
            text += f"🔍 *{ocr_fallbacks} extracted via OCR fallback*\n"

        await message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await message.reply_text(f"❌ Error fetching summary: {str(e)}")


# ─── /invoices ────────────────────────────────────────────────────────────────

async def recent_invoices_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_recent_invoices(update.message)


async def send_recent_invoices(message):
    try:
        invoices = (
            list(
                gst_invoices_collection.find({}, {"_id": 0})
                .sort("created_at", -1)
                .limit(5)
            )
            if gst_invoices_collection is not None and hasattr(gst_invoices_collection, 'find')
            else []
        )

        if not invoices:
            await message.reply_text("📭 No invoices found yet. Send me an invoice image!")
            return

        text = "🧾 *Last 5 GST Invoices*\n" + "─" * 28 + "\n"
        for inv in invoices:
            status   = "⚠️" if inv.get("tax_warning") else "✅"
            fallback = " 🔍OCR" if inv.get("fallback_used") else ""
            gst_total = (
                (inv.get("cgst") or 0)
                + (inv.get("sgst") or 0)
                + (inv.get("igst") or 0)
            )
            text += (
                f"{status} *{inv.get('invoice_number', 'N/A')}*{fallback}\n"
                f"   GSTIN: `{inv.get('gstin') or 'N/A'}`\n"
                f"   Date:  {inv.get('invoice_date') or 'N/A'}\n"
                f"   Total: ₹{inv.get('total_amount', 0):,.2f}\n"
                f"   GST:   ₹{gst_total:,.2f}\n\n"
            )

        await message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")


# ─── Photo Handler — Invoice Image ────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        "📸 Invoice received! Extracting GST data...\n⏳ Please wait..."
    )

    try:
        # Download highest-resolution photo from Telegram
        photo     = update.message.photo[-1]
        tg_file   = await context.bot.get_file(photo.file_id)
        img_bytes = await tg_file.download_as_bytearray()

        b64_data  = base64.b64encode(bytes(img_bytes)).decode("utf-8")
        mime_type = "image/jpeg"

        await msg.edit_text("🤖 Running AI extraction...")

        # Reuse your existing extraction engine
        result        = extract_gst_invoice(b64_data, mime_type)
        success       = result.get("success", False)
        fallback_used = result.get("fallback_used", False)
        data          = result.get("data", {}) or {}

        # Same validation pipeline as gst_routes.py
        raw_gstin = data.get("gstin", "") or ""
        cleaned   = clean_gstin(raw_gstin)
        data["gstin"]       = cleaned
        data["gstin_valid"] = bool(re.match(GSTIN_REGEX, cleaned))

        taxable = parse_num(data.get("taxable_value"))
        cgst    = parse_num(data.get("cgst"))
        sgst    = parse_num(data.get("sgst"))
        igst    = parse_num(data.get("igst"))
        total   = parse_num(data.get("total_amount"))
        data.update({
            "taxable_value": taxable,
            "cgst": cgst, "sgst": sgst, "igst": igst,
            "total_amount": total,
        })

        # Infer tax if breakdown is missing
        if not data.get("tax_breakdown_explicit") and total > 0 and taxable > 0:
            inferred = total - taxable
            if inferred > 0:
                data["cgst"] = round(inferred / 2, 2)
                data["sgst"] = round(inferred / 2, 2)
                data["igst"] = 0

        data["tax_warning"]  = abs((taxable + cgst + sgst + igst) - total) > 1.0
        data["created_at"]   = datetime.now().isoformat()
        data["fallback_used"] = fallback_used
        data["source"]       = "telegram"

        if not data.get("invoice_number"):
            prefix = "FB" if fallback_used else "TG"
            data["invoice_number"] = f"{prefix}-{int(datetime.now().timestamp())}"

        # Persist to the same MongoDB collection as the website
        stored = False
        if gst_invoices_collection is not None:
            try:
                gst_invoices_collection.insert_one(dict(data))
                stored = True
            except Exception as db_err:
                print(f"[Telegram] DB insert failed: {db_err}")

        status_icon = "⚠️" if data.get("tax_warning") else "✅"
        method_icon = "🔍 OCR" if fallback_used else "🤖 Gemini AI"
        stored_icon = "💾 Saved to dashboard" if stored else "⚠️ Not saved (DB error)"

        reply = (
            f"{status_icon} *Invoice Extracted!* ({method_icon})\n"
            f"{'─' * 28}\n"
            f"📄 Invoice No: `{data.get('invoice_number', 'N/A')}`\n"
            f"🏢 GSTIN:      `{data.get('gstin') or 'Not found'}`\n"
            f"📅 Date:       {data.get('invoice_date') or 'Not found'}\n"
            f"{'─' * 28}\n"
            f"💰 Taxable:    ₹{data.get('taxable_value', 0):,.2f}\n"
            f"📊 CGST:       ₹{data.get('cgst', 0):,.2f}\n"
            f"📊 SGST:       ₹{data.get('sgst', 0):,.2f}\n"
            f"📊 IGST:       ₹{data.get('igst', 0):,.2f}\n"
            f"💳 Total:      ₹{data.get('total_amount', 0):,.2f}\n"
            f"{'─' * 28}\n"
            f"{stored_icon}\n"
        )
        if data.get("tax_warning"):
            reply += "⚠️ *Tax mismatch detected — please verify*\n"
        if fallback_used:
            reply += "🔍 *OCR mode — Gemini unavailable*\n"

        keyboard = [
            [InlineKeyboardButton("📊 View Summary",   callback_data="gst_summary")],
            [InlineKeyboardButton("🧾 All Invoices",   callback_data="recent_invoices")],
            [InlineKeyboardButton("❓ Ask a Question", callback_data="help_ask")],
        ]
        await msg.edit_text(
            reply,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        traceback.print_exc()
        await msg.edit_text(
            f"❌ Extraction failed: {str(e)}\n\n"
            "Please try:\n• A clearer image\n• Better lighting\n• Full invoice visible"
        )


# ─── Text Handler — RAG Question ──────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text.strip()
    if question.startswith("/"):
        return

    msg = await update.message.reply_text("🤔 Thinking...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BACKEND_URL}/api/ask",
                json={"question": question},
                headers={"Content-Type": "application/json"},
            )
            data = response.json()

        answer = data.get("answer", "No answer found.")
        # Telegram uses single * for bold, not **
        answer = answer.replace("**", "*")

        keyboard = [
            [InlineKeyboardButton("📊 GST Summary",     callback_data="gst_summary")],
            [InlineKeyboardButton("🧾 Recent Invoices", callback_data="recent_invoices")],
        ]
        await msg.edit_text(
            f"💬 *Answer:*\n\n{answer}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        await msg.edit_text(
            f"❌ Could not process question.\nError: {str(e)[:100]}"
        )


# ─── Button Callbacks ─────────────────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "gst_summary":
        await send_gst_summary(query.message)

    elif query.data == "recent_invoices":
        await send_recent_invoices(query.message)

    elif query.data == "help_upload":
        await query.message.reply_text(
            "📸 *How to upload an invoice:*\n\n"
            "1. Take a clear photo of your invoice\n"
            "2. Make sure all text is visible\n"
            "3. Send the photo directly in this chat\n\n"
            "I'll extract GSTIN, amounts, and tax breakdown automatically!",
            parse_mode="Markdown",
        )

    elif query.data == "help_ask":
        await query.message.reply_text(
            "💬 *Questions you can ask:*\n\n"
            "• What is my total GST liability?\n"
            "• How much CGST have I collected?\n"
            "• Show me my highest invoice\n"
            "• What's my total revenue this month?\n"
            "• How many invoices do I have?\n\n"
            "Just type your question!",
            parse_mode="Markdown",
        )


# ─── Bot App Factory ──────────────────────────────────────────────────────────

def create_bot_app():
    """Build and return the configured Telegram Application, or None if token is missing."""
    if not TOKEN:
        print("[Telegram] WARNING: TELEGRAM_BOT_TOKEN not set — bot disabled")
        return None

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start",    start))
    application.add_handler(CommandHandler("summary",  gst_summary_command))
    application.add_handler(CommandHandler("invoices", recent_invoices_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(button_callback))

    return application
