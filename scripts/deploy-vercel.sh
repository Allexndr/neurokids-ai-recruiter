#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -z "${VERCEL_TOKEN:-}" ]]; then
  echo "Set VERCEL_TOKEN"
  exit 1
fi

SCOPE="${VERCEL_SCOPE:-murdasoft-9183s-projects}"
echo "==> Deploying hr-recruter-bot to Vercel production (scope=$SCOPE)..."
DEPLOY_URL=$(vercel deploy --prod --yes --scope "$SCOPE" --token "$VERCEL_TOKEN" 2>&1 | tee /dev/stderr | grep -Eo 'https://[a-zA-Z0-9.-]+\.vercel\.app' | tail -1)

if [[ -z "$DEPLOY_URL" ]]; then
  echo "Could not detect deploy URL"
  exit 1
fi

echo "==> URL: $DEPLOY_URL"
echo "==> Register Telegram webhook..."
curl -fsS "${DEPLOY_URL}/setup" | head -c 2000
echo
echo "Done. Set WEBHOOK_BASE_URL=$DEPLOY_URL in Vercel env if not set."
