FROM python:3.12-slim

WORKDIR /app
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt \
    --index-url https://pypi.org/simple \
    --extra-index-url https://download.pytorch.org/whl/cpu

COPY server.py .
COPY src/ src/
COPY scripts/ scripts/

RUN python scripts/prepare_base.py && python scripts/fetch_weights.py

ENV MGTE_MODEL_DIR=/app/model MGTE_BASE_DIR=/app/base GUARD_CONCURRENCY=1
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
