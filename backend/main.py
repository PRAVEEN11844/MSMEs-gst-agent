from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from datetime import datetime, timedelta
from typing import List, Optional
from collections import defaultdict
from bson import ObjectId
from database import transactions_collection, reminders_collection, gst_invoices_collection
import json
import base64
import traceback
import re
import os
import io as _io
import pytesseract
from PIL import Image as PILImage
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type, retry_if_exception, RetryError
from google.genai.errors import APIError, ClientError

import pathlib as _pathlib

# Load .env from backend/ dir first, then fall back to project root
_here      = _pathlib.Path(__file__).parent
_root      = _here.parent
_found_env = next(
    (p for p in [_here / ".env", _root / ".env"] if p.exists()), None
)
if _found_env:
    load_dotenv(_found_env)
else:
    load_dotenv()  # last-resort: let python-dotenv search upward


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from gst_routes import router as gst_router
app.include_router(gst_router, prefix="/api/gst", tags=["gst"])

# --------------- Telegram Bot Setup ---------------

try:
    from telegram import Update
    from telegram_bot import create_bot_app
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    # Skip obvious placeholders so the server never crashes on startup
    _token_looks_real = bool(BOT_TOKEN) and ":" in BOT_TOKEN and BOT_TOKEN != "PASTE_YOUR_NEW_TOKEN_HERE"
    telegram_app = create_bot_app() if _token_looks_real else None
    if not _token_looks_real:
        print("[Telegram] Bot disabled — set a real TELEGRAM_BOT_TOKEN in .env")
except ImportError:
    print("[Telegram] python-telegram-bot not installed — bot disabled")
    telegram_app = None

@app.on_event("startup")
async def startup():
    if telegram_app:
        try:
            await telegram_app.initialize()
            await telegram_app.start()        # ✅ THIS WAS MISSING
            print("[Telegram] Bot initialized OK")
        except Exception as e:
            print(f"[Telegram] WARNING: Bot init failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    if telegram_app:
        try:
            await telegram_app.stop()         # ✅ THIS WAS MISSING
            await telegram_app.shutdown()
        except Exception:
            pass
        print("[Telegram] Bot shut down")

@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    if not telegram_app:
        return JSONResponse(
            status_code=503,
            content={"error": "Bot not configured"}
        )
    try:
        data = await request.json()
        print(f"[Telegram] Webhook received: {json.dumps(data)[:200]}")  # ✅ ADD THIS
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return JSONResponse(content={"ok": True})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "error": str(exc)}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "data": None, "error": exc.detail}
    )

API_KEY = os.getenv("GEMINI_API_KEY", "")
client = genai.Client(api_key=API_KEY) if API_KEY else None

# --------------- Helpers ---------------

def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


# --------------- Pydantic Models ---------------

class TransactionItem(BaseModel):
    merchant: str
    amount: str
    date: str
    category: Optional[str] = None
    status: Optional[str] = None
    id: Optional[int] = None


class DetectRecurringRequest(BaseModel):
    transactions: List[TransactionItem]


class CreateReminderRequest(BaseModel):
    merchant: str
    amount: float
    frequency_days: int
    next_due_date: str


# --------------- OCR Fallback Helper ---------------

