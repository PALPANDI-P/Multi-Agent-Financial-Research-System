from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

__all__ = [
    "ConfidenceInterval",
    "ForecastResult",
    "ForecastService",
    "ForecastingService",
    "ObservationIssue",
    "forecast",
    "run_forecast",
    "run_scenario_analysis",
    "scenario_analysis",
    "validate_observations",
]

_METHODS = frozenset({"naive", "mean", "linear"})


class ObservationIssue(str):
    def __new__(
        cls,
        message: str,
        *,
        code: str = "invalid_observation",
        index: int | None = None,
    ) -> ObservationIssue:
        obj = super().__new__(cls, message)
        obj.code = code
        obj.message = message
        obj.index = index
        return obj

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            if key in {"code"}:
                return self.code
            if key in {"message", "msg", "detail"}:
                return self.message
            if key in {"index", "position"}:
                return self.index
        return super().__getitem__(key)


class ConfidenceInterval(tuple):
    def __new__(cls, lower: Any, upper: Any) -> ConfidenceInterval:
        return super().__new__(cls, (float(lower), float(upper)))

    @property
    def lower(self) -> float:
        return float(self[0])

    @property
    def upper(self) -> float:
        return float(self[1])

    def __reduce__(self) -> tuple[Any, tuple[float, float]]:
        return (ConfidenceInterval, (self[0], self[1]))

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            if key in {"lower", "lo", "min", "low"}:
                return self[0]
            if key in {"upper", "hi", "max", "high"}:
                return self[1]
            raise KeyError(key)
        return super().__getitem__(key)


@dataclass
class ForecastResult:
    method: str
    historical: list[dict[str, Any]]
    forecast: list[dict[str, Any]]
    historical_periods: list[Any]
    historical_values: list[float]
    forecast_periods: list[Any]
    forecast_values: list[float]
    assumptions: list[str]
    limitations: list[str]
    evaluation: dict[str, float] | None = None
    confidence_intervals: list[ConfidenceInterval] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        try:
            value = float(value)
        except (InvalidOperation, ValueError, TypeError):
            return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _normalize_period(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return str(int(value))
        return str(value)
    return str(value).strip()


def _std(values: list[float], ddof: int = 1) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    mean = sum(values) / n
    sq = sum((v - mean) ** 2 for v in values)
    denom = n - ddof
    if denom <= 0:
        denom = 1
    return math.sqrt(sq / denom)


def _least_squares(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return 0.0, mean_y
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=False)) / denom
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _one_step_forecast(method: str, obs: list[dict[str, Any]]) -> float:
    values = [float(o["value"]) for o in obs]
    n = len(values)
    if method == "naive":
        return values[-1]
    if method == "mean":
        return sum(values) / n
    if method == "linear":
        xs = [float(i) for i in range(n)]
        slope, intercept = _least_squares(xs, values)
        return intercept + slope * float(n)
    raise ValueError(f"unknown method: {method}")


def _extend_periods(periods: list[Any], horizon: int) -> list[Any]:
    nums: list[int] = []
    all_int = True
    for period in periods:
        try:
            number = float(period)
        except (TypeError, ValueError):
            all_int = False
            break
        if not number.is_integer():
            all_int = False
            break
        nums.append(int(number))
    if all_int and nums:
        if len(nums) >= 2:
            diffs = [nums[i + 1] - nums[i] for i in range(len(nums) - 1)]
            if all(diff == diffs[0] for diff in diffs) and diffs[0] != 0:
                step = diffs[0]
            else:
                step = diffs[-1] if diffs and diffs[-1] != 0 else 1
        else:
            step = 1
        last = nums[-1]
        return [str(last + step * (i + 1)) for i in range(horizon)]
    return [f"Forecast {i + 1}" for i in range(horizon)]


