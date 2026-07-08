# Task 3 — CRUD + time-series endpoint demonstration

_Data source: real. Backends: SQLite mirror of the MySQL schema + mongomock (real pymongo API). Each step calls the same repository the FastAPI routes use._


## SQL backend (MySQL schema / SQLite mirror)


### POST /sql/readings  (CREATE)

**request**

```json
{
  "station": "Aotizhongxin",
  "ts": "2017-03-01 00:00:00",
  "pm2_5": 123,
  "pm10": 180,
  "so2": 12,
  "no2": 64,
  "co": 900,
  "o3": 30
}
```

**response**

```json
{
  "station": "Aotizhongxin",
  "ts": "2017-03-01 00:00:00",
  "pm2_5": 123.0,
  "pm10": 180.0,
  "so2": 12.0,
  "no2": 64.0,
  "co": 900.0,
  "o3": 30.0
}
```

### GET /sql/readings/Aotizhongxin/item/2017-03-01 00:00:00  (READ one)

**response**

```json
{
  "station": "Aotizhongxin",
  "ts": "2017-03-01 00:00:00",
  "pm2_5": 123.0,
  "pm10": 180.0,
  "so2": 12.0,
  "no2": 64.0,
  "co": 900.0,
  "o3": 30.0
}
```

### GET /sql/readings/Aotizhongxin/latest  (READ latest — required)

**response**

```json
{
  "station": "Aotizhongxin",
  "ts": "2017-03-01 00:00:00",
  "pm2_5": 123.0,
  "pm10": 180.0,
  "so2": 12.0,
  "no2": 64.0,
  "co": 900.0,
  "o3": 30.0
}
```

### GET /sql/readings/Aotizhongxin/range  (READ date range — required)

**request**

```json
{
  "start": "2017-02-28 18:00:00",
  "end": "2017-02-28 23:00:00",
  "returned": 6
}
```

**response**

```json
[
  {
    "station": "Aotizhongxin",
    "ts": "2017-02-28 18:00:00",
    "pm2_5": 13.0,
    "pm10": 29.0,
    "so2": 5.0,
    "no2": 22.0,
    "co": 300.0,
    "o3": 109.0
  },
  {
    "station": "Aotizhongxin",
    "ts": "2017-02-28 19:00:00",
    "pm2_5": 12.0,
    "pm10": 29.0,
    "so2": 5.0,
    "no2": 35.0,
    "co": 400.0,
    "o3": 95.0
  },
  {
    "station": "Aotizhongxin",
    "ts": "2017-02-28 20:00:00",
    "pm2_5": 13.0,
    "pm10": 37.0,
    "so2": 7.0,
    "no2": 45.0,
    "co": 500.0,
    "o3": 81.0
  },
  {
    "station": "Aotizhongxin",
    "ts": "2017-02-28 21:00:00",
    "pm2_5": 16.0,
    "pm10": 37.0,
    "so2": 10.0,
    "no2": 66.0,
    "co": 700.0,
    "o3": 58.0
  },
  {
    "station": "Aotizhongxin",
    "ts": "2017-02-28 22:00:00",
    "pm2_5": 21.0,
    "pm10": 44.0,
    "so2": 12.0,
    "no2": 87.0,
    "co": 700.0,
    "o3": 35.0
  },
  {
    "station": "Aotizhongxin",
    "ts": "2017-02-28 23:00:00",
    "pm2_5": 19.0,
    "pm10": 31.0,
    "so2": 10.0,
    "no2": 79.0,
    "co": 600.0,
    "o3": 42.0
  }
]
```

### PUT /sql/readings/Aotizhongxin/item/2017-03-01 00:00:00  (UPDATE)

**request**

```json
{
  "pm2_5": 999
}
```

**response**

```json
{
  "station": "Aotizhongxin",
  "ts": "2017-03-01 00:00:00",
  "pm2_5": 999.0,
  "pm10": 180.0,
  "so2": 12.0,
  "no2": 64.0,
  "co": 900.0,
  "o3": 30.0
}
```

### DELETE /sql/readings/Aotizhongxin/item/2017-03-01 00:00:00  (DELETE)

**response**

```json
{
  "deleted": true,
  "station": "Aotizhongxin",
  "ts": "2017-03-01 00:00:00"
}
```

### GET deleted record -> 404

**response**

```json
{
  "status": 404,
  "detail": "no reading for Aotizhongxin @ 2017-03-01 00:00:00"
}
```

## MongoDB backend (pymongo / mongomock)


### POST /mongo/readings  (CREATE)

**request**

