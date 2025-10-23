#!/usr/bin/env bash
set -euo pipefail

# Usage: ./infra/deploy.sh <stack-name> [region]

STACK_NAME=${1:-redliner-stack}
REGION=${2:-us-east-1}
PROJECT_NAME=${PROJECT_NAME:-redliner}

ARTIFACTS_BUCKET=${ARTIFACTS_BUCKET:-${PROJECT_NAME}-artifacts-$(aws sts get-caller-identity --query Account --output text)-${REGION}}

echo "Region: $REGION"
echo "Stack:  $STACK_NAME"
echo "Artifacts bucket: $ARTIFACTS_BUCKET"

if ! aws s3 ls "s3://${ARTIFACTS_BUCKET}" --region "$REGION" >/dev/null 2>&1; then
  echo "Creating artifacts bucket..."
  aws s3 mb "s3://${ARTIFACTS_BUCKET}" --region "$REGION"
fi

echo "Building Lambda package (pure-Python deps)..."
rm -rf build
mkdir -p build
python3 -m venv .pack-venv
source .pack-venv/bin/activate
pip install -U pip
pip install -r backend/requirements.txt -t build/

# Copy app code
rsync -a backend/ build/backend/

pushd build >/dev/null
zip -r function.zip .
popd >/dev/null

S3_KEY=${STACK_NAME}/function-$(date +%s).zip
aws s3 cp build/function.zip s3://${ARTIFACTS_BUCKET}/${S3_KEY} --region "$REGION"

echo "Deploying CloudFormation stack..."
aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file infra/template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName=${PROJECT_NAME} \
    BedrockModelId=${BEDROCK_MODEL_ID:-amazon.nova-lite-v1:0} \
    AllowedOrigins='*' \
    CodeS3Bucket=${ARTIFACTS_BUCKET} \
    CodeS3Key=${S3_KEY} \
  --region "$REGION"

echo "Outputs:"
aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query 'Stacks[0].Outputs[*].{Key:OutputKey,Value:OutputValue}' --output table

echo "Done. Update frontend/config.js with ApiBaseUrl output."

