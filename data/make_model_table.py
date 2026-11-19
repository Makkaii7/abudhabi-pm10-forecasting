"""Make the shared model table from the daily pollution file. Every model reads this one table.

One row = one station on one day ("today"). The model reads the row and predicts tomorrow's PM10.

Columns:
  station_id, station, day       which station, and which day is "today"
  pm10_6d_ago ... pm10_1d_ago    the PM10 daily average of the six days before today
  pm10_today                     today's PM10 daily average
  no2_today, so2_today           today's NO2 and SO2 daily averages
  pm10_tomorrow                  the answer: tomorrow's PM10 daily average
  split                          train, validation or test

A row is kept only when nothing in it is missing. A daily average counts as known when the station has
18 or more of the 24 hourly readings that day. So PM10 must be known on all seven days and on the next
day, and NO2 and SO2 must be known today.

The split is by date and never shuffled, like in the research report:
  train        today is before 1 December 2023
  validation   today is in December 2023       (for choosing a model's settings)
  test         today is in 2024                (used once, at the very end)

Run:   python make_model_table.py      (needs pandas)
Saves: model_table.csv
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent                     # the folder this script is in
DAILY_FILE = HERE / "openaq_daily_all_stations.csv"
OUT_FILE = HERE / "model_table.csv"

FULL_DAY = 18                                    # hourly readings needed to trust a daily average
HISTORY = 7                                      # days of PM10 in one row, today included
VALIDATION_START = pd.Timestamp("2023-12-01")
TEST_START = pd.Timestamp("2024-01-01")


def known_daily_averages(daily):
    """One row per station and day, one column per pollutant. Only daily averages we can trust."""
    full = daily[daily["readings"] >= FULL_DAY]
    return full.pivot(index=["station_id", "day"], columns="parameter", values="mean")


def rows_of_one_station(averages):
    """The model rows of one station. `averages` has one row per day and one column per pollutant."""
    calendar = pd.date_range(averages.index.min(), averages.index.max(), freq="D")
    averages = averages.reindex(calendar)        # a day without data becomes an empty row
    rows = pd.DataFrame(index=calendar)
    for days_ago in range(HISTORY - 1, 0, -1):   # 6, 5, 4, 3, 2, 1
        rows[f"pm10_{days_ago}d_ago"] = averages["pm10"].shift(days_ago)
    rows["pm10_today"] = averages["pm10"]
    rows["no2_today"] = averages["no2"]
    rows["so2_today"] = averages["so2"]
    rows["pm10_tomorrow"] = averages["pm10"].shift(-1)
    rows = rows.dropna()                         # keep a row only when nothing in it is missing
    return rows.rename_axis("day").reset_index()


def split_of(day):
    """train, validation or test, decided by the date only."""
    if day >= TEST_START:
        return "test"
    if day >= VALIDATION_START:
        return "validation"
    return "train"


# ---- 1. read the daily file and keep the daily averages we can trust
daily = pd.read_csv(DAILY_FILE, parse_dates=["day"])
names = daily.drop_duplicates("station_id").set_index("station_id")["station"]
averages = known_daily_averages(daily)

# ---- 2. build the rows, station by station
parts = []
for station_id in averages.index.get_level_values("station_id").unique():
    rows = rows_of_one_station(averages.loc[station_id])
    rows.insert(0, "station", names[station_id])
    rows.insert(0, "station_id", station_id)
    parts.append(rows)
table = pd.concat(parts, ignore_index=True)
table["split"] = table["day"].apply(split_of)
table = table.round(2)

# ---- 3. save
table.to_csv(OUT_FILE, index=False)
print(f"saved {OUT_FILE.name}: {len(table)} rows, {table['station_id'].nunique()} stations")
print("columns:", list(table.columns))

# ---- 4. checks
print("\nempty cells:", int(table.isna().sum().sum()))
summary = table.groupby("split").agg(rows=("day", "size"), days=("day", "nunique"),
                                     first_day=("day", "min"), last_day=("day", "max"))
print(summary.loc[["train", "validation", "test"]].to_string())
