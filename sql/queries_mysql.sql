-- ===========================================================================
-- Task 2 — demonstration SQL queries (MySQL 8). Results captured in
-- outputs/tables/sql_query_results.md (executed via the SQLite mirror in
-- db/build_databases.py; identical ANSI-SQL semantics).
-- ===========================================================================

-- Q1. LATEST reading per station (required "latest record" query).
--     Uses a correlated subquery to pick each station's max timestamp.
SELECT s.station_name, p.ts, p.pm2_5, p.pm10, p.no2, p.co
FROM   pollutant_readings p
JOIN   stations s ON s.station_id = p.station_id
WHERE  p.ts = (SELECT MAX(p2.ts)
               FROM pollutant_readings p2
               WHERE p2.station_id = p.station_id)
ORDER  BY s.station_name;

-- Q2. Records by DATE RANGE for one station (required "date range" query).
SELECT p.ts, p.pm2_5, p.pm10, w.temp, w.wspm, wd.wd_code
FROM   pollutant_readings p
JOIN   stations s         ON s.station_id = p.station_id
JOIN   weather_readings w ON w.station_id = p.station_id AND w.ts = p.ts
LEFT JOIN wind_directions wd ON wd.wind_dir_id = w.wind_dir_id
WHERE  s.station_name = 'Aotizhongxin'
  AND  p.ts BETWEEN '2016-01-01 00:00:00' AND '2016-01-01 06:00:00'
ORDER  BY p.ts;

-- Q3. Monthly average PM2.5 by station (aggregation; shows winter peak).
SELECT s.station_name,
       DATE_FORMAT(p.ts, '%Y-%m')          AS month,
       ROUND(AVG(p.pm2_5), 1)              AS avg_pm25,
       COUNT(*)                            AS n_hours
FROM   pollutant_readings p
JOIN   stations s ON s.station_id = p.station_id
GROUP  BY s.station_name, month
ORDER  BY s.station_name, month
LIMIT  12;

-- Q4. Top-10 most polluted hours overall, with station + wind context
--     (multi-table join across both facts + both dimensions).
SELECT s.station_name, p.ts, p.pm2_5, w.wspm, wd.wd_code
FROM   pollutant_readings p
JOIN   stations s         ON s.station_id = p.station_id
JOIN   weather_readings w ON w.station_id = p.station_id AND w.ts = p.ts
LEFT JOIN wind_directions wd ON wd.wind_dir_id = w.wind_dir_id
ORDER  BY p.pm2_5 DESC
LIMIT  10;

-- Q5. Mean PM2.5 by station_type and heating season (dimension rollup).
SELECT s.station_type,
       CASE WHEN MONTH(p.ts) IN (11,12,1,2,3) THEN 'heating'
            ELSE 'non-heating' END          AS season_kind,
       ROUND(AVG(p.pm2_5),1)               AS avg_pm25
FROM   pollutant_readings p
JOIN   stations s ON s.station_id = p.station_id
GROUP  BY s.station_type, season_kind
ORDER  BY s.station_type, season_kind;
