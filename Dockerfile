FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m app && mkdir -p /app/data && chown -R app /app/data
USER app
ENV PORT=8080 RELINK_DB=/app/data/relink.db
EXPOSE 8080
CMD ["python", "server.py"]
