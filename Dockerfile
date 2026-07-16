FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (separate layer so Docker can cache this step
# and only re-installs when requirements.txt actually changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the rest of the app
COPY . .

# SQLite file lives outside the image so data survives container restarts
# when mounted as a volume (see docker-compose.yml)
ENV DB_PATH=/app/data/nutriai.db
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
