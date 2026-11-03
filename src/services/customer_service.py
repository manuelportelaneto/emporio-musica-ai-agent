"""Customer Service: Handles progressive identification, authentication, and CRM profiling."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any, Dict, List, Optional


def normalize_phone(raw_phone: str) -> str:
    """Normalize phone to numeric digits only.
    
    Examples:
        '(67) 99812-3456' -> '67998123456'
        '67 998123456'    -> '67998123456'
    """
    if not raw_phone:
        return ""
    return re.sub(r"\D", "", str(raw_phone))


def authenticate_or_register_customer(
    conn: sqlite3.Connection,
    name: str,
    phone: str,
    birth_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Identify and authenticate customer by phone or create new account dynamically.

    Args:
        conn: In-memory SQLite connection.
        name: Customer full name.
        phone: Customer full telephone (with DDD).
        birth_date: Optional date of birth.

    Returns:
        Structured customer profile dictionary.
    """
    clean_digits = normalize_phone(phone)
    if not clean_digits or len(clean_digits) < 8:
        return {
            "error": "Número de telefone inválido. Por favor, informe o telefone completo com DDD apenas em números, sem pontos, traços ou parênteses (ex: 67998123456)."
        }

    cursor = conn.cursor()

    # Search existing customer by normalized digits or raw string
    cursor.execute("SELECT * FROM customers")
    all_customers = cursor.fetchall()

    matched_row = None
    for row in all_customers:
        row_digits = normalize_phone(row["phone"])
        if row_digits and (clean_digits in row_digits or row_digits in clean_digits):
            matched_row = row
            break

    if matched_row:
        customer_id = matched_row["customer_id"]
        # Fetch past orders for contextualization
        cursor.execute(
            """
            SELECT order_id, order_date, status, total_amount, tracking_code, delivery_date
            FROM orders
            WHERE customer_id = ?
            ORDER BY order_id DESC
            LIMIT 5
            """,
            (customer_id,),
        )
        orders = [dict(o) for o in cursor.fetchall()]

        # Parse musical interests if present
        interests = []
        if "musical_interests" in matched_row.keys() and matched_row["musical_interests"]:
            try:
                interests = json.loads(matched_row["musical_interests"])
            except Exception:
                interests = [matched_row["musical_interests"]]

        return {
            "status": "authenticated",
            "is_new": False,
            "customer_id": customer_id,
            "name": matched_row["name"],
            "phone": matched_row["phone"],
            "city": matched_row["city"] or "Campo Grande",
            "address": matched_row["address"] if "address" in matched_row.keys() else None,
            "birth_date": matched_row["birth_date"] if "birth_date" in matched_row.keys() else birth_date,
            "musical_interests": interests,
            "recent_orders": orders,
            "message": f"Bem-vindo(a) de volta, {matched_row['name']}! Sua conta foi autenticada com sucesso.",
        }

    # If customer does not exist, create new account dynamically
    cursor.execute(
        """
        INSERT INTO customers (name, phone, email, city, birth_date, address, musical_interests)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name.strip() if name else "Cliente Empório",
            phone.strip(),
            None,
            "Campo Grande",
            birth_date,
            None,
            "[]",
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid

    return {
        "status": "registered",
        "is_new": True,
        "customer_id": new_id,
        "name": name.strip() if name else "Cliente Empório",
        "phone": phone.strip(),
        "city": "Campo Grande",
        "address": None,
        "birth_date": birth_date,
        "musical_interests": [],
        "recent_orders": [],
        "message": f"Conta criada com sucesso para {name}! Agora você tem acesso exclusivo ao seu histórico e condições especiais.",
    }


def update_customer_profile(
    conn: sqlite3.Connection,
    phone: str,
    address: Optional[str] = None,
    musical_interests: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Incrementally update customer profile with address or musical interests.

    Args:
        conn: In-memory SQLite connection.
        phone: Customer telephone identifier.
        address: Delivery address or CEP.
        musical_interests: List of tags or instruments of interest.

    Returns:
        Status dictionary with updated fields.
    """
    clean_digits = normalize_phone(phone)
    if not clean_digits:
        return {"error": "Telefone inválido para atualização. Envie apenas os números com DDD, sem pontos, traços ou parênteses (ex: 67998123456)."}

    cursor = conn.cursor()
    cursor.execute("SELECT customer_id, phone, address, musical_interests FROM customers")
    rows = cursor.fetchall()

    target_id = None
    current_interests = []
    for r in rows:
        if normalize_phone(r["phone"]) == clean_digits:
            target_id = r["customer_id"]
            if r["musical_interests"]:
                try:
                    current_interests = json.loads(r["musical_interests"])
                except Exception:
                    current_interests = [r["musical_interests"]]
            break

    if not target_id:
        return {"error": f"Cliente com telefone {phone} não localizado para atualização."}

    updates = []
    params = []
    if address:
        updates.append("address = ?")
        params.append(address.strip())

    if musical_interests:
        merged = list(set(current_interests + [str(t).lower().strip() for t in musical_interests]))
        updates.append("musical_interests = ?")
        params.append(json.dumps(merged, ensure_ascii=False))

    if updates:
        sql = f"UPDATE customers SET {', '.join(updates)} WHERE customer_id = ?"
        params.append(target_id)
        cursor.execute(sql, tuple(params))
        conn.commit()

    return {
        "status": "updated",
        "customer_id": target_id,
        "address": address,
        "updated_interests": musical_interests or [],
        "message": "Dados cadastrais atualizados com sucesso!",
    }


def get_customer_by_phone(conn: sqlite3.Connection, phone: str) -> Optional[Dict[str, Any]]:
    """Retrieve customer by phone number."""
    clean_digits = normalize_phone(phone)
    if not clean_digits:
        return None

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers")
    for r in cursor.fetchall():
        if normalize_phone(r["phone"]) == clean_digits:
            return dict(r)
    return None
