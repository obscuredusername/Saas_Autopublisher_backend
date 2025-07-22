#!/bin/bash

echo "Pulling latest changes..."
git pull origin main

echo "Stopping old container..."
docker stop saas-api || true

echo "Removing old container..."
docker rm saas-api || true

echo "Building new Docker image..."
docker build -t backend-api .

echo "Running new container..."
docker run -d -p 8000:8000 --name saas-api backend-api

echo "Deployment complete!"

echo "Webhook triggered at $(date)" >> /tmp/webhook.log

echo "Latest commit: $(git log -1 --pretty=%B)"

