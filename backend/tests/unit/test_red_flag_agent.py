from __future__ import annotations

from app.agents.red_flag_agent import RedFlagAgent


def test_analyze_declining_revenue_flags_high_or_critical():
    agent = RedFlagAgent()
    metrics = [
        {"metric_type": "revenue", "metric_name": "Revenue", "metric_value": 100, "reporting_period": "2023"},
        {"metric_type": "revenue", "metric_name": "Revenue", "metric_value": 60, "reporting_period": "2024"},
    ]
    result = agent.analyze(metrics)
    assert len(result.findings) >= 1
    assert any(f.severity in ("high", "critical") for f in result.findings)


def test_analyze_stable_revenue_no_findings():
    agent = RedFlagAgent()
    metrics = [
        {"metric_type": "revenue", "metric_name": "Revenue", "metric_value": 100, "reporting_period": "2023"},
        {"metric_type": "revenue", "metric_name": "Revenue", "metric_value": 100, "reporting_period": "2024"},
    ]
    result = agent.analyze(metrics=metrics)
    assert len(result.findings) == 0


def test_analyze_empty_metrics_no_crash():
    agent = RedFlagAgent()
    result = agent.analyze([])
    assert result is not None
    assert len(result.findings) == 0


def test_analyze_none_inputs_no_crash():
    agent = RedFlagAgent()
    for result in (agent.analyze(None), agent.analyze(metrics=None), agent.analyze(None, None)):
        assert result is not None
        assert len(result.findings) == 0


def test_persist_findings_no_session_factory_returns_unchanged():
    agent = RedFlagAgent()
    findings = []
    returned = agent.persist_findings(findings)
    assert returned is findings
    assert returned == findings
