import json
import os
import sqlite3
from datetime import datetime
from typing import List, Optional
from fastmcp import FastMCP

# 1. Initialize Server & Paths
mcp = FastMCP("Expense-Tracker-Pro")
# Ensure we use absolute paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "expenses.db")
CAT_FILE = os.path.join(BASE_DIR, "categories.json")

# 2. Database Initialization
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        # 1. Create the table if it doesn't exist at all
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                amount REAL,
                category TEXT,
                type TEXT CHECK(type IN ('expense', 'credit')),
                note TEXT
            )
        """)
        
        # 2. Check if 'date' column exists (Self-healing for old databases)
        cursor = conn.execute("PRAGMA table_info(transactions)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'date' not in columns:
            print("Updating database: Adding missing 'date' column...")
            conn.execute("ALTER TABLE transactions ADD COLUMN date TEXT")

init_db()  # Run this immediately so the table exists before any tool call

# 3. Resources
@mcp.resource("config://categories")
def get_categories() -> dict:
    """Provides the valid expense categories and their subcategories."""
    if not os.path.exists(CAT_FILE):
        return {"error": "categories.json not found. Please create it."}
    with open(CAT_FILE, "r") as f:
        return json.load(f)

# 4. Tools
@mcp.tool()
def add_transaction(amount: float, category: str, subcategory: str, type: str = "expense", note: str = "") -> str:
    """
    Add a transaction. 
    Matches against 'config://categories' to ensure valid categorization.
    """
    with open(CAT_FILE, "r") as f:
        data = json.load(f)["categories"]

    # Validation Logic
    if category not in data:
        return f"❌ Error: '{category}' is not a valid category."
    
    if subcategory not in data[category]:
        options = ", ".join(data[category])
        return f"❌ Error: '{subcategory}' is not valid for {category}. Options: {options}"

    # Save to SQLite
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT INTO transactions (date, amount, category, type, note) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d"), amount, f"{category}:{subcategory}", type, note)
        )
    return f"✅ Recorded {type}: ${amount} for {category} > {subcategory}."

@mcp.tool()
def list_transactions(limit: int = 10) -> List[dict]:
    """List the most recent transactions from the database."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

@mcp.tool()
def delete_transaction(transaction_id: int) -> str:
    """Delete a specific transaction using its ID number."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        if cursor.rowcount == 0:
            return f"❌ No transaction found with ID {transaction_id}."
    return f"🗑️ Deleted transaction {transaction_id}."

@mcp.tool()
def update_transaction(transaction_id: int, amount: Optional[float] = None, note: Optional[str] = None) -> str:
    """Update an existing transaction's amount or note."""
    with sqlite3.connect(DB_FILE) as conn:
        if amount:
            conn.execute("UPDATE transactions SET amount = ? WHERE id = ?", (amount, transaction_id))
        if note:
            conn.execute("UPDATE transactions SET note = ? WHERE id = ?", (note, transaction_id))
    return f"✏️ Updated transaction {transaction_id}."

if __name__ == "__main__":
    mcp.run()