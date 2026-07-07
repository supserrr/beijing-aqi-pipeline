# Task 2: MongoDB Collection Design

## Database / collection
`beijing_air.air_quality`: one document per (station, hour).

The relational model splits pollutants, weather, station, and wind into four
normalized tables. The document model does the opposite: it denormalizes one hour
of a station into a single self-contained document. A read for "the state of a
station at time *t*" is then a single-document lookup with no joins, which is the
access pattern that dominates a time-series API.

## Document structure (embedded sub-documents)

```json
{
  "station": "Aotizhongxin",
  "station_type": "urban",
  "location": { "lat": 39.982, "lon": 116.397 },
  "timestamp": ISODate("2017-02-28T23:00:00Z"),
  "time": { "year": 2017, "month": 2, "day": 28, "hour": 23,
            "is_heating_season": 1 },
  "pollutants": { "pm2_5": 19.0, "pm10": 31.0, "so2": 10.0,
                  "no2": 79.0, "co": 600.0, "o3": 42.0 },
  "weather": { "temp": 8.6, "pres": 1014.1, "dewp": -15.9,
               "rain": 0.0, "wind_dir": "NNE", "wspm": 1.3 }
}
```

Two real sample documents are exported in `sample_documents.json`.

## Why this shape
- Pollutants and weather are a 1:1 fact for a given (station, hour) and are always
  read together, so they are embedded as sub-documents rather than referenced. The
  common read needs no `$lookup`.
- Station metadata (`station_type`, `location`) is denormalized so a document is
  interpretable on its own, and station-level filtering or grouping needs no join.
- `timestamp` is stored as a native `ISODate` rather than a string, so range
  queries and sorting use the BSON date type and the index correctly.
- A redundant `time` sub-document (year/month/hour/heating flag) trades a little
  storage for cheap calendar filtering and grouping without `$expr` or date
  operators.

## Indexes
```js
db.air_quality.createIndex({ station: 1, timestamp: 1 })   // primary access path
db.air_quality.createIndex({ timestamp: 1 })               // global range scans
```
The compound `{station, timestamp}` index serves the two required query endpoints
directly from the index: *latest record*
(`find({station}).sort({timestamp:-1}).limit(1)`) and *records by date range*
(`find({station, timestamp:{$gte,$lte}})`).

## Relational vs. document trade-off
| Aspect | MySQL (normalized) | MongoDB (embedded) |
|---|---|---|
| Best at | integrity, ad-hoc joins, rollups across dimensions | single-key reads of a full hourly record, flexible/optional fields |
| One hour of a station | row in `pollutant_readings` + row in `weather_readings` | one document |
| Add a new pollutant | `ALTER TABLE` | just add a field (no migration) |
| "Latest / date-range for a station" | indexed join | single indexed collection scan |

Both are implemented and queried in `db/build_databases.py`; results are in
`outputs/tables/sql_query_results.md` and `outputs/tables/mongo_query_results.md`.
