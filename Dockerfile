FROM python:3.12.9-slim-bookworm
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    KORDEN_DATA_DIR=/data
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt && python -m pip check
COPY korden/ ./korden/
COPY static/ ./static/
COPY samples/ ./samples/
COPY run.py benchmark.py benchmark_suite.py backup.py ./
RUN mkdir -p /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" || exit 1
CMD ["uvicorn", "korden.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
