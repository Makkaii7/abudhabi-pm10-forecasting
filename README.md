# Abu Dhabi PM10 forecasting

COSC 621 course project. We predict tomorrow's PM10 (dust and other particles in the air) at the
Abu Dhabi air quality stations. One shared repository, so that everyone works on the same data file.

## The map

```
abudhabi-pm10-forecasting/
├── data/      the pollution data everyone uses (already downloaded) and the script that downloaded it
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

## One rule

Everyone reads the same file, `data/openaq_daily_all_stations.csv`. Nobody downloads their own copy.
