#!/bin/bash

echo "📥 Pulling latest code..."
cd /var/www/Saas_AutoPublisher/backend || exit
git pull origin main

echo "🐳 Rebuilding Docker image..."
docker build -t saas_backend .

echo "🔁 Restarting container..."
docker stop saas_backend_container || true
docker rm saas_backend_container || true
docker run -d --name saas_backend_container -p 8000:8000 saas_backend

echo "✅ Deployment complete"
