Auto Redliner (India) — AWS Bedrock + FastAPI + S3

Overview
- Upload a PDF or DOCX contract and get automatic issue highlights and redline suggestions tailored for Indian contract context.
- Backend: Python FastAPI on AWS Lambda + API Gateway, using Amazon Bedrock (Nova Lite) for analysis.
- Frontend: Simple Vue (CDN) + PDF.js static site on S3 with client-side highlighting.
- Storage: S3 presigned uploads keep API Gateway payloads small and costs low.

Architecture
- `S3 (uploads)` for files via presigned PUT.
- `Lambda (FastAPI + Mangum)` processes the S3 file, parses text, calls Bedrock, returns issues and highlight snippets.
- `API Gateway (HTTP API)` exposes `/upload-url` and `/analyze` endpoints.
- `S3 (static site)` hosts the Vue UI + PDF.js.

Costs
- Bedrock: pay-per-token for Nova Lite (keep file/page limits). Disable streaming. Temperature low to reduce tokens.
- S3: minimal storage and data transfer for demo.
- Lambda + API Gateway: free-tier friendly for hackathons.

Quick Start
1) Deploy backend with CloudFormation and deploy.sh (creates/upload code zip and stack).
2) Update `frontend/config.js` with the API base URL output from the stack.
3) Upload frontend to S3 static site bucket via `upload_frontend.sh`.
4) Open the StaticSiteURL and test with a small NDA PDF.

Repo Layout
- `backend/` FastAPI app, Bedrock client, parsing + analysis.
- `frontend/` Vue (CDN) app with PDF.js highlighting.
- `infra/` CloudFormation + deploy scripts.

Disclaimers
- This tool is for educational/demo use only and is not legal advice.
- The analyzer enforces conservative page and size limits for cost control.

