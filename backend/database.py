from pymongo import MongoClient
from pymongo.errors import OperationFailure, ConnectionFailure
import os
import certifi
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "ragmodel1")

# Connect with explicit timeouts and proper SSL certificates
try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=5000,
        tls=True,
        tlsCAFile=certifi.where(),
    )
except Exception as e:
    print(f"[MongoDB] WARNING: Could not create MongoClient: {e}")
    client = None

db = None
transactions_collection = None
reminders_collection = None

if client:
    # Test connection
    try:
        client.admin.command("ping")
        print(f"[MongoDB] Successfully connected to Atlas cluster!")
    except Exception as e:
        print(f"[MongoDB] WARNING: Could not connect to MongoDB Atlas: {e}")
        print("[MongoDB] The app will start but DB operations may fail.")

    db = client[DB_NAME]
    transactions_collection = db["transactions"]
    reminders_collection = db["reminders"]
    gst_invoices_collection = db["gst_invoices"]

    # Create indexes (non-fatal if they fail)
    try:
        try:
            transactions_collection.drop_index("tx_dedup_index")
        except OperationFailure:
            pass

        transactions_collection.create_index(
            [("merchant", 1), ("amount", 1), ("date", 1)],
            unique=True,
            name="tx_dedup_index"
        )
        reminders_collection.create_index("merchant", name="reminder_merchant_index")
        
        # GST Invoice Unique Index
        try:
            gst_invoices_collection.drop_index("gst_invoice_dedup_index")
        except OperationFailure:
            pass
            
        gst_invoices_collection.create_index(
            "invoice_number",
            unique=True,
            name="gst_invoice_dedup_index"
        )
        
        print(f"[MongoDB] Connected to database: {DB_NAME}")
        print(f"[MongoDB] Collections: transactions, reminders, gst_invoices")
    except Exception as e:
        print(f"[MongoDB] WARNING: Could not create indexes: {e}")
        print("[MongoDB] The app will start but some DB features may not work.")
else:
    print("[MongoDB] No client available. The app will start without database support.")
