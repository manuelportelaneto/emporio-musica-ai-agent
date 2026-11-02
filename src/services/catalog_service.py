"""Catalog Service: Product and price lookups with promotion and PIX logic."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional


def calculate_installments(price: float) -> Dict[str, Any]:
    """Calculate maximum interest-free installment options per store policy.

    Rules from store manual (Section 3.1):
    - Up to 12x interest-free for installments >= R$ 100.00
    - Up to 6x interest-free for installments >= R$ 80.00
    - Up to 3x interest-free for installments >= R$ 50.00
    """
    if price >= 1200.0:
        max_installments = 12
    elif price >= 480.0:
        max_installments = 6
    elif price >= 150.0:
        max_installments = 3
    else:
        max_installments = 1

    installment_value = round(price / max_installments, 2)
    return {
        "max_installments": max_installments,
        "installment_value": installment_value,
        "display_text": f"{max_installments}x de R$ {installment_value:.2f} sem juros",
    }


def lookup_catalog(
    conn: sqlite3.Connection,
    query: Optional[str] = None,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    in_stock_only: bool = True,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Search instruments in the catalog, checking stock and pricing.

    Args:
        conn: SQLite database connection.
        query: Optional search keyword (matches name, brand, description).
        category: Optional category name filter.
        max_price: Optional maximum price filter (in BRL).
        in_stock_only: Only return instruments currently in stock.
        limit: Maximum number of instruments to return (default 3).

    Returns:
        List of product dictionaries containing price calculations and stock.
    """
    sql = """
        SELECT 
            p.product_id,
            p.name,
            p.brand,
            p.price,
            p.stock_quantity,
            p.description,
            c.name AS category_name,
            promo.discount_percentage,
            promo.description AS promo_description
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.category_id
        LEFT JOIN promotions promo 
            ON p.product_id = promo.product_id AND promo.is_active = 1
        WHERE p.status = 'active'
    """
    params: List[Any] = []

    if in_stock_only:
        sql += " AND p.stock_quantity > 0"

    if max_price is not None:
        sql += " AND p.price <= ?"
        params.append(float(max_price))

    if category:
        sql += " AND LOWER(c.name) LIKE ?"
        params.append(f"%{category.lower().strip()}%")

    if query:
        cleaned_query = query.strip().lower()
        import re
        stop_words = {
            "de", "o", "a", "os", "as", "um", "uma", "para", "em", "com",
            "por", "que", "ver", "gostaria", "quero", "busco", "procuro",
            "tem", "têm", "qual", "quais", "quanto", "custa", "preço", "valor",
            "mostrar", "me", "sobre"
        }
        tokens = [w for w in re.findall(r"\w+", cleaned_query) if w not in stop_words]
        if not tokens:
            tokens = [cleaned_query]

        token_conditions = []
        for t in tokens:
            token_conditions.append(
                "(LOWER(p.name) LIKE ? OR LOWER(p.brand) LIKE ? OR LOWER(p.description) LIKE ?)"
            )
            params.extend([f"%{t}%", f"%{t}%", f"%{t}%"])

        sql += f" AND ({' AND '.join(token_conditions)})"

    sql += " ORDER BY p.price ASC LIMIT ?"
    params.append(min(limit, 5))

    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        regular_price = float(row["price"])
        discount_pct = float(row["discount_percentage"]) if row["discount_percentage"] else 0.0
        has_promo = discount_pct > 0

        if has_promo:
            promo_price = round(regular_price * (1.0 - discount_pct / 100.0), 2)
            # Per policy Section 6.2: PIX discount is non-cumulative with active promotions
            pix_price = promo_price
            effective_price = promo_price
        else:
            promo_price = None
            # 5% cash discount for PIX on regular prices
            pix_price = round(regular_price * 0.95, 2)
            effective_price = regular_price

        installment_info = calculate_installments(effective_price)

        results.append(
            {
                "product_id": row["product_id"],
                "name": row["name"],
                "brand": row["brand"],
                "category": row["category_name"],
                "regular_price": regular_price,
                "has_promotion": has_promo,
                "discount_percentage": discount_pct if has_promo else None,
                "promo_price": promo_price,
                "pix_price": pix_price,
                "installments": installment_info["display_text"],
                "max_installments": installment_info["max_installments"],
                "installment_value": installment_info["installment_value"],
                "stock_quantity": row["stock_quantity"],
                "description": row["description"],
            }
        )

    return results
