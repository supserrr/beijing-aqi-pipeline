# Task 1B: Analytical Questions (source: real)

## Q1 trend seasonality

PM2.5 has no strong monotonic long-term trend but a pronounced annual cycle: Winter is the most polluted season (mean 96 ug/m3) and Summer the cleanest (65 ug/m3), a 1.5x swing driven by winter coal heating and stagnant air.

## Q2 diurnal weekly

PM2.5 follows a clear daily cycle: it peaks around 22:00 and bottoms out near 07:00. Weekday and weekend curves are close, with weekday levels a little higher at commute hours. That fits traffic-linked accumulation on top of the dominant meteorological cycle.

## Q3 exogenous correlation

External variables co-move with PM2.5. The strongest positive driver is PM10 (r=0.88); co-pollutants from shared combustion sources track PM2.5 closely. Among the meteorological variables, higher wind speed (WSPM, r=-0.27) is the strongest negative driver, consistent with dispersion and ventilation of particulates. This justifies using weather and co-pollutants as model features.

## Q4 lag effects

Strong lag effects confirm forecastability. Hourly persistence is high (corr PM2.5 with lag-1h = 0.97); the daily echo at lag-24h = 0.40 and the weekly term at lag-168h = 0.02 remain positive. The ACF decays gradually with bumps near 24h multiples, which justifies lag-1, lag-24, and lag-168 as model features.

## Q5 moving averages

Moving averages expose multi-day pollution episodes hidden in hourly noise: the 24h MA removes the daily cycle, and the 168h MA traces the synoptic build-up and clearance of haze events. Smoothing cuts variability from std 82 (hourly) to 70 (24h MA). The deviation of current PM2.5 from its weekly MA is a useful episode-onset signal and a strong model feature.

## Q6 spatial

Pollution levels also vary by station. Dongsi is the most polluted station (mean 86) and Dingling the cleanest (67), a 19 ug/m3 urban-versus-background gap that supports keeping `station` as a first-class dimension in the database schema.

