Backend (FastAPI on Lambda)

Endpoints
- GET /health — basic config and limits
- POST /upload-url — body: { ext: "pdf"|"docx" } → presigned S3 PUT URL
- POST /analyze — body: { s3_key } → issues JSON

Env Vars
- AWS_REGION: default us-east-1
- BEDROCK_MODEL_ID: default amazon.nova-lite-v1:0
- UPLOADS_BUCKET: S3 bucket for uploads
- ALLOWED_ORIGINS: CORS origins, comma-separated (default *)
- MAX_PAGES: default 20
- MAX_FILE_MB: default 5
 - USE_BEDROCK_AGENT: '0' or '1' to enable Bedrock Agent path
 - BEDROCK_AGENT_ID: Agent ID when using Bedrock Agent
 - BEDROCK_AGENT_ALIAS_ID: Agent Alias ID when using Bedrock Agent

Local Dev
1) python -m venv .venv && source .venv/bin/activate
2) pip install -r requirements.txt
3) export UPLOADS_BUCKET=...; export AWS_REGION=us-east-1; export BEDROCK_MODEL_ID=amazon.nova-lite-v1:0
4) uvicorn backend.app:app --reload --port 8000

Note: Local run needs AWS credentials configured (`aws configure`) to use Bedrock and S3.

Using Bedrock Agents
- Create a Bedrock Agent (Nova Lite) with an action group that exposes functions:
  - `policy_library(category: string, jurisdiction: "India")`
  - `severity_rules(clause: string, category: string)`
  - `redline_templates(clause: string, category: string)`
- Set envs: `USE_BEDROCK_AGENT=1`, `BEDROCK_AGENT_ID=...`, `BEDROCK_AGENT_ALIAS_ID=...`.
- The backend will invoke the agent and parse STRICT JSON output into the existing schema.
