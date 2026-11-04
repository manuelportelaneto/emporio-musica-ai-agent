#!/usr/bin/env python3
"""Database Reset Script: Restores emporio_records.db to a clean, empty state.

Purges development and test audit event logs, conversation histories, and session CRM records,
preserving pristine tables identical to the initial repository deployment.
The raw data/*.csv sources remain untouched.
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.audit_store import AuditStore


def reset_records_database(db_path: str = "emporio_records.db") -> None:
    print(f"[*] Resetting SQLite database: {db_path}...")
    store = AuditStore(db_path=db_path)
    store.clear_all_sessions()
    print("[+] Successfully purged all rows from conversation_history, execution_audit_logs, and customer_sessions.")
    print("[+] emporio_records.db is now in a 100% clean, pristine state.")


if __name__ == "__main__":
    reset_records_database()