def _ocr_fallback_transactions(image_bytes: bytes) -> dict:
    """Pure Tesseract fallback when Gemini is unavailable. Always returns valid dict."""
    try:
        try:
            pytesseract.get_tesseract_version()
        except pytesseract.TesseractNotFoundError:
            common_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(common_path):
                pytesseract.pytesseract.tesseract_cmd = common_path
            else:
                raise RuntimeError("Tesseract not found")

        image = PILImage.open(_io.BytesIO(image_bytes))
        raw_text = pytesseract.image_to_string(image)
        transactions = []
        today = datetime.now().strftime("%b %d, %Y")

        for line in raw_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            amount_match = re.search(r"[\u20b9Rs\.]*\s*([\d,]+\.?\d{0,2})", line)
            if amount_match:
                try:
                    amount_val = float(amount_match.group(1).replace(",", ""))
                    if amount_val < 1:
                        continue
                    merchant = re.sub(r"[\u20b9Rs\.\d,\s]+", "", line).strip() or "Unknown"
                    transactions.append({
                        "merchant": merchant[:40],
                        "category": "Other",
                        "amount": f"\u20b9{amount_val:,.2f}",
                        "date": today,
                        "status": "pending",
                    })
                except ValueError:
                    continue

        for i, tx in enumerate(transactions):
            tx["id"] = i + 1

        print(f"[OCR Fallback] Extracted {len(transactions)} transactions from raw text")
        return {"ocr_confidence": 0.4, "transactions": transactions, "fallback_used": True}

    except Exception as e:
        print(f"[OCR Fallback] Failed completely: {e}")
        return {"ocr_confidence": 0.0, "transactions": [], "fallback_used": True, "error": str(e)}


# --------------- OCR Endpoint ---------------

EXTRACTION_PROMPT = """Analyze this financial document image (receipt, bill, bank statement, etc.) and extract all transactions.

For each transaction, extract:
- merchant: The merchant/vendor name
- category: Best-fit category (e.g., Shopping, Food & Dining, Utilities, Transport, Entertainment, Groceries, Healthcare, Education, Other)
- amount: The amount in the original currency with symbol (e.g., ₹2,499 or $45.00)
- date: The date in "MMM DD, YYYY" format (e.g., Feb 10, 2026). If no date found, use today's date.
- status: "verified" if the amount is clearly readable, "pending" if uncertain

Also provide an overall OCR confidence score between 0.0 and 1.0 based on how clearly you could read the document.

Return ONLY valid JSON in this exact format, no markdown, no code fences:
{
  "ocr_confidence": 0.95,
  "transactions": [
    {
      "merchant": "Amazon",
      "category": "Shopping",
      "amount": "₹2,499",
      "date": "Feb 10, 2026",
      "status": "verified"
    }
  ]
}"""


