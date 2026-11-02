"""Unit tests for deterministic backend services."""

from __future__ import annotations

import datetime
import pytest

from src.data_engine import PolicyVectorIndex, init_sqlite_engine
from src.services.catalog_service import calculate_installments, lookup_catalog
from src.services.order_service import calculate_return_eligibility, get_order_details
from src.services.policy_service import query_store_policy


@pytest.fixture(scope="session")
def db_conn():
    """Session-scoped in-memory database initialized from CSVs."""
    return init_sqlite_engine("data")


@pytest.fixture(scope="session")
def policy_index():
    """Session-scoped policy vector index initialized from PDF."""
    return PolicyVectorIndex("data/políticas_da_loja.pdf")


class TestCatalogService:
    def test_database_tables_populated(self, db_conn):
        cursor = db_conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM products")
        products_count = cursor.fetchone()["total"]
        assert products_count > 0, "Products table must not be empty"

        cursor.execute("SELECT COUNT(*) AS total FROM categories")
        categories_count = cursor.fetchone()["total"]
        assert categories_count > 0, "Categories table must not be empty"

    def test_lookup_catalog_query(self, db_conn):
        results = lookup_catalog(db_conn, query="Yamaha C40", in_stock_only=True)
        assert len(results) > 0
        item = results[0]
        assert "Yamaha" in item["name"]
        assert item["regular_price"] > 0
        assert item["pix_price"] > 0

    def test_lookup_catalog_pix_discount_regular_price(self, db_conn):
        # Product without active promotion should get 5% discount for PIX
        results = lookup_catalog(db_conn, query="Yamaha C40", in_stock_only=True)
        assert len(results) > 0
        item = results[0]
        if not item["has_promotion"]:
            expected_pix = round(item["regular_price"] * 0.95, 2)
            assert item["pix_price"] == expected_pix

    def test_lookup_catalog_active_promotion(self, db_conn):
        # Product 121 or 127 has active promo
        cursor = db_conn.cursor()
        cursor.execute("SELECT product_id FROM promotions WHERE is_active = 1 LIMIT 1")
        promo_row = cursor.fetchone()
        assert promo_row is not None
        prod_id = promo_row["product_id"]

        cursor.execute("SELECT name FROM products WHERE product_id = ?", (prod_id,))
        prod = cursor.fetchone()
        assert prod is not None

        results = lookup_catalog(db_conn, query=prod["name"])
        assert len(results) > 0
        item = results[0]
        assert item["has_promotion"] is True
        assert item["discount_percentage"] > 0
        # PIX is non-cumulative with promotions per Section 6.2
        assert item["pix_price"] == item["promo_price"]

    def test_installments_tiers(self):
        # >= 1200 -> 12x
        inst_12 = calculate_installments(1500.0)
        assert inst_12["max_installments"] == 12
        assert inst_12["installment_value"] == 125.0

        # >= 480 and < 1200 -> 6x
        inst_6 = calculate_installments(600.0)
        assert inst_6["max_installments"] == 6
        assert inst_6["installment_value"] == 100.0

        # >= 150 and < 480 -> 3x
        inst_3 = calculate_installments(300.0)
        assert inst_3["max_installments"] == 3
        assert inst_3["installment_value"] == 100.0


class TestOrderService:
    def test_order_lookup_by_id(self, db_conn):
        order = get_order_details(db_conn, order_id=1)
        assert order is not None
        assert order["order_id"] == 1
        assert "customer" in order
        assert len(order["items"]) > 0

    def test_order_lookup_by_customer_name(self, db_conn):
        order = get_order_details(db_conn, customer_name_or_phone="Pedro Henrique")
        assert order is not None
        assert "Pedro" in order["customer"]["name"]

    def test_cdc_return_eligibility_within_7_days(self):
        delivery_date = "2026-03-01"
        current_date = datetime.date(2026, 3, 5)  # 4 days elapsed <= 7
        ret = calculate_return_eligibility("delivered", delivery_date, reference_date=current_date)
        assert ret["is_eligible_for_return"] is True
        assert ret["days_since_delivery"] == 4

    def test_cdc_return_eligibility_after_7_days(self):
        delivery_date = "2026-02-10"
        current_date = datetime.date(2026, 3, 1)  # 19 days elapsed > 7
        ret = calculate_return_eligibility("delivered", delivery_date, reference_date=current_date)
        assert ret["is_eligible_for_return"] is False
        assert ret["days_since_delivery"] == 19
        assert "expirado" in ret["reason"].lower()

    def test_cdc_return_eligibility_not_delivered(self):
        ret = calculate_return_eligibility("shipped", "2026-03-10")
        assert ret["is_eligible_for_return"] is False
        assert "não consta como entregue" in ret["reason"]


class TestPolicyService:
    def test_query_store_policy_found(self, policy_index):
        result = query_store_policy(policy_index, topic="horário de funcionamento endereço")
        assert result["found"] is True
        assert len(result["excerpts"]) > 0
        assert "Empório da Música" in result["store_info"]["name"]
        assert "Campo Grande" in result["store_info"]["address"]

    def test_query_store_policy_shipping(self, policy_index):
        result = query_store_policy(policy_index, topic="frete motoboy entrega Campo Grande")
        assert result["found"] is True
        excerpts_text = " ".join([e["content"] for e in result["excerpts"]])
        assert any(term in excerpts_text.lower() for term in ["campo grande", "frete", "entrega", "correios", "sedex"])
