# API container (Phase 2). Mount or bake `data/` for production.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/gold_signal ./backend/gold_signal
COPY data ./data

ENV PYTHONPATH=/app/backend
ENV GOLD_DATA_DIR=/app/data

EXPOSE 8000
CMD ["uvicorn", "gold_signal.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