```json
{
  "station": "Aotizhongxin",
  "timestamp": "2017-03-01 00:00:00",
  "station_type": "urban",
  "location": {
    "lat": 39.982,
    "lon": 116.397
  },
  "pollutants": {
    "pm2_5": 123,
    "pm10": 180,
    "co": 900
  },
  "weather": {
    "temp": 2.0,
    "wind_dir": "NW",
    "wspm": 3.1
  }
}
```

**response**

```json
{
  "station": "Aotizhongxin",
  "timestamp": "2017-03-01 00:00:00",
  "station_type": "urban",
  "location": {
    "lat": 39.982,
    "lon": 116.397
  },
  "pollutants": {
    "pm2_5": 123,
    "pm10": 180,
    "co": 900
  },
  "weather": {
    "temp": 2.0,
    "wind_dir": "NW",
    "wspm": 3.1
  }
}
```

### GET /mongo/readings/Aotizhongxin/item/2017-03-01 00:00:00  (READ one)

**response**

```json
{
  "station": "Aotizhongxin",
  "timestamp": "2017-03-01 00:00:00",
  "station_type": "urban",
  "location": {
    "lat": 39.982,
    "lon": 116.397
  },
  "pollutants": {
    "pm2_5": 123,
    "pm10": 180,
    "co": 900
  },
  "weather": {
    "temp": 2.0,
    "wind_dir": "NW",
    "wspm": 3.1
  }
}
```

### GET /mongo/readings/Aotizhongxin/latest  (READ latest — required)

**response**

```json
{
  "station": "Aotizhongxin",
  "timestamp": "2017-03-01 00:00:00",
  "station_type": "urban",
  "location": {
    "lat": 39.982,
    "lon": 116.397
  },
  "pollutants": {
    "pm2_5": 123,
    "pm10": 180,
    "co": 900
  },
  "weather": {
    "temp": 2.0,
    "wind_dir": "NW",
    "wspm": 3.1
  }
}
```

### GET /mongo/readings/Aotizhongxin/range  (READ date range — required)

**request**

```json
{
  "start": "2017-02-28T18:00",
  "end": "2017-02-28T23:00",
  "returned": 6
}
```

**response**

```json
[
  {
    "station": "Aotizhongxin",
    "station_type": "urban",
    "location": {
      "lat": 39.982,
      "lon": 116.397
    },
    "timestamp": "2017-02-28 18:00:00",
    "pollutants": {
      "pm2_5": 13.0,
      "pm10": 29.0,
      "so2": 5.0,
      "no2": 22.0,
      "co": 300.0,
      "o3": 109.0
    },
    "weather": {
      "temp": 13.4,
      "wind_dir": "WNW",
      "wspm": 1.4
    }
  },
  {
    "station": "Aotizhongxin",
    "station_type": "urban",
    "location": {
      "lat": 39.982,
      "lon": 116.397
    },
    "timestamp": "2017-02-28 19:00:00",
    "pollutants": {
      "pm2_5": 12.0,
      "pm10": 29.0,
      "so2": 5.0,
      "no2": 35.0,
      "co": 400.0,
      "o3": 95.0
    },
    "weather": {
      "temp": 12.5,
      "wind_dir": "NW",
      "wspm": 2.4
    }
  },
  {
    "station": "Aotizhongxin",
    "station_type": "urban",
    "location": {
      "lat": 39.982,
      "lon": 116.397
    },
    "timestamp": "2017-02-28 20:00:00",
    "pollutants": {
      "pm2_5": 13.0,
      "pm10": 37.0,
      "so2": 7.0,
      "no2": 45.0,
      "co": 500.0,
      "o3": 81.0
    },
    "weather": {
      "temp": 11.6,
      "wind_dir": "WNW",
      "wspm": 0.9
    }
  },
  "..."
]
```

### PUT /mongo/readings/Aotizhongxin/item/2017-03-01 00:00:00  (UPDATE)

**request**

```json
{
  "pollutants.pm2_5": 999
}
```

**response**

```json
{
  "station": "Aotizhongxin",
  "timestamp": "2017-03-01 00:00:00",
  "station_type": "urban",
  "location": {
    "lat": 39.982,
    "lon": 116.397
  },
  "pollutants": {
    "pm2_5": 999,
    "pm10": 180,
    "co": 900
  },
  "weather": {
    "temp": 2.0,
    "wind_dir": "NW",
    "wspm": 3.1
  }
}
```

### DELETE /mongo/readings/Aotizhongxin/item/2017-03-01 00:00:00  (DELETE)

**response**

```json
{
  "deleted": true,
  "station": "Aotizhongxin",
  "ts": "2017-03-01 00:00:00"
}
```

### GET deleted record -> 404

**response**

```json
{
  "status": 404,
  "detail": "no document for Aotizhongxin @ 2017-03-01 00:00:00"
}
```