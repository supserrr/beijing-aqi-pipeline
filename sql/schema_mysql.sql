-- ===========================================================================
-- Beijing Multi-Site Air-Quality — Relational schema (MySQL 8)
-- Task 2: normalized (3NF) design, 4 tables
--   Dimensions : stations, wind_directions
--   Facts      : pollutant_readings, weather_readings
-- The two fact tables share the (station_id, ts) grain and reference the
-- station + wind-direction dimensions, giving a clean star schema.
-- Note: MySQL identifiers cannot contain '.', so PM2.5 -> pm2_5 etc.
-- ===========================================================================
DROP DATABASE IF EXISTS beijing_air;
CREATE DATABASE beijing_air CHARACTER SET utf8mb4;
USE beijing_air;

-- --------------------------------------------------------------------------
-- Dimension: monitoring stations
-- --------------------------------------------------------------------------
CREATE TABLE stations (
    station_id    INT AUTO_INCREMENT PRIMARY KEY,
    station_name  VARCHAR(64)  NOT NULL UNIQUE,
    station_type  ENUM('urban','suburban','background') NOT NULL,
    latitude      DECIMAL(8,5),
    longitude     DECIMAL(8,5)
) ENGINE=InnoDB;

-- --------------------------------------------------------------------------
-- Lookup: wind direction codes (normalizes the categorical `wd` column)
-- --------------------------------------------------------------------------
CREATE TABLE wind_directions (
    wind_dir_id   INT AUTO_INCREMENT PRIMARY KEY,
    wd_code       VARCHAR(4)  NOT NULL UNIQUE,    -- e.g. 'NW', 'NNW'
    wd_label      VARCHAR(32)                     -- e.g. 'Northwest'
) ENGINE=InnoDB;

-- --------------------------------------------------------------------------
-- Fact: pollutant concentrations (one row per station per hour)
-- --------------------------------------------------------------------------
CREATE TABLE pollutant_readings (
    reading_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
    station_id    INT       NOT NULL,
    ts            DATETIME  NOT NULL,
    pm2_5         FLOAT,
    pm10          FLOAT,
    so2           FLOAT,
    no2           FLOAT,
    co            FLOAT,
    o3            FLOAT,
    CONSTRAINT fk_poll_station FOREIGN KEY (station_id)
        REFERENCES stations(station_id),
    CONSTRAINT uq_poll UNIQUE (station_id, ts)
) ENGINE=InnoDB;
CREATE INDEX ix_poll_ts          ON pollutant_readings (ts);
CREATE INDEX ix_poll_station_ts  ON pollutant_readings (station_id, ts);

-- --------------------------------------------------------------------------
-- Fact: meteorology (one row per station per hour)
-- --------------------------------------------------------------------------
CREATE TABLE weather_readings (
    reading_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
    station_id    INT       NOT NULL,
    ts            DATETIME  NOT NULL,
    temp          FLOAT,                 -- degC
    pres          FLOAT,                 -- hPa
    dewp          FLOAT,                 -- degC
    rain          FLOAT,                 -- mm
    wspm          FLOAT,                 -- m/s
    wind_dir_id   INT,
    CONSTRAINT fk_wx_station FOREIGN KEY (station_id)
        REFERENCES stations(station_id),
    CONSTRAINT fk_wx_wind FOREIGN KEY (wind_dir_id)
        REFERENCES wind_directions(wind_dir_id),
    CONSTRAINT uq_wx UNIQUE (station_id, ts)
) ENGINE=InnoDB;
CREATE INDEX ix_wx_ts          ON weather_readings (ts);
CREATE INDEX ix_wx_station_ts  ON weather_readings (station_id, ts);
