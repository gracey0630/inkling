"""Google Health API (Fitbit) client, via the BINF 4070 course OAuth helper (adapted from Lab 3).

Credentials come from .env (GOOGLE_HEALTH_REFRESH_TOKEN, GOOGLE_HEALTH_HELPER_TOKEN) and are never
printed. The short-lived access token is kept in memory only. Everything pulled is real personal
data: it is saved under data/raw/fitbit/ (gitignored) and labeled source="real".
"""

import json
import os
import statistics
import time
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import requests
from dotenv import load_dotenv

API_BASE = "https://health.googleapis.com/v4"
HELPER_BASE = "https://binf4070-health-oauth-helper-7pw5f3iaiq-ue.a.run.app"
REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw" / "fitbit"

# Date filter field per data type, from the AIP-160 patterns in the dataPoints.list reference
# (interval, sample, daily summary, sleep). None = filter field unknown; pull one unfiltered page.
# menstrual-period is absent on purpose: the API does not support listing it (write-only).
# heart-rate is intraday (~1 sample / 3 s, ~33k points/day); daily-resting-heart-rate covers RHR.
FILTER_FIELDS: dict[str, str | None] = {
    "steps": "steps.interval.civil_start_time",
    "heart-rate": "heart_rate.sample_time.civil_time",
    "sleep": "sleep.interval.civil_end_time",
    "daily-resting-heart-rate": "daily_resting_heart_rate.date",
    "daily-heart-rate-variability": "daily_heart_rate_variability.date",
    "heart-rate-variability": "heart_rate_variability.sample_time.civil_time",
    "daily-sleep-temperature-derivations": "daily_sleep_temperature_derivations.date",
    "oxygen-saturation": "oxygen_saturation.sample_time.civil_time",
    "daily-oxygen-saturation": "daily_oxygen_saturation.date",
    "daily-respiratory-rate": "daily_respiratory_rate.date",
    "respiratory-rate-sleep-summary": "respiratory_rate_sleep_summary.sample_time.civil_time",
}
MAX_PAGE_SIZE = {"sleep": 25}  # every other type allows up to 10000
CHUNK_DAYS = 7  # long ranges of intraday data (35 days of heart-rate) fail with HTTP 503
RETRY_STATUSES = {429, 500, 502, 503, 504}  # seen intermittently on steps and sleep
RETRY_WAITS_S = [2, 5, 15, 0]  # wait after each failed try; the last try is not retried

_token_cache = {"value": None, "expires_at": 0.0}


def _access_token() -> str:
    """Exchange the course token pair for a short-lived access token, cached in memory."""
    if _token_cache["value"] and time.monotonic() < _token_cache["expires_at"]:
        return _token_cache["value"]
    load_dotenv(REPO_ROOT / ".env")
    response = requests.post(
        f"{HELPER_BASE}/refresh",
        json={"refresh_token": os.environ["GOOGLE_HEALTH_REFRESH_TOKEN"]},
        headers={
            "Authorization": f"Bearer {os.environ['GOOGLE_HEALTH_HELPER_TOKEN']}",
            "Accept": "application/json",
        },
        timeout=30,
        allow_redirects=False,
    )
    response.raise_for_status()
    payload = response.json()
    # Refresh at least one minute before the helper-reported expiry.
    _token_cache.update(
        value=payload["access_token"],
        expires_at=time.monotonic() + payload["expires_in"] - 60,
    )
    return _token_cache["value"]


def date_filter(data_type: str, start: date, end: date) -> str | None:
    """AIP-160 filter for start <= day < end, or None if the type's filter field is unknown."""
    field = FILTER_FIELDS.get(data_type)
    if field is None:
        return None
    return f'{field} >= "{start.isoformat()}" AND {field} < "{end.isoformat()}"'


def list_points(data_type: str, start: date, end: date) -> list[dict]:
    """All DataPoints of one type with start <= day < end. Raises requests.HTTPError on failure."""
    if FILTER_FIELDS.get(data_type) is None:
        return _list_window(data_type, start, end)
    points, chunk_start = [], start
    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), end)
        points.extend(_list_window(data_type, chunk_start, chunk_end))
        chunk_start = chunk_end
    return points


def _get_page(url: str, params: dict) -> dict:
    """GET one page, retrying transient errors (429 and 5xx) with backoff before giving up."""
    for wait_s in RETRY_WAITS_S:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {_access_token()}", "Accept": "application/json"},
            params=params,
            timeout=60,
        )
        if response.status_code not in RETRY_STATUSES:
            break
        time.sleep(wait_s)
    response.raise_for_status()
    return response.json()


