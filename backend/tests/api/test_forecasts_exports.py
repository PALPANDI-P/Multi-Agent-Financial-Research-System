from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.integration


def _workspace(client):
    r = client.post("/api/v1/workspaces", json={"name": "FE"})
    assert r.status_code == 201
    return r.json()["id"]


def test_forecast_observations(client):
    ws = _workspace(client)
    obs = [
        {"period": "2020", "value": 100},
        {"period": "2021", "value": 120},
        {"period": "2022", "value": 140},
    ]
    r = client.post(
        f"/api/v1/workspaces/{ws}/forecasts",
        json={"observations": obs, "horizon": 2, "method": "linear"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["method"] == "linear"
    assert len(body["forecast"]) == 2


def test_forecast_insufficient(client):
    ws = _workspace(client)
    obs = [{"period": "2020", "value": 100}]
    r = client.post(
        f"/api/v1/workspaces/{ws}/forecasts",
        json={"observations": obs, "horizon": 1, "method": "linear"},
    )
    assert r.status_code in (400, 422)


def test_export_csv(client):
    ws = _workspace(client)
    r = client.post(
        f"/api/v1/workspaces/{ws}/exports", json={"format": "csv", "data_type": "metrics"}
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert "attachment" in r.headers.get("content-disposition", "")


def test_export_json(client):
    ws = _workspace(client)
    r = client.post(
        f"/api/v1/workspaces/{ws}/exports", json={"format": "json", "data_type": "metrics"}
    )
    assert r.status_code == 200
    json.loads(r.content)


def test_unknown_workspace(client):
    import uuid

    ws = str(uuid.uuid4())
    r = client.post(
        f"/api/v1/workspaces/{ws}/forecasts",
        json={"observations": [{"period": "2020", "value": 1}], "horizon": 1, "method": "naive"},
    )
    assert r.status_code == 404
