# Task 2 — MongoDB query results (engine: mongomock, real pymongo API)

_In-memory demo collection `beijing_air.air_quality` with 35,436 documents (recent 4-month window)._


## M1 — latest record for a station

```js
db.air_quality.find({station:'Aotizhongxin'}).sort({timestamp:-1}).limit(1)
```

```json
[
  {
    "station": "Aotizhongxin",
    "timestamp": "2017-02-28 23:00:00",
    "pollutants": {
      "pm2_5": 19.0
    },
    "weather": {
      "wspm": 1.3
    }
  }
]
```

## M2 — records by date range (2017-02-01 00:00..06:00)

```js
db.air_quality.find({station:'Aotizhongxin',timestamp:{$gte:ISODate('2017-02-01'),$lte:ISODate('2017-02-01T06:00')}}).sort({timestamp:1})
```

```json
[
  {
    "timestamp": "2017-02-01 00:00:00",
    "pollutants": {
      "pm2_5": 5.0
    },
    "weather": {
      "temp": 0.3,
      "wind_dir": "NNE"
    }
  },
  {
    "timestamp": "2017-02-01 01:00:00",
    "pollutants": {
      "pm2_5": 5.0
    },
    "weather": {
      "temp": -0.4,
      "wind_dir": "NNE"
    }
  },
  {
    "timestamp": "2017-02-01 02:00:00",
    "pollutants": {
      "pm2_5": 7.0
    },
    "weather": {
      "temp": -1.9,
      "wind_dir": "N"
    }
  },
  {
    "timestamp": "2017-02-01 03:00:00",
    "pollutants": {
      "pm2_5": 6.0
    },
    "weather": {
      "temp": -1.9,
      "wind_dir": "NE"
    }
  },
  {
    "timestamp": "2017-02-01 04:00:00",
    "pollutants": {
      "pm2_5": 8.0
    },
    "weather": {
      "temp": -3.3,
      "wind_dir": "ENE"
    }
  },
  {
    "timestamp": "2017-02-01 05:00:00",
    "pollutants": {
      "pm2_5": 8.0
    },
    "weather": {
      "temp": -3.9,
      "wind_dir": "NE"
    }
  },
  {
    "timestamp": "2017-02-01 06:00:00",
    "pollutants": {
      "pm2_5": 6.0
    },
    "weather": {
      "temp": -4.0,
      "wind_dir": "NE"
    }
  }
]
```

## M3 — aggregation: average PM2.5 by station

```js
db.air_quality.aggregate([{$group:{_id:'$station',avg_pm25:{$avg:'$pollutants.pm2_5'},hours:{$sum:1}}},{$sort:{avg_pm25:-1}}])
```

```json
[
  {
    "station": "Wanshouxigong",
    "avg_pm25": 117.1,
    "hours": 2953
  },
  {
    "station": "Dongsi",
    "avg_pm25": 113.8,
    "hours": 2953
  },
  {
    "station": "Nongzhanguan",
    "avg_pm25": 111.2,
    "hours": 2953
  },
  {
    "station": "Gucheng",
    "avg_pm25": 108.6,
    "hours": 2953
  },
  {
    "station": "Guanyuan",
    "avg_pm25": 108.4,
    "hours": 2953
  },
  {
    "station": "Tiantan",
    "avg_pm25": 108.0,
    "hours": 2953
  },
  {
    "station": "Aotizhongxin",
    "avg_pm25": 103.7,
    "hours": 2953
  },
  {
    "station": "Wanliu",
    "avg_pm25": 101.6,
    "hours": 2953
  },
  {
    "station": "Shunyi",
    "avg_pm25": 99.2,
    "hours": 2953
  },
  {
    "station": "Changping",
    "avg_pm25": 87.4,
    "hours": 2953
  },
  {
    "station": "Huairou",
    "avg_pm25": 79.2,
    "hours": 2953
  },
  {
    "station": "Dingling",
    "avg_pm25": 75.6,
    "hours": 2953
  }
]
```

## M4 — hazardous hours (PM2.5 > 250) by station type

```js
db.air_quality.aggregate([{$match:{'pollutants.pm2_5':{$gt:250}}},{$group:{_id:'$station_type',hazardous_hours:{$sum:1}}},{$sort:{hazardous_hours:-1}}])
```

```json
[
  {
    "station_type": "urban",
    "hazardous_hours": 2709
  },
  {
    "station_type": "suburban",
    "hazardous_hours": 603
  },
  {
    "station_type": "background",
    "hazardous_hours": 122
  }
]
```