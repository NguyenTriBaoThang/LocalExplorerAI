FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
ARG INSTALL_E5=false
ARG INSTALL_ML=false
COPY requirements.txt requirements-e5.txt requirements-ml.txt ./
RUN pip install --no-cache-dir --timeout=120 --retries=5 -r requirements.txt \
    && if [ "$INSTALL_E5" = "true" ]; then pip install --no-cache-dir --timeout=120 --retries=5 -r requirements-e5.txt; fi
RUN if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir --timeout=120 --retries=5 -r requirements-ml.txt; fi
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--ws-max-size", "65536"]
