from __future__ import annotations

from decimal import Decimal

from app.agents.financial_extraction_agent import (
    FinancialExtractionAgent,
    TableExtractionStrategy,
)


def test_extract_revenue_from_text():
    agent = FinancialExtractionAgent()
    result = agent.extract("Total revenue was 1.2 billion US dollars")
    metrics = list(result)
    assert len(metrics) >= 1
    revenue_metrics = [
        m for m in metrics
        if "revenue" in str(getattr(m, "metric_type", "")).lower()
        or "revenue" in str(getattr(m, "metric_name", "")).lower()
    ]
    assert revenue_metrics
    metric = revenue_metrics[0]
    assert metric.metric_value == Decimal("1.2") or float(metric.metric_value) == 1.2
    assert metric.currency in ("USD", None)


def test_extract_empty_text():
    agent = FinancialExtractionAgent()
    result = agent.extract("")
    assert len(result) == 0


def test_extract_dedupes_conflicting_duplicates():
    agent = FinancialExtractionAgent()
    text = "Total revenue was 1.2 billion USD. Total revenue was 1.2 billion USD."
    result = agent.extract(text)
    revenue_metrics = [
        m for m in result
        if "revenue" in str(getattr(m, "metric_type", "")).lower()
    ]
    assert len(revenue_metrics) == 1


def test_extract_invalid_none_input():
    agent = FinancialExtractionAgent()
    for bad in (None,):
        result = agent.extract(bad)
        assert len(result) == 0
    result = agent.extract(text=None)
    assert len(result) == 0


def test_table_strategy_none_tables():
    strategy = TableExtractionStrategy()
    produced = strategy.extract(tables=None)
    assert produced == []