class ForecastingService:
    @staticmethod
    def validate_observations(obs: Any) -> tuple[list[dict[str, Any]], list[ObservationIssue]]:
        valid_obs: list[dict[str, Any]] = []
        issues: list[ObservationIssue] = []
        if not isinstance(obs, (list, tuple)):
            issues.append(
                ObservationIssue(
                    "observations must be a list of dicts with 'period' and 'value'",
                    code="observations_not_list",
                    index=None,
                )
            )
            return valid_obs, issues
        seen_periods: set[str] = set()
        for index, item in enumerate(obs):
            if not isinstance(item, Mapping):
                issues.append(
                    ObservationIssue(
                        f"observation {index} must be a mapping",
                        code="observation_not_mapping",
                        index=index,
                    )
                )
                continue
            if "period" not in item or item.get("period") is None:
                issues.append(
                    ObservationIssue(
                        f"observation {index} is missing 'period'",
                        code="missing_period",
                        index=index,
                    )
                )
                continue
            period_raw = item.get("period")
            period = _normalize_period(period_raw)
            if period == "":
                issues.append(
                    ObservationIssue(
                        f"observation {index} has an empty 'period'",
                        code="empty_period",
                        index=index,
                    )
                )
                continue
            if "value" not in item:
                issues.append(
                    ObservationIssue(
                        f"observation {index} is missing 'value'",
                        code="missing_value",
                        index=index,
                    )
                )
                continue
            value = _coerce_float(item.get("value"))
            if value is None:
                issues.append(
                    ObservationIssue(
                        f"observation {index} has a non-numeric 'value'",
                        code="invalid_value",
                        index=index,
                    )
                )
                continue
            if period in seen_periods:
                issues.append(
                    ObservationIssue(
                        f"observation {index} repeats period {period!r}",
                        code="duplicate_period",
                        index=index,
                    )
                )
                continue
            seen_periods.add(period)
            valid_obs.append({"period": period, "value": value})
        return valid_obs, issues

    @staticmethod
    def forecast(
        observations: Any,
        horizon: int = 1,
        method: str = "naive",
    ) -> dict[str, Any]:
        try:
            horizon_int = int(horizon)
        except (TypeError, ValueError) as exc:
            raise ValueError("horizon must be a positive integer") from exc
        if horizon_int < 1:
            raise ValueError("horizon must be a positive integer")

        method_name = str(method).strip().lower()
        if method_name not in _METHODS:
            raise ValueError(f"method must be one of {sorted(_METHODS)}")

        valid_obs, issues = ForecastingService.validate_observations(observations)
        if issues:
            raise ValueError("; ".join(str(issue) for issue in issues))

        min_required = 3 if method_name == "linear" else 2
        if len(valid_obs) < min_required:
            raise ValueError(
                f"insufficient data: need at least {min_required} observations for "
                f"{method_name}, got {len(valid_obs)}"
            )

        values = [float(o["value"]) for o in valid_obs]
        periods = [o["period"] for o in valid_obs]
        n = len(values)

        if method_name == "naive":
            forecast_values = [values[-1] for _ in range(horizon_int)]
        elif method_name == "mean":
            forecast_values = [sum(values) / n for _ in range(horizon_int)]
        else:
            xs = [float(i) for i in range(n)]
            slope, intercept = _least_squares(xs, values)
            forecast_values = [
                intercept + slope * float(n + i) for i in range(horizon_int)
            ]

        forecast_periods = _extend_periods(periods, horizon_int)

        confidence_intervals: list[ConfidenceInterval] | None = None
        if method_name == "linear":
            xs = [float(i) for i in range(n)]
            slope, intercept = _least_squares(xs, values)
            residuals = [values[i] - (intercept + slope * xs[i]) for i in range(n)]
            std = _std(residuals, 1 if n > 1 else 0)
            if std <= 0:
                std = 1e-9
            mean_x = sum(xs) / n
            sxx = sum((x - mean_x) ** 2 for x in xs) or 1.0
            confidence_intervals = []
            for i in range(horizon_int):
                x_future = float(n + i)
                margin = 1.96 * std * math.sqrt(
                    1.0 + 1.0 / n + (x_future - mean_x) ** 2 / sxx
                )
                confidence_intervals.append(
                    ConfidenceInterval(forecast_values[i] - margin, forecast_values[i] + margin)
                )

        evaluation = ForecastingService._evaluate(method_name, valid_obs)

        historical = [{"period": p, "value": v} for p, v in zip(periods, values, strict=False)]
        forecast_list: list[dict[str, Any]] = []
        for i in range(horizon_int):
            entry: dict[str, Any] = {
                "period": forecast_periods[i],
                "value": forecast_values[i],
            }
            if confidence_intervals is not None:
                entry["lower"] = confidence_intervals[i].lower
                entry["upper"] = confidence_intervals[i].upper
            forecast_list.append(entry)

        assumptions: list[str] = [
            "Observations are ordered chronologically by period.",
            "Values are numeric and finite.",
        ]
        limitations: list[str] = [
            "The forecast extrapolates historical patterns and ignores external drivers.",
        ]
        if method_name == "naive":
            assumptions.append("The most recent observed value persists across the horizon.")
            limitations.append("Ignores trend, seasonality, and level shifts.")
        elif method_name == "mean":
            assumptions.append("The series fluctuates around a stable historical mean.")
            limitations.append("Ignores trend and seasonality.")
        else:
            assumptions.append("A linear trend fitted by ordinary least squares continues.")
            limitations.append("Sensitive to outliers and assumes a constant slope.")
            if confidence_intervals is not None:
                assumptions.append("Residuals are approximately normal for interval coverage.")
                limitations.append("Confidence intervals are residual-based approximations.")
        if evaluation is None:
            limitations.append("Insufficient data for chronological holdout evaluation.")

        result: dict[str, Any] = {
            "method": method_name,
            "historical": historical,
            "forecast": forecast_list,
            "historical_periods": list(periods),
            "historical_values": list(values),
            "forecast_periods": list(forecast_periods),
            "forecast_values": list(forecast_values),
            "periods": list(forecast_periods),
            "values": list(forecast_values),
            "assumptions": assumptions,
            "limitations": limitations,
            "evaluation": evaluation,
            "confidence_intervals": confidence_intervals,
            "confidence_interval": confidence_intervals,
            "ci": confidence_intervals,
        }
        return result

    @staticmethod
    def _evaluate(
        method: str, obs: list[dict[str, Any]]
    ) -> dict[str, float] | None:
        n = len(obs)
        min_required = 3 if method == "linear" else 1
        holdout = max(1, n // 5)
        if holdout < 1 or n - holdout < min_required:
            return None
        preds: list[float] = []
        actuals: list[float] = []
        for j in range(holdout):
            train = obs[: n - holdout + j]
            if len(train) < min_required:
                return None
            try:
                pred = _one_step_forecast(method, train)
            except ValueError:
                return None
            preds.append(float(pred))
            actuals.append(float(obs[n - holdout + j]["value"]))
        errors = [a - p for a, p in zip(actuals, preds, strict=False)]
        mae = sum(abs(e) for e in errors) / len(errors)
        rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
        return {
            "mae": mae,
            "rmse": rmse,
            "MAE": mae,
            "RMSE": rmse,
            "mean_absolute_error": mae,
            "root_mean_squared_error": rmse,
        }

    @staticmethod
    def scenario_analysis(
        base_obs: Any,
        horizon: int = 1,
        adjustments: Any = None,
    ) -> dict[str, Any]:
        try:
            horizon_int = int(horizon)
        except (TypeError, ValueError) as exc:
            raise ValueError("horizon must be a positive integer") from exc
        if horizon_int < 1:
            raise ValueError("horizon must be a positive integer")

        valid_obs, issues = ForecastingService.validate_observations(base_obs)
        if issues:
            raise ValueError("; ".join(str(issue) for issue in issues))

        n = len(valid_obs)
        method = "linear" if n >= 3 else "naive"
        if n < 2:
            raise ValueError("insufficient data: need at least 2 observations")

        multipliers: dict[str, float] = {
            "conservative": 0.9,
            "baseline": 1.0,
            "optimistic": 1.1,
        }
        additives: dict[str, float] = {
            "conservative": 0.0,
            "baseline": 0.0,
            "optimistic": 0.0,
        }

        if isinstance(adjustments, Mapping):
            if isinstance(adjustments.get("method"), str):
                method = str(adjustments["method"]).strip().lower()
            if isinstance(adjustments.get("multipliers"), Mapping):
                for key, val in adjustments["multipliers"].items():
                    if key in multipliers:
                        coerced = _coerce_float(val)
                        if coerced is not None:
                            multipliers[key] = coerced
            if isinstance(adjustments.get("additives"), Mapping):
                for key, val in adjustments["additives"].items():
                    if key in additives:
                        coerced = _coerce_float(val)
                        if coerced is not None:
                            additives[key] = coerced
            for name in ("conservative", "baseline", "optimistic"):
                if name in adjustments:
                    val = adjustments[name]
                    if isinstance(val, Mapping):
                        for mk in ("multiplier", "factor", "scale"):
                            if mk in val:
                                coerced = _coerce_float(val[mk])
                                if coerced is not None:
                                    multipliers[name] = coerced
                        for ak in ("additive", "delta", "offset", "adjustment"):
                            if ak in val:
                                coerced = _coerce_float(val[ak])
                                if coerced is not None:
                                    additives[name] = coerced
                    else:
                        coerced = _coerce_float(val)
                        if coerced is not None:
                            multipliers[name] = coerced
        elif isinstance(adjustments, (list, tuple)):
            vals = list(adjustments)
            if len(vals) >= 1:
                c = _coerce_float(vals[0])
                if c is not None:
                    multipliers["conservative"] = c
            if len(vals) >= 2:
                c = _coerce_float(vals[1])
                if c is not None:
                    multipliers["baseline"] = c
            if len(vals) >= 3:
                c = _coerce_float(vals[2])
                if c is not None:
                    multipliers["optimistic"] = c

        if method not in _METHODS:
            method = "linear" if n >= 3 else "naive"

        base_result = ForecastingService.forecast(valid_obs, horizon_int, method)

        scenarios: dict[str, dict[str, Any]] = {}
        for name in ("conservative", "baseline", "optimistic"):
            scenarios[name] = ForecastingService._apply_scenario(
                base_result,
                multipliers[name],
                additives[name],
                name,
            )

        return {
            "method": method,
            "base_method": method,
            "scenarios": scenarios,
            "conservative": scenarios["conservative"],
            "baseline": scenarios["baseline"],
            "optimistic": scenarios["optimistic"],
            "adjustments": {
                "multipliers": dict(multipliers),
                "additives": dict(additives),
            },
        }

    @staticmethod
    def _apply_scenario(
        base_result: dict[str, Any],
        multiplier: float,
        additive: float,
        name: str,
    ) -> dict[str, Any]:
        result = copy.deepcopy(base_result)
        base_cis = base_result.get("confidence_intervals")
        new_forecast: list[dict[str, Any]] = []
        new_values: list[float] = []
        new_cis: list[ConfidenceInterval] | None = None
        if base_cis is not None:
            new_cis = []
        for i, item in enumerate(base_result["forecast"]):
            value = float(item["value"]) * float(multiplier) + float(additive)
            new_values.append(value)
            entry: dict[str, Any] = {"period": item["period"], "value": value}
            if new_cis is not None and i < len(base_cis):
                ci = base_cis[i]
                new_ci = ConfidenceInterval(
                    float(ci.lower) * float(multiplier) + float(additive),
                    float(ci.upper) * float(multiplier) + float(additive),
                )
                new_cis.append(new_ci)
                entry["lower"] = new_ci.lower
                entry["upper"] = new_ci.upper
            new_forecast.append(entry)
        result["forecast"] = new_forecast
        result["forecast_values"] = new_values
        result["values"] = new_values
        result["confidence_intervals"] = new_cis
        result["confidence_interval"] = new_cis
        result["ci"] = new_cis
        result["assumptions"] = [*list(base_result["assumptions"]), f"Scenario {name!r}: multiplier={multiplier}, additive={additive}."]
        result["limitations"] = list(base_result["limitations"])
        return result


# Module-level convenience API.
def validate_observations(obs: Any) -> tuple[list[dict[str, Any]], list[ObservationIssue]]:
    return ForecastingService.validate_observations(obs)


def forecast(
    observations: Any, horizon: int = 1, method: str = "naive"
) -> dict[str, Any]:
    return ForecastingService.forecast(observations, horizon, method)


def scenario_analysis(
    base_obs: Any, horizon: int = 1, adjustments: Any = None
) -> dict[str, Any]:
    return ForecastingService.scenario_analysis(base_obs, horizon, adjustments)


def run_forecast(
    observations: Any, horizon: int = 1, method: str = "naive"
) -> dict[str, Any]:
    return forecast(observations, horizon, method)


def run_scenario_analysis(
    base_obs: Any, horizon: int = 1, adjustments: Any = None
) -> dict[str, Any]:
    return scenario_analysis(base_obs, horizon, adjustments)


ForecastService = ForecastingService