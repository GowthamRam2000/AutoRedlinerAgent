#!/usr/bin/env bash
set -euo pipefail

# Usage: STACK_NAME=<stack> REGION=<region> ./upload_frontend.sh

STACK_NAME=${STACK_NAME:-redliner-stack}
REGION=${REGION:-us-east-1}

SITE_BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='StaticSiteURL'].OutputValue" --output text)

if [[ -z "$SITE_BUCKET" ]]; then
  echo "Could not determine StaticSiteURL from stack outputs."
  exit 1
fi

# Extract bucket name from website URL
BUCKET=$(echo "$SITE_BUCKET" | sed -E 's#http://([^\.]+)\.s3-website-[^/]+\.amazonaws\.com.*#\1#')

echo "Syncing frontend/ to s3://$BUCKET ..."
aws s3 sync frontend/ s3://$BUCKET --delete --acl public-read --region "$REGION"

echo "Done. Visit: $SITE_BUCKET"