@app.post("/api/analyze")
async def analyze_document(file: UploadFile = File(...)):
    raw_text = ""
    try:
        contents = await file.read()
        mime_type = file.content_type or "image/png"

        print(f"[Backend] Received file: {file.filename} ({mime_type}, {len(contents)} bytes)")

        # Guard: reject if Gemini client is unavailable
        if not client:
            print("[/api/analyze] No Gemini client — using OCR fallback")
            fallback_data = _ocr_fallback_transactions(contents)
            return JSONResponse(status_code=200, content={
                "success": True, "data": fallback_data,
                "error": "Gemini API key not configured", "fallback_used": True,
            })

        # Guard: reject empty files immediately
        if not contents:
            return JSONResponse(
                status_code=400,
                content={"success": False, "data": None, "error": "Empty file received. Please upload a valid image."},
            )

        # Validate it's a readable image via PIL
        try:
            from PIL import Image as _PIL_Image
            import io as _io
            _PIL_Image.open(_io.BytesIO(contents)).verify()
        except Exception as img_err:
            print(f"[ERROR] Invalid image file: {img_err}")
            return JSONResponse(
                status_code=400,
                content={"success": False, "data": None, "error": "Invalid image file. Please upload a PNG or JPG."},
            )

        b64_data = base64.b64encode(contents).decode("utf-8")

        # Model cascade: try newer model first, fall back on quota errors
        _ANALYZE_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash"]
        response = None
        for _model in _ANALYZE_MODELS:
            try:
                @retry(
                    stop=stop_after_attempt(2),
                    wait=wait_fixed(1),
                    retry=retry_if_exception(lambda e: not isinstance(e, (ClientError, APIError)))
                )
                def generate_with_retry(m=_model):
                    return client.models.generate_content(
                        model=m,
                        contents=[
                            {
                                "role": "user",
                                "parts": [
                                    {"text": EXTRACTION_PROMPT},
                                    {
                                        "inline_data": {
                                            "mime_type": mime_type,
                                            "data": b64_data,
                                        }
                                    },
                                ],
                            }
                        ],
                    )
                response = generate_with_retry()
                print(f"[Backend] Used model: {_model}")
                break
            except (ClientError, APIError) as _e:
                _msg = str(_e)
                if "429" in _msg or "RESOURCE_EXHAUSTED" in _msg:
                    print(f"[Backend] {_model} quota exceeded — trying next")
                    continue
                raise   # non-quota error: re-raise to outer handler
            except Exception:
                raise

        if response is None:
            raise ClientError(429, {}, None)   # all models exhausted


        raw_text = response.text.strip()
        print(f"[Backend] Gemini raw response: {raw_text[:500]}")

        # Strip markdown fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            raw_text = raw_text.rsplit("```", 1)[0]
            raw_text = raw_text.strip()

        data = json.loads(raw_text)

        # Assign IDs to transactions
        for i, tx in enumerate(data.get("transactions", [])):
            tx["id"] = i + 1

        # Store transactions in MongoDB (with dedup), ignore DB errors
        try:
            new_count = 0
            for tx in data.get("transactions", []):
                existing = transactions_collection.find_one({
                    "merchant": tx["merchant"],
                    "amount": tx["amount"],
                    "date": tx["date"],
                })
                if not existing:
                    transactions_collection.insert_one(dict(tx))
                    new_count += 1
            print(f"[MongoDB] Stored {new_count} new transactions (skipped {len(data.get('transactions', [])) - new_count} duplicates)")
        except Exception as e:
            print(f"[MongoDB] Skipping DB persistence: {e}")

        print(f"[Backend] Extracted {len(data.get('transactions', []))} transactions, confidence: {data.get('ocr_confidence')}")

        return JSONResponse(content={
            "success": True,
            "data": {
                "ocr_confidence": data.get("ocr_confidence", 0.85),
                "transactions": data.get("transactions", []),
            },
            "error": None
        })

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parse error: {e} | Raw text: {raw_text[:300]}")
        return JSONResponse(
            status_code=422,
            content={"success": False, "data": None, "error": "AI returned an unreadable response. Please try again."},
        )
    except (ClientError, APIError) as e:
        msg = str(e)
        if '429' in msg or 'RESOURCE_EXHAUSTED' in msg:
            print(f"[/api/analyze] Gemini quota exceeded — switching to OCR fallback")
        elif '403' in msg:
            print(f"[/api/analyze] Gemini auth failed — switching to OCR fallback")
        else:
            print(f"[/api/analyze] Gemini ClientError — switching to OCR fallback: {msg[:150]}")

        fallback_data = _ocr_fallback_transactions(contents)
        try:
            new_count = 0
            for tx in fallback_data.get("transactions", []):
                if transactions_collection is not None:
                    existing = transactions_collection.find_one(
                        {"merchant": tx["merchant"], "amount": tx["amount"], "date": tx["date"]}
                    )
                    if not existing:
                        transactions_collection.insert_one(dict(tx))
                        new_count += 1
            print(f"[MongoDB] OCR fallback stored {new_count} transactions")
        except Exception as db_err:
            print(f"[MongoDB] OCR fallback DB store skipped: {db_err}")

        return JSONResponse(
            status_code=200,
            content={"success": True, "data": fallback_data, "error": None, "fallback_used": True},
        )
    except RetryError as e:
        inner = str(e.last_attempt.exception()) if hasattr(e, 'last_attempt') else str(e)
        print(f"[ERROR] RetryError after all attempts — switching to OCR fallback: {inner[:200]}")
        fallback_data = _ocr_fallback_transactions(contents)
        return JSONResponse(
            status_code=200,
            content={"success": True, "data": fallback_data, "error": None, "fallback_used": True},
        )
    except Exception as e:
        print(f"[ERROR] Unexpected error in /api/analyze: {str(e)}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "data": None, "error": f"Internal server error: {str(e)}", "fallback_used": False},
        )


# --------------- Get Stored Transactions ---------------

