from datetime import date

import pandas as pd
import pytest
import requests

from contracts import DailyRecord, PhaseEstimate
from signals import google_health as gh
from signals.mcphases import load
from signals.stub import estimate_phase, get_daily_records

START, END = date(2026, 10, 1), date(2026, 10, 3)


def test_stub_matches_contract():
    records = get_daily_records("u1")
    assert records and all(isinstance(r, DailyRecord) and r.user_id == "u1" for r in records)
    assert isinstance(estimate_phase("u1"), PhaseEstimate)


class FakeResponse:
    def __init__(self, body=None, status=200):
        self.body, self.status_code = body or {}, status

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


@pytest.fixture
def fake_api(monkeypatch, tmp_path):
    """Offline Google Health: no token exchange, pages served from a list, saves go to tmp."""
    monkeypatch.setattr(gh, "_access_token", lambda: "test-token")
    monkeypatch.setattr(gh, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(gh, "RAW_DIR", tmp_path / "fitbit")
    calls = []

    def serve(pages):
        def fake_get(url, params, **_):
            calls.append(dict(params))
            return pages.pop(0)

        monkeypatch.setattr(gh.requests, "get", fake_get)
        return calls

    return serve


def test_date_filter_daily_sample_and_unknown():
    assert gh.date_filter("daily-resting-heart-rate", START, END) == (
        'daily_resting_heart_rate.date >= "2026-10-01" AND '
        'daily_resting_heart_rate.date < "2026-10-03"'
    )
    assert gh.date_filter("heart-rate", START, END).startswith("heart_rate.sample_time.civil_time")
    assert gh.date_filter("menstrual-period", START, END) is None


def test_list_points_follows_pages(fake_api):
    calls = fake_api(
        [
            FakeResponse({"dataPoints": [{"a": 1}], "nextPageToken": "p2"}),
            FakeResponse({"dataPoints": [{"a": 2}]}),
        ]
    )
    assert gh.list_points("steps", START, END) == [{"a": 1}, {"a": 2}]
    assert calls[1]["pageToken"] == "p2"


def test_list_points_stops_on_repeated_page_token(fake_api):
    fake_api([FakeResponse({"dataPoints": [], "nextPageToken": "same"})] * 2)
    with pytest.raises(RuntimeError, match="repeated"):
        gh.list_points("steps", START, END)


def test_transient_errors_are_retried(fake_api, monkeypatch):
    monkeypatch.setattr(gh.time, "sleep", lambda _: None)
    ok = FakeResponse({"dataPoints": [{}]})
    fake_api([FakeResponse(status=503), FakeResponse(status=500), ok])
    assert gh.list_points("steps", START, END) == [{}]


def test_persistent_errors_raise_after_retries(fake_api, monkeypatch):
    monkeypatch.setattr(gh.time, "sleep", lambda _: None)
    calls = fake_api([FakeResponse(status=503)] * len(gh.RETRY_WAITS_S))
    with pytest.raises(requests.HTTPError):
        gh.list_points("steps", START, END)
    assert len(calls) == len(gh.RETRY_WAITS_S)


def test_list_points_pulls_long_ranges_in_chunks(fake_api):
    calls = fake_api([FakeResponse({"dataPoints": [{"a": i}]}) for i in range(3)])
    points = gh.list_points("heart-rate", date(2026, 10, 1), date(2026, 10, 16))
    assert len(points) == 3 and len(calls) == 3  # 15 days = 7 + 7 + 1
    assert '>= "2026-10-15"' in calls[2]["filter"]


def test_coverage_counts_days_and_gaps():
    def sample(day, hh, mm):
        return {
            "oxygenSaturation": {
                "sampleTime": {
                    "physicalTime": f"2026-10-{day:02d}T{hh:02d}:{mm:02d}:00Z",
                    "civilTime": {"date": {"year": 2026, "month": 10, "day": day}},
                },
                "percentage": 97,
            }
        }

    daily = {"dailyRestingHeartRate": {"date": {"year": 2026, "month": 10, "day": 2}}}
    cov = gh.coverage([sample(1, 3, 0), sample(1, 3, 1), sample(2, 3, 0)])
    assert cov["days_with_data"] == 2 and cov["median_gap_min"] > 1
    assert gh.coverage([daily])["first_day"] == date(2026, 10, 2)


def test_probe_reports_each_type_and_saves_real(fake_api, tmp_path):
    fake_api(
        [
            FakeResponse({"dataPoints": [{"dailyRestingHeartRate": {"beatsPerMinute": 60}}]}),
            FakeResponse(status=403),
            FakeResponse({"dataPoints": []}),
        ]
    )
    types = ["daily-resting-heart-rate", "daily-sleep-temperature-derivations", "steps"]
    rows = {r["data_type"]: r for r in gh.probe(types, START, END)}
    rhr = rows["daily-resting-heart-rate"]
    assert rhr["fields"] == ["dailyRestingHeartRate.beatsPerMinute"]
    saved = (tmp_path / rhr["saved"]).read_text()
    assert '"source": "real"' in saved
    assert rows["daily-sleep-temperature-derivations"]["status"].startswith("forbidden")
    assert rows["steps"]["status"] == "empty"


def test_mcphases_loader_skips_absent_columns(tmp_path):
    """Synthetic table only: real mcPHASES data never goes in tests."""
    pd.DataFrame({"id": ["a", "b"], "day_in_study": [1, 2], "value": [60.0, 61.0]}).to_csv(
        tmp_path / "resting_heart_rate.csv", index=False
    )
    df = load("resting_heart_rate", ["id", "value", "error"], root=tmp_path)
    assert list(df.columns) == ["id", "value"]
