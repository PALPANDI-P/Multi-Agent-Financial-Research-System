from __future__ import annotations

import unittest.mock as mock

from app.agents.research_agent import ResearchAgent


def test_project_handling_returns_project_answer() -> None:
    pa = "Project info answer"
    with mock.patch("app.agents.research_agent.project_answer", return_value=pa):
        agent = ResearchAgent()
        result = agent.research("What file formats are supported?")
    assert result.answer == pa
    assert result.citations == []


def test_forecast_handling_returns_detailed_answer() -> None:
    metrics = [
        {"metric_name": "Revenue", "metric_type": "revenue", "reporting_period": "2020", "metric_value": 100},
        {"metric_name": "Revenue", "metric_type": "revenue", "reporting_period": "2021", "metric_value": 120},
        {"metric_name": "Revenue", "metric_type": "revenue", "reporting_period": "2022", "metric_value": 140},
    ]
    with mock.patch("app.agents.research_agent.project_answer", return_value=None):
        agent = ResearchAgent(metrics=metrics)
        result = agent.research("predict revenue")
    assert "Forecast for Revenue" in (result.answer or "")
    assert "Historical:" in (result.answer or "")
    assert "Forecast:" in (result.answer or "")
    assert "Assumptions:" in (result.answer or "")
    assert "Limitations:" in (result.answer or "")
    assert "Evaluation:" in (result.answer or "")
    assert result.citations == []


def test_forecast_insufficient_data_returns_guidance() -> None:
    metrics = [
        {"metric_name": "Revenue", "metric_type": "revenue", "reporting_period": "2020", "metric_value": 100},
    ]
    with mock.patch("app.agents.research_agent.project_answer", return_value=None):
        agent = ResearchAgent(metrics=metrics)
        result = agent.research("predict revenue")
    assert "Insufficient data" in (result.answer or "")
