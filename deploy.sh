#!/usr/bin/env bash
# ==============================================================================
# BorderWise AI — 1-Command Google Cloud Run Deployment Script
# 100% Google Cloud Platform Native ($0 Always-Free Tier)
# ==============================================================================

set -e

PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
REGION="asia-south1"

if [ -z "$PROJECT_ID" ]; then
  echo "⚠️ Google Cloud Project ID not set. Please run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

echo "🚀 Deploying BorderWise AI to Google Cloud Run in project: $PROJECT_ID ($REGION)..."

# Build and deploy container directly using Cloud Run source deploy
gcloud run deploy borderwise-ai \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "GEMINI_MODEL=gemini-3.8"

SERVICE_URL=$(gcloud run services describe borderwise-ai --region "$REGION" --format 'value(status.url)')

echo ""
echo "=============================================================================="
echo "✅ BorderWise AI successfully deployed to Google Cloud Run!"
echo "🌐 Live Web Companion URL for Judges: $SERVICE_URL"
echo "📡 API Documentation: $SERVICE_URL/docs"
echo "=============================================================================="
