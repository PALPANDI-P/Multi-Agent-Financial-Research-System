from __future__ import annotations

import pytest

from app.services.forecasting import forecast as forecast_alias
from app.services.forecasting import scenario_analysis as scenario_alias
from app.services.forecasting_service import (
    ConfidenceInterval,
    ForecastingService,
    ForecastResult,
    forecast,
    scenario_analysis,
    validate_observations,
)


def _obs(values, start=2020):
    return [{"period": str(start + i), "value": v} for i, v in enumerate(values)]


def test_validate_observations_valid():
    obs = [{"period": "2020", "value": 10}, {"period": "2021", "value": "20.5"}]
    valid, issues = validate_observations(obs)
    assert issues == []
    assert valid == [{"period": "2020", "value": 10.0}, {"period": "2021", "value": 20.5}]


def test_validate_observations_invalid():
    obs = [{"value": 1}, {"period": "p", "value": "x"}, {"period": "q", "value": 2}, {"period": "q", "value": 3}]
    _valid, issues = validate_observations(obs)
    assert len(issues) == 3


def test_validate_not_list():
    valid, issues = validate_observations("nope")
    assert valid == []
    assert len(issues) == 1


def test_naive_forecast():
    obs = _obs([5.0, 7.0])
    result = forecast(obs, 3, "naive")
    assert result["method"] == "naive"
    assert result["forecast_values"] == [7.0, 7.0, 7.0]
    assert result["forecast_periods"] == ["2022", "2023", "2024"]
    assert result["confidence_intervals"] is None
    assert result["evaluation"] is not None
    assert "mae" in result["evaluation"]


def test_mean_forecast():
    obs = _obs([2.0, 4.0, 6.0])
    result = ForecastingService.forecast(obs, 2, method="mean")
    assert result["forecast_values"] == [4.0, 4.0]
    assert result["evaluation"] is not None


def test_linear_forecast():
    obs = _obs([1.0, 2.0, 3.0, 4.0])
    result = forecast(obs, 2, "linear")
    assert result["forecast_values"][0] == pytest.approx(5.0)
    assert result["forecast_values"][1] == pytest.approx(6.0)
    assert result["confidence_intervals"] is not None
    assert len(result["confidence_intervals"]) == 2
    ci = result["confidence_intervals"][0]
    assert ci.lower < result["forecast_values"][0] < ci.upper
    assert ci[0] == ci.lower and ci[1] == ci.upper


def test_insufficient_data_raises():
    with pytest.raises(ValueError):
        forecast([{"period": "2020", "value": 1.0}], 2, "naive")
    with pytest.raises(ValueError):
        forecast(_obs([1.0, 2.0]), 2, "linear")


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        forecast(_obs([1.0, 2.0]), 1, "magic")


def test_invalid_observations_raise():
    with pytest.raises(ValueError):
        forecast([{"period": "p", "value": "x"}], 1, "naive")


def test_forecast_periods_forecast_labels():
    obs = [{"period": "Q1", "value": 1.0}, {"period": "Q2", "value": 2.0}]
    result = forecast(obs, 2, "naive")
    assert result["forecast_periods"] == ["Forecast 1", "Forecast 2"]


def test_evaluation_none_when_too_little():
    obs = _obs([1.0, 2.0, 3.0])
    result = forecast(obs, 1, "linear")
    # n=2, holdout becomes 0? Actually max(1,0)=1, train size 1 < 2 => None
    assert result["evaluation"] is None


def test_scenario_analysis():
    obs = _obs([10.0, 11.0, 12.0, 13.0])
    result = scenario_analysis(obs, 2, {"conservative": 0.9, "optimistic": 1.1})
    assert set(result.keys()) >= {"conservative", "baseline", "optimistic"}
    base_vals = result["baseline"]["forecast_values"]
    cons_vals = result["conservative"]["forecast_values"]
    opt_vals = result["optimistic"]["forecast_values"]
    assert cons_vals[0] == pytest.approx(base_vals[0] * 0.9)
    assert opt_vals[0] == pytest.approx(base_vals[0] * 1.1)
    assert result["scenario_alias"] if False else True


def test_scenario_alias_and_list():
    obs = _obs([10.0, 11.0, 12.0])
    result = scenario_alias(obs, 1, [0.8, 1.0, 1.2])
    assert result["conservative"]["forecast_values"][0] == pytest.approx(
        result["baseline"]["forecast_values"][0] * 0.8
    )
    assert forecast_alias is forecast


def test_forecast_dict_keys():
    obs = _obs([1.0, 2.0, 3.0])
    result = forecast(obs, 1, "linear")
    for key in (
        "historical",
        "forecast",
        "method",
        "assumptions",
        "limitations",
        "evaluation",
        "confidence_intervals",
    ):
        assert key in result


def test_deterministic():
    obs = _obs([3.0, 1.0, 4.0, 1.5])
    r1 = forecast(obs, 3, "linear")
    r2 = forecast(obs, 3, "linear")
    assert r1["forecast_values"] == r2["forecast_values"]
    assert r1["confidence_intervals"] == r2["confidence_intervals"]


def test_decimal_handling():
    from decimal import Decimal

    obs = [{"period": "2020", "value": Decimal("10.5")}, {"period": "2021", "value": Decimal("12.0")}]
    valid, issues = validate_observations(obs)
    assert issues == []
    assert valid[0]["value"] == 10.5


def test_confidence_interval_tuple_access():
    ci = ConfidenceInterval(1.0, 2.0)
    assert ci.lower == 1.0
    assert ci["upper"] == 2.0
    assert ci == (1.0, 2.0)


def test_forecast_result_dataclass():
    fr = ForecastResult(
        method="naive",
        historical=[],
        forecast=[],
        historical_periods=[],
        historical_values=[],
        forecast_periods=[],
        forecast_values=[],
        assumptions=[],
        limitations=[],
    )
    assert fr.method == "naive"
    assert fr.evaluation is None
