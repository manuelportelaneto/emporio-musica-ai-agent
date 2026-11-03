"""Data Engine: In-memory SQLite engine and Policy Vector Indexer.

Loads normalized CSV datasets into an in-memory SQLite relational database
and parses the store policies PDF into a vector index for semantic retrieval.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pypdf


def _clean_str(val: Optional[str]) -> str:
    return val.strip() if val else ""


def _to_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(str(val).replace(",", ".").strip())
    except (ValueError, TypeError):
        return default


def _to_int(val: Any, default: int = 0) -> int:
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return default


def init_sqlite_engine(data_dir: str = "data") -> sqlite3.Connection:
    """Initialize an in-memory SQLite database populated from CSV datasets.

    Args:
        data_dir: Directory containing the normalized CSV files.

    Returns:
        Configured in-memory sqlite3.Connection with row_factory.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create tables per SPEC.md Section 3.2
    cursor.execute(
        """
        CREATE TABLE categories (
            category_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category_id INTEGER REFERENCES categories(category_id),
            brand TEXT NOT NULL,
            price REAL NOT NULL,
            stock_quantity INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            specs TEXT,
            description TEXT
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            city TEXT,
            birth_date TEXT,
            address TEXT,
            musical_interests TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(customer_id),
            order_date TEXT NOT NULL,
            status TEXT NOT NULL,
            total_amount REAL NOT NULL,
            payment_method TEXT,
            tracking_code TEXT,
            delivery_date TEXT,
            notes TEXT
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE order_items (
            order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER REFERENCES orders(order_id),
            product_id INTEGER REFERENCES products(product_id),
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL DEFAULT 0.0
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE promotions (
            promotion_id INTEGER PRIMARY KEY,
            product_id INTEGER REFERENCES products(product_id),
            discount_percentage REAL NOT NULL,
            description TEXT,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        """
    )

    # Ingest categories
    categories_path = os.path.join(data_dir, "categories.csv")
    if os.path.exists(categories_path):
        with open(categories_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    "INSERT INTO categories (category_id, name, description) VALUES (?, ?, ?)",
                    (
                        _to_int(row.get("category_id")),
                        _clean_str(row.get("name")),
                        _clean_str(row.get("description")),
                    ),
                )

    # Ingest products
    products_path = os.path.join(data_dir, "products.csv")
    if os.path.exists(products_path):
        with open(products_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = _clean_str(row.get("name"))
                brand = name.split()[0] if name else "Generic"
                price = _to_float(row.get("price_brl") or row.get("price"))
                cursor.execute(
                    """
                    INSERT INTO products (
                        product_id, name, category_id, brand, price, stock_quantity, status, specs, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _to_int(row.get("product_id")),
                        name,
                        _to_int(row.get("category_id")),
                        brand,
                        price,
                        _to_int(row.get("stock_quantity")),
                        _clean_str(row.get("status") or "active"),
                        _clean_str(row.get("specs")),
                        _clean_str(row.get("description")),
                    ),
                )

    # Ingest customers
    customers_path = os.path.join(data_dir, "customers.csv")
    if os.path.exists(customers_path):
        with open(customers_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    "INSERT INTO customers (customer_id, name, phone, email, city) VALUES (?, ?, ?, ?, ?)",
                    (
                        _to_int(row.get("customer_id")),
                        _clean_str(row.get("name")),
                        _clean_str(row.get("phone")),
                        _clean_str(row.get("email")),
                        _clean_str(row.get("city")),
                    ),
                )

    # Ingest orders
    orders_path = os.path.join(data_dir, "orders.csv")
    if os.path.exists(orders_path):
        with open(orders_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT INTO orders (
                        order_id, customer_id, order_date, status, total_amount,
                        payment_method, tracking_code, delivery_date, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _to_int(row.get("order_id")),
                        _to_int(row.get("customer_id")),
                        _clean_str(row.get("order_date")),
                        _clean_str(row.get("status")),
                        _to_float(row.get("total_brl") or row.get("total_amount")),
                        _clean_str(row.get("payment_method")),
                        _clean_str(row.get("tracking_code")),
                        _clean_str(row.get("estimated_delivery") or row.get("delivery_date")),
                        _clean_str(row.get("notes")),
                    ),
                )

    # Ingest order_items (calculating unit_price from products if missing)
    order_items_path = os.path.join(data_dir, "order_items.csv")
    if os.path.exists(order_items_path):
        with open(order_items_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                prod_id = _to_int(row.get("product_id"))
                unit_price = _to_float(row.get("unit_price"))
                if unit_price == 0.0:
                    cursor.execute("SELECT price FROM products WHERE product_id = ?", (prod_id,))
                    p_res = cursor.fetchone()
                    if p_res:
                        unit_price = p_res["price"]

                cursor.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                    (
                        _to_int(row.get("order_id")),
                        prod_id,
                        _to_int(row.get("quantity"), default=1),
                        unit_price,
                    ),
                )

    # Ingest promotions
    promotions_path = os.path.join(data_dir, "promotions.csv")
    if os.path.exists(promotions_path):
        with open(promotions_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute(
                    """
                    INSERT INTO promotions (
                        promotion_id, product_id, discount_percentage, description, is_active
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        _to_int(row.get("promotion_id")),
                        _to_int(row.get("product_id")),
                        _to_float(row.get("discount_percent") or row.get("discount_percentage")),
                        _clean_str(row.get("description")),
                        _to_int(row.get("is_active"), default=1),
                    ),
                )

    conn.commit()
    return conn


@dataclass
class PolicyChunk:
    """Document chunk extracted from the policy manual."""

    chunk_id: int
    page: int
    title: str
    content: str
    word_freq: Dict[str, float]


class PolicyVectorIndex:
    """Lightweight TF-IDF Semantic Vector Index for store policies.
    
    Prioritizes structured summarized policies (data/store_policies.json)
    for zero noise, low token consumption, and instant retrieval, falling
    back to the raw PDF manual when json is absent.
    """

    def __init__(
        self,
        pdf_path: str = "data/políticas_da_loja.pdf",
        json_path: str = "data/store_policies.json",
    ):
        self.pdf_path = pdf_path
        self.json_path = json_path
        self.chunks: List[PolicyChunk] = []
        self.idf: Dict[str, float] = {}
        self._build_index()

    def _tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r"[^\w\s]", " ", text.lower(), flags=re.UNICODE)
        tokens = [t for t in cleaned.split() if len(t) > 2]
        return tokens

    def _build_index(self) -> None:
        chunk_id = 0
        df: Dict[str, int] = {}

        # 1. Prioritize Structured Summarized Policies JSON
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, mode="r", encoding="utf-8") as f:
                    data = json.load(f)

                # Add store metadata as first chunk
                store_meta = data.get("store_metadata", {})
                if store_meta:
                    meta_text = (
                        f"Informações Oficiais da Loja: {store_meta.get('name')}. "
                        f"Endereço: {store_meta.get('address')}. "
                        f"Horário de Atendimento: {store_meta.get('hours')}. "
                        f"Telefone: {store_meta.get('phone')} | E-mail: {store_meta.get('email')}. "
                        f"Escopo: {store_meta.get('catalog_scope')}"
                    )
                    tokens = self._tokenize(meta_text)
                    if tokens:
                        tf: Dict[str, float] = {}
                        for t in tokens:
                            tf[t] = tf.get(t, 0.0) + 1.0
                        for t in tf:
                            tf[t] /= len(tokens)
                        self.chunks.append(
                            PolicyChunk(
                                chunk_id=chunk_id,
                                page=1,
                                title="Informações e Contato da Loja",
                                content=meta_text,
                                word_freq=tf,
                            )
                        )
                        chunk_id += 1
                        for t in set(tokens):
                            df[t] = df.get(t, 0) + 1

                # Add each structured policy section
                for idx, p in enumerate(data.get("policies", [])):
                    title = p.get("title", f"Regra {idx+1}")
                    summary = p.get("summary", "")
                    content_full = f"{title}: {summary}"
                    keywords = " ".join(p.get("keywords", []))
                    tokens = self._tokenize(content_full + " " + keywords)
                    if not tokens:
                        continue
                    tf = {}
                    for t in tokens:
                        tf[t] = tf.get(t, 0.0) + 1.0
                    for t in tf:
                        tf[t] /= len(tokens)

                    self.chunks.append(
                        PolicyChunk(
                            chunk_id=chunk_id,
                            page=idx + 1,
                            title=title,
                            content=summary,
                            word_freq=tf,
                        )
                    )
                    chunk_id += 1
                    for t in set(tokens):
                        df[t] = df.get(t, 0) + 1

                doc_count = len(self.chunks)
                if doc_count > 0:
                    for term, count in df.items():
                        self.idf[term] = math.log((doc_count + 1) / (count + 1)) + 1.0
                return
            except Exception:
                pass

        # 2. Fallback to Raw PDF parsing if JSON is absent
        if not os.path.exists(self.pdf_path):
            return

        reader = pypdf.PdfReader(self.pdf_path)
        doc_count = 0

        for page_idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            # Normalize excessive whitespace
            text = re.sub(r"\s+", " ", text).strip()
            if not text:
                continue

            # Split into semantic paragraphs / sections (~400 chars each)
            paragraphs = [p.strip() for p in text.split("\n") if len(p.strip()) > 30]
            if not paragraphs:
                paragraphs = [text[i : i + 400] for i in range(0, len(text), 350)]

            for para in paragraphs:
                tokens = self._tokenize(para)
                if not tokens:
                    continue

                tf = {}
                for t in tokens:
                    tf[t] = tf.get(t, 0.0) + 1.0

                total_tokens = len(tokens)
                for t in tf:
                    tf[t] /= total_tokens

                # Track title / section name if present
                title = f"Manual de Políticas - Página {page_idx + 1}"
                chunk = PolicyChunk(
                    chunk_id=chunk_id,
                    page=page_idx + 1,
                    title=title,
                    content=para,
                    word_freq=tf,
                )
                self.chunks.append(chunk)
                chunk_id += 1

                for t in set(tokens):
                    df[t] = df.get(t, 0) + 1

        doc_count = len(self.chunks)
        if doc_count > 0:
            for term, count in df.items():
                self.idf[term] = math.log((doc_count + 1) / (count + 1)) + 1.0

    def search(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """Search policy chunks using cosine similarity over TF-IDF vectors.

        Args:
            query: Query string.
            top_k: Number of chunks to retrieve.

        Returns:
            List of dictionaries containing content, page, and score.
        """
        if not self.chunks:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        q_tf: Dict[str, float] = {}
        for t in query_tokens:
            q_tf[t] = q_tf.get(t, 0.0) + 1.0
        for t in q_tf:
            q_tf[t] /= len(query_tokens)

        # Query vector magnitude
        q_vec = {t: q_tf[t] * self.idf.get(t, 1.0) for t in q_tf}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        scores: List[Tuple[float, PolicyChunk]] = []
        for chunk in self.chunks:
            dot = 0.0
            c_norm_sq = 0.0
            for t, tf in chunk.word_freq.items():
                w = tf * self.idf.get(t, 1.0)
                c_norm_sq += w * w
                if t in q_vec:
                    dot += q_vec[t] * w

            c_norm = math.sqrt(c_norm_sq) or 1.0
            score = dot / (q_norm * c_norm)
            scores.append((score, chunk))

        scores.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, chunk in scores[:top_k]:
            results.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "page": chunk.page,
                    "title": chunk.title,
                    "content": chunk.content,
                    "score": round(score, 4),
                }
            )
        return results
