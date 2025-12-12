# Simple container image for running TopicBoard with MongoDB dependency.
FROM python:3.12-slim

WORKDIR /app

# System deps (optional, kept minimal).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot source.
COPY bot ./bot

# Default environment; override at runtime.
ENV MONGO_URI="mongodb://mongo:27017" \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "bot.main"]
