FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
RUN useradd -m -u 10001 appuser && mkdir -p /app/state && chown appuser:appuser /app/state
USER appuser
ENV ISSUEWEAVER_DB_PATH=/app/state/deliveries.sqlite3
EXPOSE 8000
CMD ["uvicorn", "issueweaver.api:app", "--host", "0.0.0.0", "--port", "8000"]
