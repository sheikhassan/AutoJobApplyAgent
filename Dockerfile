FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY entrypoint.sh ./entrypoint.sh
COPY tests ./tests
COPY README.md README_V0.8.md MODEL_API.md ./
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh","-c","if [ \"${SERVICE_ROLE:-api}\" = \"scheduler\" ]; then exec python -m app.scheduler; else exec uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