@app.get("/api/transactions")
async def get_transactions():
    """Return all stored transactions from MongoDB."""
    try:
        txns = list(transactions_collection.find({}, {"_id": 0}))
        print(f"[MongoDB] Returning {len(txns)} stored transactions")
        return JSONResponse(content={"success": True, "data": {"transactions": txns}, "error": None})
    except Exception as e:
        print(f"[MongoDB] Returning empty transactions due to error: {e}")
        return JSONResponse(content={"success": False, "data": {"transactions": []}, "error": str(e)})


# --------------- Recurring Detection ---------------

def parse_amount(amount_str: str) -> float:
    """Parse amount string like '₹2,499' or '$45.00' into a float."""
    cleaned = re.sub(r"[^0-9.\-]", "", amount_str)
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_date(date_str: str) -> Optional[datetime]:
    """Try multiple date formats to parse a date string."""
    formats = ["%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


@app.post("/api/detect-recurring")
async def detect_recurring(request: DetectRecurringRequest):
    """Detect recurring transactions based on merchant grouping, date gaps, and amount similarity."""
    try:
        # Group transactions by merchant (case-insensitive)
        merchant_groups: dict[str, list[dict]] = defaultdict(list)
        for tx in request.transactions:
            key = tx.merchant.strip().lower()
            parsed_date = parse_date(tx.date)
            parsed_amount = parse_amount(tx.amount)
            if parsed_date and parsed_amount > 0:
                merchant_groups[key].append({
                    "merchant": tx.merchant.strip(),
                    "date": parsed_date,
                    "amount": parsed_amount,
                })

        recurring = []

        for key, txns in merchant_groups.items():
            if len(txns) < 2:
                continue

            # Sort by date
            txns.sort(key=lambda t: t["date"])

            # Calculate gaps between consecutive transactions
            gaps = []
            for i in range(1, len(txns)):
                gap = (txns[i]["date"] - txns[i - 1]["date"]).days
                gaps.append(gap)

            # Check if all gaps are between 25-35 days
            if not all(25 <= g <= 35 for g in gaps):
                continue

            # Check amount variation ≤ 10%
            amounts = [t["amount"] for t in txns]
            avg_amount = sum(amounts) / len(amounts)
            if avg_amount == 0:
                continue
            max_variation = max(abs(a - avg_amount) / avg_amount for a in amounts)
            if max_variation > 0.10:
                continue

            # Compute next due date
            avg_gap = sum(gaps) / len(gaps)
            last_date = txns[-1]["date"]
            next_due = last_date + timedelta(days=round(avg_gap))

            recurring.append({
                "merchant": txns[0]["merchant"],
                "average_amount": round(avg_amount, 2),
                "frequency_days": round(avg_gap),
                "last_date": last_date.strftime("%Y-%m-%d"),
                "next_due_date": next_due.strftime("%Y-%m-%d"),
            })

        print(f"[Backend] Detected {len(recurring)} recurring payments")
        return JSONResponse(content={"success": True, "data": {"recurring": recurring}, "error": None})

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "data": None, "error": str(e)})


# --------------- Reminder CRUD ---------------

@app.post("/api/reminders")
async def create_reminder(request: CreateReminderRequest):
    """Create a new reminder in MongoDB."""
    try:
        reminder = {
            "merchant": request.merchant,
            "amount": request.amount,
            "frequency_days": request.frequency_days,
            "next_due_date": request.next_due_date,
            "enabled": True,
            "created_at": datetime.now().isoformat(),
        }
        result = reminders_collection.insert_one(reminder)
        rid = str(result.inserted_id)
        print(f"[MongoDB] Created reminder {rid} for {request.merchant}")
        return JSONResponse(content={"success": True, "data": {"id": rid}, "error": None})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "data": None, "error": str(e)})


@app.get("/api/reminders")
async def get_reminders():
    """Return all reminders from MongoDB."""
    docs = list(reminders_collection.find())
    reminders = [serialize_doc(d) for d in docs]
    return JSONResponse(content={"success": True, "data": {"reminders": reminders}, "error": None})


