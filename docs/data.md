# Data sources

Reference for building against our two data sources: how to get access, how the data is shaped,
and the quirks we've hit. It holds **no one's actual values**. Real data never goes in the repo.
Handling rules are in [CLAUDE.md](../CLAUDE.md) and decisions D18–D20 in [decisions.md](decisions.md).

- [Fitbit via the Google Health API](#fitbit-via-the-google-health-api): live data for the app
- [mcPHASES](#mcphases): labeled research data for building and evaluating the phase model

---

## Fitbit via the Google Health API

Last checked: 2026-10-26, Fitbit Air, `notebooks/fitbit_test_pull.ipynb`.

### Access

- Access goes through the **course OAuth app** (BINF 4070, Lab 3), not our own Google Cloud project.
  1. Open the [course authorization helper](https://binf4070-health-oauth-helper-7pw5f3iaiq-ue.a.run.app/authorize)
     with the Google account your Fitbit syncs to.
  2. Grant all three read permissions: activity and fitness, health metrics and measurements, and sleep.
  3. Put the two values the helper gives you in `.env` as `GOOGLE_HEALTH_REFRESH_TOKEN` and
     `GOOGLE_HEALTH_HELPER_TOKEN`. Never paste them into a chat or an AI tool.
- The client exchanges that token pair at the helper's `/refresh` endpoint for a short-lived access
  token, which it keeps in memory only.
- The access is **read-only**. We can't write anything back to Google Health.
- If a token is exposed, revoke the course app in
  [Google Account connections](https://myaccount.google.com/connections), then authorize again.
- Code:
  - Client: `signals/google_health.py`
  - Test pull: `notebooks/fitbit_test_pull.ipynb`
  - Raw pulls are cached as `data/raw/fitbit/<type>_<start>_<end>.json` (gitignored, `"source": "real"`).

### Endpoint

`GET https://health.googleapis.com/v4/users/me/dataTypes/{type}/dataPoints`
([reference](https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/list))

| Param | Notes |
|---|---|
| `filter` | Date range ([AIP-160](https://google.aip.dev/160) syntax), e.g. `daily_resting_heart_rate.date >= "2026-10-01" AND daily_resting_heart_rate.date < "2026-10-08"`. Only `>=`, `<`, `AND` (and `OR` for sleep). |
| `pageSize` | Max 10,000, except 25 for `sleep`. |
| `pageToken` | Pass the `nextPageToken` from the previous page. An empty token means that was the last page. |
| `dataSourceFamily` | `all-sources` (default), `google-wearables`, `google-sources` or `self-sources`. Not allowed for `sleep`. |

- Results come newest first.
- Rate limit: 300 requests per minute per user.

### Data types

Every type below returned data through the course app. **Granularity** is how often the device
records that type, not how much any one person has.

| Signal | Type | Filter field | Key fields | Granularity |
|---|---|---|---|---|
| Skin temp | `daily-sleep-temperature-derivations` | `daily_sleep_temperature_derivations.date` | `nightlyTemperatureCelsius`, `baselineTemperatureCelsius`, `relativeNightlyStddev30dCelsius` | 1 per night |
| Resting HR | `daily-resting-heart-rate` | `daily_resting_heart_rate.date` | `beatsPerMinute`\*, `dailyRestingHeartRateMetadata.calculationMethod` | 1 per day |
| HRV | `daily-heart-rate-variability` | `daily_heart_rate_variability.date` | `averageHeartRateVariabilityMilliseconds`, `deepSleepRootMeanSquareOfSuccessiveDifferencesMilliseconds`, `nonRemHeartRateBeatsPerMinute`\*, `entropy` | 1 per night |
| HRV samples | `heart-rate-variability` | `heart_rate_variability.sample_time.civil_time` | `rootMeanSquareOfSuccessiveDifferencesMilliseconds`, `metadata.highFrequencyPower`, `metadata.lowFrequencyPower` | every 5 min during sleep |
| Respiratory rate | `daily-respiratory-rate` | `daily_respiratory_rate.date` | `breathsPerMinute` | 1 per night |
| Resp. rate by sleep stage | `respiratory-rate-sleep-summary` | `respiratory_rate_sleep_summary.sample_time.civil_time` | `deepSleepStats`, `lightSleepStats`, `remSleepStats`, `fullSleepStats`, each with `breathsPerMinute`, `standardDeviation`, `signalToNoise` | about 1 per night |
| SpO2 | `daily-oxygen-saturation` | `daily_oxygen_saturation.date` | `averagePercentage`, `lowerBoundPercentage`, `upperBoundPercentage`, `standardDeviationPercentage` | 1 per night |
| SpO2 samples | `oxygen-saturation` | `oxygen_saturation.sample_time.civil_time` | `percentage` | every minute during sleep |
| Sleep | `sleep` | `sleep.interval.civil_end_time` | `interval` (start/end), `type` (e.g. `STAGES`), `stages[]` (`startTime`, `endTime`, `type` e.g. `AWAKE`), `summary`, `metadata` | per session; naps add sessions |
| Steps | `steps` | `steps.interval.civil_start_time` | `count`\*, `interval` | 1-minute intervals |
| Heart rate | `heart-rate` | `heart_rate.sample_time.civil_time` | not inspected yet | every ~3 s (~33k points/day) |

\* These numbers come back as strings (`"beatsPerMinute": "63"`). Convert them when parsing.

**Every other type in the [DataPoint reference](https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints)**
(checked by asking each for its latest point; "empty" means the permission works but this device
or person had nothing recorded):

| Result | Types |
|---|---|
| **Can't be read** ("List is not supported", write-only) | `menstrual-period`, `ovulation-test`, `symptoms`, `moods`, `floors` |
| **No permission** (403; outside the course app's scopes) | `nutrition-log`, `hydration-log`, `electrocardiogram`, `irregular-rhythm-notification` |
| **Allowed, empty** for a Fitbit Air | `core-body-temperature`, `blood-glucose`, `body-fat`, `altitude`, `vo2-max`, `daily-vo2-max`, `run-vo2-max`, `basal-energy-burned` |
| **Has data** (activity; not used yet) | `exercise`, `distance`, `active-zone-minutes`, `active-minutes`, `activity-level`, `sedentary-period`, `active-energy-burned`, `time-in-heart-rate-zone`, `daily-heart-rate-zones`, `swim-lengths-data` |
| **Has data** (manual entries) | `weight`, `height` |

What this means for Inkling:
- **All self-logged cycle data is write-only** (periods, ovulation tests, symptoms, moods). Period
  dates and symptoms must come from our own check-in.
- **Core body temperature** (basal body temperature) is not recorded by the Fitbit Air. It would
  need a thermometer or a manual log, so nightly skin temperature is our temperature signal.

### Shape of a data point

```jsonc
{
  "name": "users/<numeric Google account id>/dataTypes/...",   // only on some types; NEVER copy this
  "dataSource": {
    "recordingMethod": "DERIVED",               // or PASSIVELY_MEASURED
    "device": {"displayName": "Fitbit Air", "formFactor": "FITNESS_BAND"},
    "platform": "FITBIT",
    "application": {"packageName": "..."}       // present when a phone app recorded it
  },
  "dailyRestingHeartRate": { ... }              // one payload key, the type name in camelCase
}
```

- **Times:**
  - `physicalTime` / `startTime` / `endTime` are RFC-3339 UTC, paired with a `utcOffset` like `"-14400s"`.
  - `civilTime` is local time as an object: `{"date": {"year", "month", "day"}, "time": {"hours", "minutes", ...}}`.
  - Daily types have a `date` object in the same `{year, month, day}` form.
- **Which day a value belongs to:** sleep-derived daily values (temperature, HRV, RHR, SpO2, respiratory
  rate) are dated the day you **wake up**.
- **Missing data:** a missing day is no data point at all, never a zero.
- **Identifiers:** `name` contains the account's Google user id. It stays in the raw cache and never
  goes into records, fixtures or logs. Use our own `user_id`.

### Quirks we've hit

- **Long intraday ranges fail.** 35 days of `heart-rate` in one request returned HTTP 503. The client
  pulls in 7-day chunks.
- **Temporary server errors.** `steps` and `sleep` sometimes return 500/503 on a request that worked
  minutes earlier. The client retries 429 and 5xx errors with backoff.
- **Steps can come from the phone.** Step points with `dataSource.application.packageName` are from
  a phone app. Use `dataSourceFamily=google-wearables` if we want watch-only steps.
- **Temperature is not a deviation.** The API returns the nightly value plus Fitbit's own baseline, so
  the deviation is nightly minus baseline. The first night or so after setup may have no value.
- **Filter field names** in snake_case (as in Lab 3) work. The docs also show camelCase
  (`dailyHeartRateVariability.date`).
- **Stale code in notebooks.** Restart the kernel after changing `signals/`. The test-pull notebook
  autoreloads.

### Mapping to `DailyRecord` (proposal, not decided)

| Contract field | Proposed source | Open question |
|---|---|---|
| `rhr_bpm` | `daily-resting-heart-rate.beatsPerMinute` | none |
| `hrv_rmssd_ms` | `daily-heart-rate-variability`: the average or the deep-sleep RMSSD | Pick whichever matches mcPHASES, so the model transfers |
| `skin_temp_dev_c` | `nightlyTemperatureCelsius − baselineTemperatureCelsius` | Keep `relativeNightlyStddev30dCelsius` for confidence? |
| `sleep_min` | Sum of non-`AWAKE` stages across that day's sessions | Count naps? |
| `steps` | Sum of `steps.count` per civil day | Watch only, or include the phone? |
| (new?) | `daily-respiratory-rate.breathsPerMinute` | Add to the contract (v0.2)? |
| `date` | Wake-up day for sleep-derived values | none |

---

## mcPHASES

Access is under PhysioNet's **restricted-access DUA**:
- Everyone downloads their own copy into `data/raw/mcphases/`.
- Claude never reads the raw files.
- Only **schema and aggregates** go in this section: column names, types, counts, % missing,
  summary stats. Never rows, and never one participant's series.

### Files and tables
TBD (from the schema script).

### Wearable signals
TBD: which signals, units, sampling rate, and how they line up with the Fitbit types above.

### Hormone and phase labels
TBD: which hormones, how phase is defined, and how often labels exist.

### Coverage and missingness (aggregate)
TBD.

### Mapping to `DailyRecord` / `PhaseEstimate`
TBD, including mismatches with the Fitbit fields above.
