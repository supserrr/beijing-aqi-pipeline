# Image used by the `loader` and `api` services in docker-compose.yml
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# server-side dependencies (numpy/pandas for the loader; fastapi/uvicorn for the
# API; pymysql/pymongo as the real DB drivers)
RUN pip install --no-cache-dir \
        numpy pandas \
        "pymysql>=1.1" "pymongo>=4.6" \
        "fastapi>=0.110" "uvicorn>=0.29"

COPY . .
