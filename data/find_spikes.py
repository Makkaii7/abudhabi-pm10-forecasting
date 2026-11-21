"""Find the unusual PM10 days: days when one station is far above its own usual level.

How a local spike is found, in plain words:
  1. Take one station on one day, and the middle value (the median) of the OTHER stations that day.
  2. Divide the two: how many times higher is this station than the others today?
  3. Every station has its own usual answer to that question. Al Mafraq is usually about twice the
     others, Bida Zayed about two thirds. So divide again by the station's own usual value.
  4. If the result is 3 or more, the day is a local spike: the station is at least 3 times higher
     than is normal for it, and the other stations are not.

Columns of the file (one row per station and day):
  station_id, station, day   which station and which day
  pm10                       the station's PM10 daily average (only days with 18 or more hourly readings)
  others                     the median PM10 of the other stations on the same day
  times_others               pm10 divided by others
  times_usual                times_others divided by the station's usual times_others
  high_day                   True when pm10 is above 150
  local_spike                True when times_usual is 3 or more

Nothing is removed from the data. The two flags only mark the days.

Run:   python find_spikes.py     (needs pandas)
Saves: pm10_spikes.csv
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent                     # the folder this script is in
DAILY_FILE = HERE / "openaq_daily_all_stations.csv"
OUT_FILE = HERE / "pm10_spikes.csv"

FULL_DAY = 18        # hourly readings needed to trust a daily average
MIN_OTHERS = 5       # other stations needed on the same day to compare with
HIGH = 150           # a high day: PM10 above this
SPIKE = 3            # a local spike: this many times the station's usual level, or more


def pm10_by_day_and_station(daily):
    """One row per day, one column per station: the PM10 daily average (full days only)."""
    full = daily[(daily["parameter"] == "pm10") & (daily["readings"] >= FULL_DAY)]
    return full.pivot(index="day", columns="station_id", values="mean")


def median_of_the_others(pm10):
    """For every station and day: the median PM10 of the OTHER stations on that day."""
    others = pd.DataFrame(index=pm10.index, columns=pm10.columns, dtype=float)
    for station_id in pm10.columns:
        rest = pm10.drop(columns=station_id)
        enough = rest.notna().sum(axis=1) >= MIN_OTHERS
        others[station_id] = rest.median(axis=1).where(enough)
    return others


def to_long(wide, name):
    """Turn a day-by-station table into a list: one row per station and day."""
    return wide.reset_index().melt(id_vars="day", var_name="station_id", value_name=name)


# ---- 1. the PM10 of every station and day, and the median of the other stations
daily = pd.read_csv(DAILY_FILE, parse_dates=["day"])
names = daily.drop_duplicates("station_id").set_index("station_id")["station"]
pm10 = pm10_by_day_and_station(daily)
others = median_of_the_others(pm10)

# ---- 2. how far above the others, and how far above the station's own usual level
times_others = pm10 / others
usual = times_others.median()                    # one number per station: its usual level against the others
times_usual = times_others / usual

# ---- 3. one row per station and day, with the two flags
table = to_long(pm10, "pm10")
for name, wide in [("others", others), ("times_others", times_others), ("times_usual", times_usual)]:
    table = table.merge(to_long(wide, name), on=["day", "station_id"])
table = table.dropna(subset=["pm10", "others"])   # keep days the station has, and that can be compared
table["high_day"] = table["pm10"] > HIGH
table["local_spike"] = table["times_usual"] >= SPIKE
table.insert(1, "station", table["station_id"].map(names))
table = table[["station_id", "station", "day", "pm10", "others", "times_others", "times_usual", "high_day", "local_spike"]]
table = table.sort_values(["station_id", "day"]).round(2)

# ---- 4. save
table.to_csv(OUT_FILE, index=False)
print(f"saved {OUT_FILE.name}: {len(table)} rows, {table['station_id'].nunique()} stations, {table['day'].nunique()} days")

# ---- 5. what the list says
spikes = table[table["local_spike"]]
print(f"\nhigh days (PM10 above {HIGH}): {int(table['high_day'].sum())} station-days")
print(f"local spikes ({SPIKE} times the usual level or more): {len(spikes)} station-days at {spikes['station_id'].nunique()} stations")
print("high days that are NOT local spikes:", int((table["high_day"] & ~table["local_spike"]).sum()))
for cut in (2, 3, 5):
    print(f"  with a cut-off of {cut} times: {int((table['times_usual'] >= cut).sum())} station-days")

print("\nusual level of each station against the others (1.0 = the same as the others):")
print(usual.rename(index=names).sort_values(ascending=False).round(2).to_string())

print("\nall local spikes, biggest first:")
print(spikes.sort_values("times_usual", ascending=False)[["station", "day", "pm10", "others", "times_usual"]].to_string(index=False))