@app.patch("/api/reminders/{reminder_id}")
async def toggle_reminder(reminder_id: str):
    """Toggle a reminder's enabled state in MongoDB."""
    try:
        doc = reminders_collection.find_one({"_id": ObjectId(reminder_id)})
        if not doc:
            return JSONResponse(status_code=404, content={"success": False, "data": None, "error": "Reminder not found"})
        new_enabled = not doc["enabled"]
        reminders_collection.update_one(
            {"_id": ObjectId(reminder_id)},
            {"$set": {"enabled": new_enabled}}
        )
        print(f"[MongoDB] Toggled reminder {reminder_id} → enabled={new_enabled}")
        return JSONResponse(content={"success": True, "data": {"enabled": new_enabled}, "error": None})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=400, content={"success": False, "data": None, "error": str(e)})


@app.delete("/api/reminders/{reminder_id}")
async def delete_reminder(reminder_id: str):
    """Delete a reminder from MongoDB."""
    try:
        result = reminders_collection.delete_one({"_id": ObjectId(reminder_id)})
        if result.deleted_count > 0:
            print(f"[MongoDB] Deleted reminder {reminder_id}")
            return JSONResponse(content={"success": True, "data": None, "error": None})
        return JSONResponse(status_code=404, content={"success": False, "data": None, "error": "Reminder not found"})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=400, content={"success": False, "data": None, "error": str(e)})


# --------------- Due Reminders Check ---------------

@app.get("/api/check-due-reminders")
async def check_due_reminders():
    """Return reminders where next_due_date <= today from MongoDB."""
    today = datetime.now().date()
    due = []
    for doc in reminders_collection.find({"enabled": True}):
        try:
            due_date = datetime.strptime(doc["next_due_date"], "%Y-%m-%d").date()
            if due_date <= today:
                due.append(serialize_doc(doc))
        except (ValueError, KeyError):
            continue
    return JSONResponse(content={"success": True, "data": {"due_reminders": due}, "error": None})


# --------------- RAG Chat ---------------

class AskRequest(BaseModel):
    question: str


RAG_SYSTEM_PROMPT = """You are a financial data assistant for the InsightFlow AI app.

IMPORTANT RULES:
- You MUST answer ONLY using the provided transaction data below.
- You are NOT allowed to use external knowledge, general advice, or information not in the data.
- If the answer is not explicitly in the data, you MUST respond EXACTLY with:
  "No relevant data found in uploaded transactions."
- Do NOT guess or invent numbers.
- Do NOT provide general financial advice.
- Keep responses concise and use markdown bold (**text**) for emphasis.
- When referencing amounts, use the exact values from the data.

Transaction Data:
{transactions}

User Question:
{question}"""


def retrieve_relevant_transactions(question: str, transactions: list[dict]) -> list[dict]:
    """Filter transactions relevant to the user's question using smart intent detection."""
    q = question.lower().strip()

    # --- Intent detection: these intents always need ALL transactions ---
    broad_intents = [
        "total", "all", "summary", "how much", "spent", "spending",
        "average", "highest", "lowest", "top", "show", "list",
        "recurring", "monthly", "overview", "transactions",
        "every", "each", "breakdown", "categorize", "categories",
        "date", "time", "when", "detail", "bill", "receipt",
        "full", "complete", "entire",
    ]
    if any(kw in q for kw in broad_intents):
        return transactions

    # --- Merchant-specific matching ---
    merchant_names = set()
    for tx in transactions:
        merchant_names.add(tx.get("merchant", "").lower().strip())

    matched_merchants = [name for name in merchant_names if name and name in q]
    if matched_merchants:
        return [
            tx for tx in transactions
            if tx.get("merchant", "").lower().strip() in matched_merchants
        ]

    # --- Category-specific matching ---
    categories = set()
    for tx in transactions:
        categories.add(tx.get("category", "").lower().strip())
    matched_categories = [c for c in categories if c and c in q]
    if matched_categories:
        return [
            tx for tx in transactions
            if tx.get("category", "").lower().strip() in matched_categories
        ]

    # Fallback: if the question seems finance-related, return all
    finance_words = ["spent", "pay", "paid", "cost", "expense", "money", "amount", "rupee", "₹"]
    if any(w in q for w in finance_words):
        return transactions

    # No match at all — return empty
    return []


