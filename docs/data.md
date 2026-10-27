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

Last checked: 2026-10-27, mcPHASES v1.0.0, `notebooks/mcphases_eda.ipynb`.

Access is under PhysioNet's **restricted-access DUA**:
- Everyone gets their own access and download: see [data/README.md](../data/README.md#getting-mcphases),
  which also lists which files we use and why.
- Claude never reads the raw files.
- This section holds only **schema and aggregates**: column names, types, counts, % missing,
  percentiles. Never rows, and never one participant's series.

### The study

- **42 participants** (menstruating adults, no recent hormonal contraception), wearing a
  **Fitbit Sense** and testing urine hormones daily with a **Mira** monitor.
- **Two rounds:** 2022 (all 42) and 2024 (~20 of them). About 90 days per participant per round:
  the median participant has 90 days, and those in both rounds have ~190.
- **Join keys:** `id` + `day_in_study`. Sleep-based tables use `sleep_start_day_in_study` /
  `sleep_end_day_in_study`. Every table has `study_interval` (2022/2024) and `is_weekend`.
  There are no calendar dates.

### Phase labels and hormones (`hormones_and_selfreport`)

| What | Values | Notes |
|---|---|---|
| `phase` | `Menstrual`, `Follicular`, `Fertility`, `Luteal` | On essentially every day for all 42 participants. ~1,080 menstrual days, so roughly 200 cycles |
| `lh` (mIU/mL), `estrogen` (E3G, ng/mL) | median 4.4 / 100 | 5.7% missing |
| `pdg` (PdG, mcg/mL) | median 3.4 | **67% missing** |

- **The labels come from Mira's own algorithm** working from urine hormones, not from a medical
  measurement of ovulation (no ultrasound). Say so whenever we report accuracy.
- **`Fertility` is a fertile window, not ovulation day.** Our contract's `Phase` has `ovulatory`;
  see the mapping below.

### Self-report (`hormones_and_selfreport`)

- About **41% missing** (the diary was optional in the 2024 round).
- Symptoms (`cramps`, `bloating`, `fatigue`, `headaches`, `moodswing`, `stress`, ...) are **text**,
  not the 0–5 numbers the README describes: `Not at all`, `Very Low/Little`, `Low`, `Moderate`,
  `High`, `Very High`. A handful of rows hold stray numbers 1–5.
- `flow_volume` has 8 levels: `Not at all`, `Spotting / Very Light`, `Light`, `Somewhat Light`,
  `Moderate`, `Somewhat Heavy`, `Heavy`, `Very Heavy`.
- `flow_color` includes `Bright Red`, `Dark Brown / Dark Red`, `Pink`, `Orange`, `Yellow`, `Grey`,
  `Black`, `Other`.

### Wearable signals and how they line up with the Google Health API

| Signal | mcPHASES | Per night | Typical values (p25–p75) | Google Health API |
|---|---|---|---|---|
| Skin temp deviation | `computed_temperature`: `baseline_relative_sample_sum / temperature_samples` | 1 (more with naps) | −0.35 to +0.33 °C | `nightlyTemperatureCelsius − baselineTemperatureCelsius` |
| Skin temp (absolute) | `computed_temperature.nightly_temperature` | 1 | 33.2–34.4 °C | `nightlyTemperatureCelsius` (same scale) |
| RHR | `resting_heart_rate.value` | 1 | 64–74 bpm | `daily-resting-heart-rate` |
| HRV | `heart_rate_variability_details.rmssd`, 5-min samples | ~90 (~7.5 h) | 31–69 ms | `heart-rate-variability` (same 5-min RMSSD) |
| Respiratory rate | `respiratory_rate_summary.full_sleep_breathing_rate` | 1 | 14.4–16.8 /min | `respiratory-rate-sleep-summary` |
| Sleep | `sleep.minutesasleep`, `mainsleep` | 1+ (naps) | 297–459 min asleep | `sleep.summary.minutesAsleep`, `metadata.mainSleep` |

HRV and respiratory rate cover 40 of the 42 participants; the rest cover all 42.

### Cleaning rules (apply before any modeling)

- **Sentinels mean missing:** RHR `value == 0` (with `error == 100`); respiratory rates of `0` or `-1`.
- **Duplicate rows in the 2024 round:** `resting_heart_rate` and `sleep` have up to ~10 rows per
  participant-day in 2024. Deduplicate to one per day (for sleep, use the `mainsleep` session).
- **The day axis doesn't restart:** the 2022 round is days 1–90, and the 2024 round is roughly days
  850–997 (the README says each round starts at day 1). Treat each (participant, round) as its own
  sequence and never bridge the gap.
- **Don't use `wrist_temperature`:** it's minute-level all day, mostly negative, and includes
  off-wrist time. Use `computed_temperature`.
- **Self-report text** needs mapping to ordered levels before use.

### Who is in the data (`subject-info`, one column at a time, groups under 5 suppressed)

- **Age in 2022:** under 20: 17, 20–24: 20, 25–29: 5. So **18–29, nobody under 18**: a good fit
  for young adults, but results can't be claimed for teens.
- **Ethnicity:** East Asian 14, Southeast Asian 10, White 9, Middle Eastern 5, others under 5 each.
  Worth noting because optical sensors can behave differently across skin tones.
- **Age at first period:** mostly 11–12. **Menstrual-health literacy:** mostly medium or high.

### Mapping to the contracts (proposal, not decided; see D25)

| Contract | From mcPHASES | Open question |
|---|---|---|
| `PhaseEstimate.phase` | `Menstrual`→`menstrual`, `Follicular`→`follicular`, `Fertility`→`ovulatory`, `Luteal`→`luteal` | Is "ovulatory" honest for a fertile window, and how do we keep the UI from reading as contraception advice? |
| `DailyRecord.skin_temp_dev_c` | nightly mean deviation (above) | Confirm it matches the API's nightly minus baseline |
| `DailyRecord.hrv_rmssd_ms` | nightly mean of 5-min `rmssd` (drop low `coverage`) | Compute the same way from API samples, not the API's daily average |
| `DailyRecord.rhr_bpm` | `resting_heart_rate.value` (0 = missing) | none |
| `DailyRecord.sleep_min` | `minutesasleep` of the main sleep | Count naps? |
| `CheckIn.bleeding` | `flow_volume`: Not at all→none, Spotting→spot, Light + Somewhat Light→light, Moderate→medium, Somewhat Heavy + Heavy + Very Heavy→heavy | none |
| `CheckIn.pain` (0–10) | `cramps` (6 text levels) | Rescale, or change the contract to the same 6 levels? |
| (new?) respiratory rate | `full_sleep_breathing_rate` | Add in v0.2? Both sources have it |