def _list_window(data_type: str, start: date, end: date) -> list[dict]:
    params = {"pageSize": MAX_PAGE_SIZE.get(data_type, 10000)}
    filter_ = date_filter(data_type, start, end)
    if filter_:
        params["filter"] = filter_
    points, seen_tokens = [], set()
    while True:
        page = _get_page(f"{API_BASE}/users/me/dataTypes/{data_type}/dataPoints", params)
        points.extend(page.get("dataPoints", []))
        token = page.get("nextPageToken", "")
        # Without a date filter we only want a first look, not the whole history.
        if not token or not filter_:
            return points
        if token in seen_tokens:
            raise RuntimeError(f"{data_type}: Google Health repeated a nextPageToken.")
        seen_tokens.add(token)
        params["pageToken"] = token


def save_raw(data_type: str, points: list[dict], start: date, end: date) -> Path:
    """Write a pull to data/raw/fitbit/ (gitignored) with its provenance."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{data_type}_{start.isoformat()}_{end.isoformat()}.json"
    record = {
        "source": "real",
        "data_type": data_type,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "pulled_at": datetime.now(UTC).isoformat(),
        "filter": date_filter(data_type, start, end),
        "dataPoints": points,
    }
    path.write_text(json.dumps(record, indent=1))
    return path


def field_paths(points: list[dict], limit: int = 200) -> list[str]:
    """Sorted dotted paths of the leaf fields seen in the first `limit` points."""
    paths: set[str] = set()

    def walk(value, prefix: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{prefix}.{key}" if prefix else key)
        elif isinstance(value, list):
            for child in value:
                walk(child, f"{prefix}[]")
        else:
            paths.add(prefix)

    for point in points[:limit]:
        walk(point, "")
    return sorted(paths)


def _payload(point: dict) -> dict:
    """The type-specific part of a DataPoint, e.g. point["dailyRestingHeartRate"]."""
    return next(v for k, v in point.items() if k not in ("name", "dataSource"))


def _point_time(payload: dict) -> datetime | None:
    if "sampleTime" in payload:
        return datetime.fromisoformat(payload["sampleTime"]["physicalTime"])
    if "interval" in payload:
        return datetime.fromisoformat(payload["interval"]["startTime"])
    return None


def _point_day(payload: dict) -> date | None:
    """Local (civil) day of a point: daily `date`, sample civil date, or interval civil start."""
    d = (
        payload.get("date")
        or payload.get("sampleTime", {}).get("civilTime", {}).get("date")
        or payload.get("interval", {}).get("civilStartTime", {}).get("date")
    )
    if d:
        return date(d["year"], d["month"], d["day"])
    t = _point_time(payload)  # sleep has no civil time; fall back to the UTC start date
    return t.date() if t else None


def coverage(points: list[dict]) -> dict:
    """How often a type has data: points, days with data, first/last day, median gap in minutes."""
    payloads = [_payload(p) for p in points]
    days = sorted({d for d in map(_point_day, payloads) if d})
    times = sorted(t for t in map(_point_time, payloads) if t)
    gaps = [(b - a).total_seconds() / 60 for a, b in pairwise(times) if b > a]
    return {
        "n_points": len(points),
        "days_with_data": len(days),
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "median_gap_min": statistics.median(gaps) if gaps else None,
    }


def probe(data_types: list[str], start: date, end: date, save: bool = True) -> list[dict]:
    """Try each data type once and summarize what comes back. Only an auth failure raises."""
    _access_token()  # fail here, not as a misleading per-type error
    results = []
    for data_type in data_types:
        row = {"data_type": data_type, "status": "ok", "n_points": 0, "fields": [], "saved": None}
        try:
            points = list_points(data_type, start, end)
        except requests.HTTPError as err:
            code = err.response.status_code if err.response is not None else None
            row["status"] = {400: "bad request (filter?)", 403: "forbidden (scope?)"}.get(
                code, f"HTTP {code}"
            )
            results.append(row)
            continue
        row.update(n_points=len(points), fields=field_paths(points))
        if not points:
            row["status"] = "empty"
        elif save:
            row["saved"] = str(save_raw(data_type, points, start, end).relative_to(REPO_ROOT))
        results.append(row)
    return results