def try_compute_directly(question: str, relevant_txns: list[dict]) -> str | None:
    """Smart intent detection: compute answers directly without LLM where possible."""
    q = question.lower().strip()

    # --- Parse all amounts ---
    amounts = []
    for tx in relevant_txns:
        amt = parse_amount(tx.get("amount", "0"))
        amounts.append(amt)

    # --- Intent flags ---
    is_total = any(kw in q for kw in ["how much", "total", "sum", "spent"])
    is_date = any(kw in q for kw in ["date", "when", "day"])
    is_time = any(kw in q for kw in ["time", "clock", "hour"])
    is_detail = any(kw in q for kw in ["detail", "bill", "receipt", "full", "complete", "breakdown"])
    is_list = any(kw in q for kw in ["show", "list", "all transaction", "every transaction"])
    is_average = any(kw in q for kw in ["average", "avg", "mean"])
    is_highest = any(kw in q for kw in ["highest", "most expensive", "largest", "biggest", "max"])
    is_lowest = any(kw in q for kw in ["lowest", "cheapest", "smallest", "minimum", "min"])
    is_count = any(kw in q for kw in ["how many", "count", "number of"])

    print(f"[RAG Intent] total={is_total} date={is_date} time={is_time} detail={is_detail} list={is_list} avg={is_average} high={is_highest} low={is_lowest} count={is_count}")

    # --- Check for merchant-specific filter ---
    merchant_names = set(tx.get("merchant", "").lower().strip() for tx in relevant_txns)
    matched_merchant = None
    for name in merchant_names:
        if name and name in q:
            matched_merchant = name
            break

    # Filter to matched merchant if applicable
    if matched_merchant:
        filtered = [tx for tx in relevant_txns if tx.get("merchant", "").lower().strip() == matched_merchant]
        display_name = filtered[0].get("merchant", matched_merchant) if filtered else matched_merchant
    else:
        filtered = relevant_txns
        display_name = None

    filtered_amounts = [parse_amount(tx.get("amount", "0")) for tx in filtered]

    # ==================== INTENT HANDLERS ====================

    # INTENT: Date query
    if is_date and not is_total and not is_detail:
        dates = [tx.get("date", "N/A") for tx in filtered]
        if display_name:
            lines = [f"- **{tx.get('date', 'N/A')}** — {tx.get('amount', 'N/A')}" for tx in filtered]
            return f"Transaction dates for **{display_name}**:\n" + "\n".join(lines)
        lines = [f"- **{tx.get('date', 'N/A')}** — {tx.get('merchant', 'Unknown')} ({tx.get('amount', 'N/A')})" for tx in filtered]
        return f"All transaction dates:\n" + "\n".join(lines)

    # INTENT: Time query
    if is_time:
        times = [tx.get("time", None) for tx in filtered]
        has_time = any(t and t != "N/A" for t in times)
        if has_time:
            lines = [f"- **{tx.get('merchant', 'Unknown')}** — {tx.get('time', 'N/A')} on {tx.get('date', 'N/A')}" for tx in filtered]
            return f"Transaction times:\n" + "\n".join(lines)
        return "No time information available in the uploaded data. The document only contains dates, not specific times."

    # INTENT: Bill details / full breakdown
    if is_detail or is_list:
        lines = []
        total = 0
        for tx in filtered:
            amt = parse_amount(tx.get("amount", "0"))
            total += amt
            lines.append(
                f"- **{tx.get('merchant', 'Unknown')}** — {tx.get('amount', 'N/A')} | "
                f"{tx.get('category', 'N/A')} | {tx.get('date', 'N/A')} | "
                f"{'✅ Verified' if tx.get('status') == 'verified' else '⏳ Pending'}"
            )
        header = f"Bill details for **{display_name}**" if display_name else f"All transaction details (**{len(filtered)}** items)"
        return f"{header}:\n" + "\n".join(lines) + f"\n\n**Total: ₹{total:,.0f}**"

    # INTENT: Total / how much
    if is_total:
        valid_amounts = [a for a in filtered_amounts if a > 0]
        if not valid_amounts:
            return None
        total = sum(valid_amounts)
        if len(filtered) == 1:
            tx = filtered[0]
            return f"You spent **{tx['amount']}** at **{tx['merchant']}** on {tx.get('date', 'unknown date')}."
        if display_name:
            return f"You spent a total of **₹{total:,.0f}** on **{display_name}** across **{len(valid_amounts)} transaction(s)**."
        return f"Your total spending is **₹{total:,.0f}** across **{len(valid_amounts)} transaction(s)**."

    # INTENT: Average
    if is_average:
        valid_amounts = [a for a in filtered_amounts if a > 0]
        if not valid_amounts:
            return None
        avg = sum(valid_amounts) / len(valid_amounts)
        scope = f" for **{display_name}**" if display_name else ""
        return f"Your average transaction amount{scope} is **₹{avg:,.0f}** (across {len(valid_amounts)} transactions)."

    # INTENT: Highest
    if is_highest:
        valid = [(parse_amount(tx.get("amount", "0")), tx) for tx in filtered if parse_amount(tx.get("amount", "0")) > 0]
        if not valid:
            return None
        valid.sort(key=lambda x: x[0], reverse=True)
        _, tx = valid[0]
        return f"Your highest transaction is **{tx['amount']}** at **{tx['merchant']}** on {tx.get('date', 'unknown date')}."

    # INTENT: Lowest
    if is_lowest:
        valid = [(parse_amount(tx.get("amount", "0")), tx) for tx in filtered if parse_amount(tx.get("amount", "0")) > 0]
        if not valid:
            return None
        valid.sort(key=lambda x: x[0])
        _, tx = valid[0]
        return f"Your lowest transaction is **{tx['amount']}** at **{tx['merchant']}** on {tx.get('date', 'unknown date')}."

    # INTENT: Count
    if is_count:
        scope = f" for **{display_name}**" if display_name else ""
        return f"You have **{len(filtered)} transaction(s)**{scope} in your uploaded data."

    # No direct computation possible — fall through to LLM
    return None


