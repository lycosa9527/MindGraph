"""market_payments is keyed by order_id; visibility follows market_orders.user_id."""

from utils.db.alembic_migration import load_rls_policy_builder

builder = load_rls_policy_builder()
MARKET_PAYMENTS_EXPR = dict(builder.MARKET_CHILD_TABLES)["market_payments"]


def test_market_payments_not_user_owned():
    assert "market_payments" not in builder.USER_OWNED_TABLES


def test_market_payments_policy_joins_orders():
    assert "market_orders mo" in MARKET_PAYMENTS_EXPR
    assert "order_id" in MARKET_PAYMENTS_EXPR
    assert "rls_diagram_visible(mo.user_id)" in MARKET_PAYMENTS_EXPR
    assert "rls_diagram_visible(user_id)" not in MARKET_PAYMENTS_EXPR
