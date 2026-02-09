FROM python:3.11-slim
WORKDIR /app
COPY config/ ./config/
COPY src/ ./src/
COPY api/ ./api/
COPY pyproject.toml .
RUN pip install --no-cache-dir . && pip install --no-cache-dir -r api/requirements.txt
EXPOSE 8000
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
