# Backend container for Auto Redliner (India)
# - Exposes FastAPI on port 8000
# - Uses host-provided AWS credentials via volume or env

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /app/backend/requirements.txt

# Copy app code
COPY backend/ /app/backend/

EXPOSE 8000

# Env vars: AWS_REGION, BEDROCK_MODEL_ID, UPLOADS_BUCKET, ALLOWED_ORIGINS, MAX_PAGES, MAX_FILE_MB
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]

