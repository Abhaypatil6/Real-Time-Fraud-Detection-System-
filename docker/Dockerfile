FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create models dir
RUN mkdir -p models

# Train model on container start (remove if pre-built image preferred)
RUN python main.py train

EXPOSE 8000

CMD ["python", "main.py", "serve"]
