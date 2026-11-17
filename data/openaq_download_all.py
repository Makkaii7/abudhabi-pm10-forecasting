"""Download the daily air-quality data for every Abu Dhabi station in the OpenAQ archive (no account needed).

What it does, in plain words:
  1. Finds the stations that have real data (skips the near-empty ones).
  2. Downloads every day-file of those stations (about 20 stations x about 350 days).
  3. Turns the hourly readings into one row per station, pollutant and day: how many hourly readings,
     the daily average and the daily maximum.
  4. Prints how many usable rows the daily PM10 model would have.
     A usable row = a station on a day where PM10 is known for that day and the 6 days before it,
     and also for the next day (the answer the model has to predict).

Run:   python openaq_download_all.py        (needs requests and pandas; takes a few minutes)
Saves: openaq_daily_all_stations.csv   one row per station, pollutant and day
       openaq_stations.csv             one row per station: id, name, latitude, longitude
"""
import gzip
import io
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

BUCKET = "https://openaq-data-archive.s3.amazonaws.com"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
ABU_DHABI_IDS = list(range(369948, 369975))     # the block of ids OpenAQ gave the Abu Dhabi provider
MIN_DAY_FILES = 100                             # skip stations with almost no data
FULL_DAY = 18                                   # hourly readings needed to trust a daily average
HISTORY = 7                                     # days of PM10 history in one row of the daily model


def list_keys(prefix):
    """All file names under a prefix in the public archive (handles paging)."""
    keys, token = [], None
    while True:
        params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            params["continuation-token"] = token
        r = requests.get(BUCKET + "/", params=params, timeout=60)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        keys += [k.text for k in root.findall("s3:Contents/s3:Key", NS)]
        if root.findtext("s3:IsTruncated", default="false", namespaces=NS) != "true":
            return keys
        token = root.findtext("s3:NextContinuationToken", namespaces=NS)


def download_day_file(key):
    """One day-file as a table of hourly readings (three tries, then give up on that file)."""
    for _ in range(3):
        try:
            r = requests.get(f"{BUCKET}/{key}", timeout=60)
            r.raise_for_status()
            return pd.read_csv(io.BytesIO(gzip.decompress(r.content)))
        except Exception:
            continue
    print("  could not download", key)
    return None


def download_station(station_id, keys):
    """All hourly readings of one station."""
    with ThreadPoolExecutor(max_workers=16) as pool:
        parts = [p for p in pool.map(download_day_file, keys) if p is not None]
    raw = pd.concat(parts, ignore_index=True)
    raw.columns = [c.lower() for c in raw.columns]
    raw["station_id"] = station_id
    return raw


def to_daily(raw):
    """Hourly readings -> one row per station, pollutant and local (UAE) day."""
    raw = raw.copy()
    raw["parameter"] = raw["parameter"].str.lower()
    raw["day"] = pd.to_datetime(raw["datetime"], utc=True).dt.tz_convert("Asia/Dubai").dt.date
    daily = (raw.groupby(["station_id", "parameter", "day"])["value"]
                .agg(readings="count", mean="mean", max="max").reset_index())
    daily["day"] = pd.to_datetime(daily["day"])
    return daily


def usable_rows(pm10_one_station, min_readings, first_day, last_day):
    """Days that can be one row of the daily model: PM10 known on the day, the days before it, and the next day."""
    calendar = pd.date_range(first_day, last_day, freq="D")
    good = pd.Series(False, index=calendar)
    good.loc[pm10_one_station.loc[pm10_one_station["readings"] >= min_readings, "day"]] = True
    has_history = good.rolling(HISTORY).sum() == HISTORY
    has_answer = good.shift(-1, fill_value=False)
    return has_history & has_answer


# ---- 1. which stations have real data
stations, all_keys = [], {}
for sid in ABU_DHABI_IDS:
    keys = list_keys(f"records/csv.gz/locationid={sid}/")
    if len(keys) >= MIN_DAY_FILES:
        all_keys[sid] = keys
print(f"stations with at least {MIN_DAY_FILES} day-files: {len(all_keys)}")

# ---- 2. download them and make the daily table
daily_parts = []
for n, (sid, keys) in enumerate(all_keys.items(), 1):
    raw = download_station(sid, keys)
    name = str(raw["location"].iloc[0]) if "location" in raw else str(sid)
    lat = float(raw["lat"].iloc[0]) if "lat" in raw else float("nan")
    lon = float(raw["lon"].iloc[0]) if "lon" in raw else float("nan")
    stations.append({"station_id": sid, "station": name, "lat": lat, "lon": lon, "day_files": len(keys)})
    daily_parts.append(to_daily(raw))
    print(f"  {n:2d}/{len(all_keys)}  {name}: {len(keys)} day-files, pollutants {sorted(raw['parameter'].str.lower().unique())}")

daily = pd.concat(daily_parts, ignore_index=True)
station_table = pd.DataFrame(stations)
daily = daily.merge(station_table[["station_id", "station"]], on="station_id")
daily.to_csv("openaq_daily_all_stations.csv", index=False)
station_table.to_csv("openaq_stations.csv", index=False)
print("\nsaved openaq_daily_all_stations.csv and openaq_stations.csv")

# ---- 3. how many usable rows for the daily PM10 model
pm10 = daily[daily["parameter"] == "pm10"]
first_day, last_day = daily["day"].min(), daily["day"].max()
print(f"\n=== Daily PM10 model: usable rows ({HISTORY} days of history + the next day), {first_day.date()} to {last_day.date()} ===")
rows = []
for sid, one in pm10.groupby("station_id"):
    rows.append({"station": one["station"].iloc[0],
                 f"days with {FULL_DAY}+ readings": int((one["readings"] >= FULL_DAY).sum()),
                 f"usable rows ({FULL_DAY}+ readings)": int(usable_rows(one, FULL_DAY, first_day, last_day).sum()),
                 "usable rows (12+ readings)": int(usable_rows(one, 12, first_day, last_day).sum())})
summary = pd.DataFrame(rows).sort_values(f"usable rows ({FULL_DAY}+ readings)", ascending=False)
pd.set_option("display.width", 200)
print(summary.to_string(index=False))
print(f"\nstations with PM10: {len(summary)}")
print("total usable rows, all stations together:",
      f"{summary[f'usable rows ({FULL_DAY}+ readings)'].sum()} ({FULL_DAY}+ readings),",
      f"{summary['usable rows (12+ readings)'].sum()} (12+ readings)")

# ---- 4. are the gaps the same days for every station?
calendar = pd.date_range(first_day, last_day, freq="D")
stations_per_day = (pm10[pm10["readings"] >= FULL_DAY].groupby("day")["station_id"].nunique()
                    .reindex(calendar, fill_value=0))
print(f"\ncalendar days: {len(calendar)}")
print(f"days on which NO station has a full day of PM10: {int((stations_per_day == 0).sum())}")
print(f"days on which at least half of the stations have a full day: {int((stations_per_day >= len(summary) / 2).sum())}")
by_year = (stations_per_day > 0).groupby(stations_per_day.index.year).agg(days="count", days_with_data="sum")
print("\nper year: calendar days / days on which at least one station has a full day of PM10")
print(by_year.to_string())
