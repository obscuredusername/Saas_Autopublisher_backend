# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Create directories for temporary files
RUN mkdir -p /app/scraped_data /app/news /app/google_news

# Give permissions to create files (more secure)
RUN chmod -R 755 /app/scraped_data /app/news /app/google_news

# Add default command
CMD ["python", "main.py"] 