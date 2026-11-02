"""Order Service: Order lifecycle tracking and CDC return eligibility calculation."""

from __future__ import annotations

import datetime
import sqlite3
from typing import Any, Dict, List, Optional


def calculate_return_eligibility(
    status: str,
    delivery_date_str: Optional[str],
    reference_date: Optional[datetime.date] = None,
) -> Dict[str, Any]:
    """Calculate 7-day statutory remorse return eligibility under CDC (Art. 49).

    Args:
        status: Order delivery status.
        delivery_date_str: Date string of delivery (YYYY-MM-DD).
        reference_date: Date to evaluate against (defaults to today).

    Returns:
        Dict with eligibility flag, days elapsed, and policy rationale.
    """
    if status.lower() != "delivered" or not delivery_date_str:
        return {
            "is_eligible_for_return": False,
            "days_since_delivery": None,
            "reason": (
                "O pedido ainda não consta como entregue. O prazo legal de 7 dias "
                "para devolução por arrependimento inicia apenas a partir da data de recebimento."
            ),
        }

    try:
        delivery_date = datetime.date.fromisoformat(delivery_date_str.strip())
    except ValueError:
        return {
            "is_eligible_for_return": False,
            "days_since_delivery": None,
            "reason": "Data de entrega em formato inválido no sistema.",
        }

    ref_date = reference_date or datetime.date.today()
    delta_days = (ref_date - delivery_date).days

    if delta_days < 0:
        return {
            "is_eligible_for_return": True,
            "days_since_delivery": 0,
            "reason": "Produto entregue recentemente. Dentro do prazo legal de 7 dias para arrependimento (CDC).",
        }

    if delta_days <= 7:
        return {
            "is_eligible_for_return": True,
            "days_since_delivery": delta_days,
            "reason": (
                f"Dentro do prazo legal de arrependimento (Art. 49 do CDC). "
                f"Entregue há {delta_days} dia(s). Devolução integral permitida sem custos."
            ),
        }
    else:
        return {
            "is_eligible_for_return": False,
            "days_since_delivery": delta_days,
            "reason": (
                f"Prazo de 7 dias corridos de arrependimento (CDC) expirado "
                f"(entregue há {delta_days} dias). Válida apenas a garantia da loja de "
                f"30 dias para defeitos de fabricação."
            ),
        }


def get_order_details(
    conn: sqlite3.Connection,
    order_id: Optional[int] = None,
    customer_name_or_phone: Optional[str] = None,
    reference_date: Optional[datetime.date] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch order status, items, delivery details, and return eligibility.

    Args:
        conn: SQLite database connection.
        order_id: Unique order ID.
        customer_name_or_phone: Customer name or phone substring.
        reference_date: Optional reference date for deterministic testing.

    Returns:
        Order summary dictionary or None if not found.
    """
    cursor = conn.cursor()

    sql = """
        SELECT 
            o.order_id,
            o.order_date,
            o.status,
            o.total_amount,
            o.payment_method,
            o.tracking_code,
            o.delivery_date,
            o.notes,
            c.customer_id,
            c.name AS customer_name,
            c.phone AS customer_phone,
            c.email AS customer_email,
            c.city AS customer_city
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE 1=1
    """
    params: List[Any] = []

    if order_id is not None:
        sql += " AND o.order_id = ?"
        params.append(int(order_id))
    elif customer_name_or_phone:
        query_val = f"%{customer_name_or_phone.strip().lower()}%"
        sql += " AND (LOWER(c.name) LIKE ? OR c.phone LIKE ?)"
        params.extend([query_val, query_val])
    else:
        return None

    sql += " ORDER BY o.order_date DESC LIMIT 1"
    cursor.execute(sql, params)
    order_row = cursor.fetchone()

    if not order_row:
        return None

    # Fetch ordered items
    items_sql = """
        SELECT 
            oi.quantity,
            oi.unit_price,
            p.product_id,
            p.name AS product_name,
            p.brand,
            p.price AS current_catalog_price
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = ?
    """
    cursor.execute(items_sql, (order_row["order_id"],))
    item_rows = cursor.fetchall()

    items = [
        {
            "product_id": it["product_id"],
            "name": it["product_name"],
            "brand": it["brand"],
            "quantity": it["quantity"],
            "unit_price": float(it["unit_price"]),
        }
        for it in item_rows
    ]

    return_info = calculate_return_eligibility(
        status=order_row["status"],
        delivery_date_str=order_row["delivery_date"],
        reference_date=reference_date,
    )

    return {
        "order_id": order_row["order_id"],
        "customer": {
            "name": order_row["customer_name"],
            "phone": order_row["customer_phone"],
            "email": order_row["customer_email"],
            "city": order_row["customer_city"],
        },
        "order_date": order_row["order_date"],
        "status": order_row["status"],
        "total_amount": float(order_row["total_amount"]),
        "payment_method": order_row["payment_method"],
        "tracking_code": order_row["tracking_code"] or "Não aplicável / Em processamento",
        "delivery_date": order_row["delivery_date"],
        "notes": order_row["notes"],
        "items": items,
        "return_policy": return_info,
    }
