FROM python:3.11-slim

# curl — для HEALTHCHECK в docker run и диагностики;
# build-essential + libffi-dev — для компиляции cryptography wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала только requirements.txt — кэш слоя не инвалидируется при изменении кода
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Остальные исходники
COPY . .

EXPOSE 8000

# --workers 1 обязателен: SQLite не поддерживает конкурентную запись из нескольких процессов.
# Воркер живёт внутри того же процесса через lifespan asyncio.create_task.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
