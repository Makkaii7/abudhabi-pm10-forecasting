# Abu Dhabi PM10 forecasting

COSC 621 course project. We predict tomorrow's PM10 (dust and other particles in the air) at the
Abu Dhabi air quality stations. One shared repository, so that everyone works on the same data file.

## The map

```
abudhabi-pm10-forecasting/
├── data/      the pollution data, the model table every model reads, and the scripts that made them
├── models/    one notebook per model (empty for now)
└── results/   every model saves its predictions here (empty for now)
```

## The data

Source: the OpenAQ public archive (free, no account needed), Abu Dhabi government stations.

`data/openaq_daily_all_stations.csv`: one row per station, pollutant and day. 28,714 rows, 20 stations,
29 Oct 2022 to 20 May 2024.

| Column | Meaning |
|---|---|
| station_id | the station's number in OpenAQ |
| parameter | the pollutant: pm10, no2, so2, o3 or co |
| day | the day in UAE time, written like 2023-09-05 |
| readings | how many hourly readings the station has for that day |
| mean | the average of that day's readings |
| max | the highest reading of that day |
| station | the station's name |

`data/openaq_stations.csv`: one row per station with its name, latitude and longitude.

`data/openaq_download_all.py`: the script that made both files. Nobody needs to run it again.
If you do, run it from inside the `data` folder (it needs `requests` and `pandas`).

## The model table

`data/model_table.csv` is the table every model reads. 2,253 rows, no empty cells.
One row is one station on one day ("today").

| Column | Meaning |
|---|---|
| station_id, station, day | which station, and which day is "today" |
| pm10_6d_ago ... pm10_1d_ago | the PM10 daily average of the six days before today |
| pm10_today | today's PM10 daily average |
| no2_today, so2_today | today's NO2 and SO2 daily averages |
| pm10_tomorrow | the answer: tomorrow's PM10 daily average |
| split | train (31 Aug to 30 Nov 2023), validation (December 2023) or test (1 Jan to 24 Feb 2024) |

`data/make_model_table.py` made it from the daily file. Nobody needs to run it again.

## One rule

Every model reads the same table, `data/model_table.csv`. Nobody builds their own.