@app.post("/api/ask")
async def ask_question(request: AskRequest):
    """RAG-powered chat endpoint grounded in uploaded transaction data."""
    question = request.question.strip()
    print(f"\n[RAG] Question: {question}")

    # Load transactions from MongoDB (individually try/except'd — DB hiccup won't crash the whole request)
    stored_transactions = []
    if transactions_collection is not None:
        try:
            stored_transactions = list(transactions_collection.find({}, {"_id": 0}))
        except Exception as e:
            print(f"[RAG] Failed to load transactions: {e}")
    print(f"[RAG] Stored transactions (from DB): {len(stored_transactions)}")

    # Load GST invoices for context (top-level import — no per-request import risk)
    stored_gst_invoices = []
    if gst_invoices_collection is not None:
        try:
            stored_gst_invoices = list(gst_invoices_collection.find({}, {"_id": 0}))
        except Exception as e:
            print(f"[RAG] Failed to load GST invoices: {e}")

    # If no data uploaded at all
    if not stored_transactions and not stored_gst_invoices:
        print("[RAG] No transactions stored — returning no-data message")
        return JSONResponse(content={
            "answer": "No transactions or GST invoices have been uploaded yet. Please upload a financial document first, then ask me about your spending."
        })

    # Step 1: Retrieve relevant transactions
    gst_keywords = ["gst", "tax", "cgst", "sgst", "liability", "gstr"]
    is_gst_query = any(k in question.lower() for k in gst_keywords)
    
    if is_gst_query:
        relevant = stored_gst_invoices
        print(f"[RAG] GST query detected. Retrieved {len(relevant)} GST invoices.")
        # Attempt basic GST math logic
        if "liability" in question.lower() or "total gst" in question.lower():
            total_cgst = sum(inv.get("cgst", 0) for inv in relevant)
            total_sgst = sum(inv.get("sgst", 0) for inv in relevant)
            total_igst = sum(inv.get("igst", 0) for inv in relevant)
            total = total_cgst + total_sgst + total_igst
            return JSONResponse(content={"answer": f"Your total GST liability is **₹{total:,.2f}** (CGST: ₹{total_cgst:,.2f}, SGST: ₹{total_sgst:,.2f}, IGST: ₹{total_igst:,.2f})."})
    else:
        relevant = retrieve_relevant_transactions(question, stored_transactions)
        print(f"[RAG] Retrieved {len(relevant)} relevant transactions")
        for tx in relevant:
            print(f"  - {tx.get('merchant')} | {tx.get('amount')} | {tx.get('date')}")

        # Step 2: Check if we can answer without LLM (only for standard transactions)
        if relevant:
            direct_answer = try_compute_directly(question, relevant)
            if direct_answer:
                print(f"[RAG] Direct computation answer: {direct_answer}")
                return JSONResponse(content={"answer": direct_answer})

    # Step 3: If no relevant transactions found
    if not relevant:
        print("[RAG] No relevant transactions found — returning refusal")
        return JSONResponse(content={
            "answer": "No relevant data found in uploaded transactions or invoices."
        })

    # Step 4: Use LLM with strict grounding prompt
    try:
        tx_text    = json.dumps(relevant, indent=2, ensure_ascii=False)
        full_prompt = RAG_SYSTEM_PROMPT.format(transactions=tx_text, question=question)

        print(f"[RAG] Calling Gemini with {len(relevant)} grounded transactions...")

        _RAG_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash"]
        response = None
        for _model in _RAG_MODELS:
            try:
                @retry(
                    stop=stop_after_attempt(2),
                    wait=wait_fixed(1),
                    retry=retry_if_exception(lambda e: not isinstance(e, (ClientError, APIError)))
                )
                def ask_with_retry(m=_model):
                    return client.models.generate_content(
                        model=m,
                        contents=[{"role": "user", "parts": [{"text": full_prompt}]}],
                    )
                response = ask_with_retry()
                print(f"[RAG] Used model: {_model}")
                break
            except (ClientError, APIError) as _e:
                _msg = str(_e)
                if "429" in _msg or "RESOURCE_EXHAUSTED" in _msg:
                    print(f"[RAG] {_model} quota exceeded — trying next")
                    continue
                raise
            except Exception:
                raise

        if response is None:
            return JSONResponse(content={
                "answer": "The AI service is currently rate-limited on all models. "
                          "Your data is safe — please try again in a few minutes."
            })

        answer = response.text.strip()
        print(f"[RAG] LLM answer ({len(answer)} chars): {answer[:200]}")
        return JSONResponse(content={"answer": answer})

    except ClientError as e:
        msg = str(e)
        if '429' in msg or 'RESOURCE_EXHAUSTED' in msg:
            answer = "The AI service is currently rate-limited. Please wait a moment and try again."
        else:
            answer = f"Gemini API error: {msg[:150]}"
        print(f"[ERROR] Gemini ClientError in /api/ask: {msg[:200]}")
        return JSONResponse(content={"answer": answer})
    except RetryError as e:
        print(f"[ERROR] RetryError in /api/ask after all attempts")
        return JSONResponse(content={"answer": "Unable to process your request currently. Please try again in a moment."})
    except Exception as e:
        print(f"[ERROR] Unexpected error in /api/ask: {str(e)}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"answer": f"Failed to process your question: {str(e)}"}
        )


# --------------- Health Check ---------------

@app.get("/api/health")
async def health():
    """Health check endpoint — reports DB and Gemini availability."""
    db_ok = False
    try:
        if transactions_collection is not None:
            transactions_collection.find_one()
            db_ok = True
    except Exception:
        pass
    return JSONResponse(content={
        "status": "ok",
        "db": db_ok,
        "gemini": bool(API_KEY),
    })
