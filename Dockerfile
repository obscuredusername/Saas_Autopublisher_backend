# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Environment config
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system packages
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . .

# Create folders & set permissions
RUN mkdir -p /app/scraped_data /app/news /app/google_news \
 && chmod -R 755 /app/scraped_data /app/news /app/google_news

# Expose port for FastAPI
EXPOSE 8000

# 🚀 Start FastAPI app with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
