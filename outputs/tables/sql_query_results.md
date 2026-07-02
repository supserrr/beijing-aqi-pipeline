# Task 2 — SQL query results (engine: SQLite mirror of MySQL schema; data source: real)

_Loaded 420,768 pollutant rows + matching weather rows across 12 stations._


## Q1 — latest record per station

```sql
SELECT s.station_name, p.ts, p.pm2_5, p.pm10, p.no2, p.co
FROM pollutant_readings p JOIN stations s ON s.station_id=p.station_id
WHERE p.ts = (SELECT MAX(p2.ts) FROM pollutant_readings p2
              WHERE p2.station_id=p.station_id)
ORDER BY s.station_name;
```

| station_name   | ts                  |   pm2_5 |   pm10 |   no2 |   co |
|:---------------|:--------------------|--------:|-------:|------:|-----:|
| Aotizhongxin   | 2017-02-28 23:00:00 |      19 |     31 |    79 |  600 |
| Changping      | 2017-02-28 23:00:00 |      20 |     25 |    28 |  900 |
| Dingling       | 2017-02-28 23:00:00 |      13 |     16 |     9 |  500 |
| Dongsi         | 2017-02-28 23:00:00 |      30 |     71 |    87 | 1200 |
| Guanyuan       | 2017-02-28 23:00:00 |      15 |     27 |    53 |  600 |
| Gucheng        | 2017-02-28 23:00:00 |      12 |     48 |    48 |  600 |
| Huairou        | 2017-02-28 23:00:00 |      11 |     20 |    27 |  400 |
| Nongzhanguan   | 2017-02-28 23:00:00 |      10 |     28 |    48 |  600 |
| Shunyi         | 2017-02-28 23:00:00 |      15 |     22 |    34 |  500 |
| Tiantan        | 2017-02-28 23:00:00 |      15 |     50 |    68 |  700 |
| Wanliu         | 2017-02-28 23:00:00 |       7 |     25 |    86 |  700 |
| Wanshouxigong  | 2017-02-28 23:00:00 |      13 |     19 |    38 |  600 |


## Q2 — records by date range (Aotizhongxin, 2016-01-01 00:00..06:00)

```sql
SELECT p.ts, p.pm2_5, p.pm10, w.temp, w.wspm, wd.wd_code
FROM pollutant_readings p
JOIN stations s ON s.station_id=p.station_id
JOIN weather_readings w ON w.station_id=p.station_id AND w.ts=p.ts
LEFT JOIN wind_directions wd ON wd.wind_dir_id=w.wind_dir_id
WHERE s.station_name='Aotizhongxin'
  AND p.ts BETWEEN '2016-01-01 00:00:00' AND '2016-01-01 06:00:00'
ORDER BY p.ts;
```

| ts                  |   pm2_5 |   pm10 |   temp |   wspm | wd_code   |
|:--------------------|--------:|-------:|-------:|-------:|:----------|
| 2016-01-01 00:00:00 |     209 |    268 |   -2.5 |    1.1 | NNE       |
| 2016-01-01 01:00:00 |     211 |    248 |   -3.5 |    1   | NE        |
| 2016-01-01 02:00:00 |     167 |    192 |   -4.7 |    0.8 | ENE       |
| 2016-01-01 03:00:00 |     136 |    159 |   -3.6 |    1.5 | ENE       |
| 2016-01-01 04:00:00 |     108 |    121 |   -5.1 |    1   | E         |
| 2016-01-01 05:00:00 |      93 |    108 |   -5.7 |    1.2 | ENE       |
| 2016-01-01 06:00:00 |     107 |    126 |   -6.3 |    0.7 | ENE       |


## Q3 — monthly average PM2.5 (Aotizhongxin, first 12 months)

```sql
SELECT s.station_name, strftime('%Y-%m', p.ts) AS month,
       ROUND(AVG(p.pm2_5),1) AS avg_pm25, COUNT(*) AS n_hours
FROM pollutant_readings p JOIN stations s ON s.station_id=p.station_id
WHERE s.station_name='Aotizhongxin'
GROUP BY month ORDER BY month LIMIT 12;
```

| station_name   | month   |   avg_pm25 |   n_hours |
|:---------------|:--------|-----------:|----------:|
| Aotizhongxin   | 2013-03 |      110.1 |       744 |
| Aotizhongxin   | 2013-04 |       62.8 |       720 |
| Aotizhongxin   | 2013-05 |       85.4 |       744 |
| Aotizhongxin   | 2013-06 |      106.2 |       720 |
| Aotizhongxin   | 2013-07 |       68.9 |       744 |
| Aotizhongxin   | 2013-08 |       62.3 |       744 |
| Aotizhongxin   | 2013-09 |       79.3 |       720 |
| Aotizhongxin   | 2013-10 |       95.3 |       744 |
| Aotizhongxin   | 2013-11 |       77.3 |       720 |
| Aotizhongxin   | 2013-12 |       76.7 |       744 |
| Aotizhongxin   | 2014-01 |       95.4 |       744 |
| Aotizhongxin   | 2014-02 |      149.6 |       672 |


## Q4 — top-10 most polluted hours (joins both facts + dims)

```sql
SELECT s.station_name, p.ts, p.pm2_5, w.wspm, wd.wd_code
FROM pollutant_readings p
JOIN stations s ON s.station_id=p.station_id
JOIN weather_readings w ON w.station_id=p.station_id AND w.ts=p.ts
LEFT JOIN wind_directions wd ON wd.wind_dir_id=w.wind_dir_id
ORDER BY p.pm2_5 DESC LIMIT 10;
```

| station_name   | ts                  |   pm2_5 |   wspm | wd_code   |
|:---------------|:--------------------|--------:|-------:|:----------|
| Wanshouxigong  | 2016-02-08 02:00:00 |     999 |    1.1 | SW        |
| Wanliu         | 2016-02-08 02:00:00 |     957 |    0.6 | SW        |
| Shunyi         | 2016-02-08 02:00:00 |     941 |    1.1 | NNE       |
| Aotizhongxin   | 2016-02-08 02:00:00 |     898 |    1.1 | SW        |
| Changping      | 2016-02-08 02:00:00 |     882 |    0.7 | ESE       |
| Dingling       | 2016-02-08 01:00:00 |     881 |    1.3 | NNE       |
| Wanshouxigong  | 2016-02-08 03:00:00 |     857 |    0.6 | W         |
| Nongzhanguan   | 2013-05-05 12:00:00 |     844 |    2.6 | SW        |
| Nongzhanguan   | 2017-01-28 02:00:00 |     835 |    1.4 | NE        |
| Wanshouxigong  | 2016-02-08 01:00:00 |     826 |    1.5 | WSW       |


## Q5 — mean PM2.5 by station_type x heating season

```sql
SELECT s.station_type,
       CASE WHEN CAST(strftime('%m',p.ts) AS INT) IN (11,12,1,2,3)
            THEN 'heating' ELSE 'non-heating' END AS season_kind,
       ROUND(AVG(p.pm2_5),1) AS avg_pm25
FROM pollutant_readings p JOIN stations s ON s.station_id=p.station_id
GROUP BY s.station_type, season_kind
ORDER BY s.station_type, season_kind;
```

| station_type   | season_kind   |   avg_pm25 |
|:---------------|:--------------|-----------:|
| background     | heating       |       77.4 |
| background     | non-heating   |       59.8 |
| suburban       | heating       |       86.4 |
| suburban       | non-heating   |       64.4 |
| urban          | heating       |      100.6 |
| urban          | non-heating   |       72.2 |
