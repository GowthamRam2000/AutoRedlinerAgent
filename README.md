Auto Redliner (India) — Bedrock + FastAPI + S3

This project analyzes PDF/DOCX contracts and returns issues, page hints, and suggested redlines tailored to the Indian contract context. It uses Amazon Bedrock (Nova Lite) for analysis, FastAPI for the backend (Lambda friendly), and a simple Vue + PDF.js frontend for highlighting.

What’s here
- Backend: FastAPI API with S3 presigned uploads and Bedrock calls (Lambda compatible)
- Frontend: Vue (CDN) + PDF.js static site for preview and highlights
- Infra: CloudFormation template and a deploy script
- Docker: Backend and frontend Dockerfiles and a `docker-compose.yml` for local

Prerequisites
- AWS account with Bedrock access and an S3 bucket for uploads
- AWS CLI v2 configured (`aws configure`) and permission to create resources
- Python 3.12+ (for local backend), Docker (optional), zip and rsync (for deploy script)

Environment Variables (backend)
- `AWS_REGION` (default: `us-east-1`)
- `BEDROCK_MODEL_ID` (default: `amazon.nova-lite-v1:0`)
- `UPLOADS_BUCKET` (required): S3 bucket name for uploads
- `ALLOWED_ORIGINS` (default: `*`)
- `MAX_PAGES` (default: `20`)
- `MAX_FILE_MB` (default: `5`)
- `USE_BEDROCK_AGENT` (optional, `0`/`1`)
- `BEDROCK_AGENT_ID`, `BEDROCK_AGENT_ALIAS_ID` (when using Bedrock Agent)

Run Locally (Python)
1) Create/choose an S3 bucket for uploads (must exist). Example: `redliner-uploads-<account>-<region>`
2) Create venv and install deps:
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -r backend/requirements.txt`
3) Export required env vars:
   - `export AWS_REGION=us-east-1`
   - `export UPLOADS_BUCKET=<your-uploads-bucket>`
   - `export BEDROCK_MODEL_ID=amazon.nova-lite-v1:0`
4) Start API:
   - `uvicorn backend.app:app --reload --port 8000`
5) Configure frontend to talk to the API:
   - Edit `frontend/config.js` and set `API_BASE_URL` to `http://localhost:8000`
   - Open `frontend/index.html` in your browser (no build step required)

Run Locally (Docker Compose)
1) Ensure AWS creds are available (Compose mounts `~/.aws` into backend container)
2) Ensure the uploads bucket exists and export it for Compose:
   - `export UPLOADS_BUCKET=<your-uploads-bucket>`
3) Start both services:
   - `docker-compose up --build`
   - Backend: `http://localhost:8000` (FastAPI)
   - Frontend: `http://localhost:8080` (nginx serving `frontend/`)

Deploy to AWS (CloudFormation)
1) Build and deploy the backend stack (packages code and uploads to S3):
   - `./infra/deploy.sh <stack-name> <region>` (defaults: `redliner-stack us-east-1`)
2) Copy the API URL from the stack outputs and set it in `frontend/config.js` as `API_BASE_URL`.
3) Upload the frontend to the static website bucket:
   - `./upload_frontend.sh` (expects `STACK_NAME`/`REGION` envs or defaults)
4) Open the `StaticSiteURL` output to use the app.

Using Bedrock Agents (optional)
- Create a Bedrock Agent that exposes functions:
  - `policy_library(category: string, jurisdiction: "India")`
  - `severity_rules(clause: string, category: string)`
  - `redline_templates(clause: string, category: string)`
- Set envs on the backend: `USE_BEDROCK_AGENT=1`, `BEDROCK_AGENT_ID`, `BEDROCK_AGENT_ALIAS_ID`.

Security and Git Hygiene
- Secrets are never committed. The repo uses a hardened `.gitignore` to exclude common secret and artifact patterns.
- Account-specific files are excluded by default:
  - `backend-service.json` (contains ARNs)
  - `original.json` (your private local JSON). Use the provided `original.example.json` as a template if needed.
- Screenshot and build artifacts are excluded.

GitHub
- Initialize and push:
  - `git init -b main && git add . && git commit -m "initial"`
  - `git remote add origin <git-url>`
  - `git push -u origin main`

API Summary
- `GET /health` – returns configuration and limits
- `POST /upload-url` – body `{ ext: "pdf"|"docx" }` → presigned S3 PUT
- `POST /analyze` – body `{ s3_key }` → issues JSON with page hints and redlines

Disclaimers
- This is a demo/educational tool; not legal advice.
- Analysis limits (pages/size) are conservative to control cost.
- Important: This is not legal advice.
Think of it as a smoke detector, not a firefighter. It tells you when something might be burning, but you still need the professionals to actually put out the fire. Every contract that matters should ultimately be reviewed by a qualified lawyer. 
Real-world scenarios where this helps:
Startups evaluating multiple vendor agreements and need to prioritize which ones need immediate legal attention
Small businesses that can't afford to send every contract to a lawyer but need to catch major problems
Legal teams doing initial triage before dedicating senior attorney time
Founders reviewing term sheets at 2 AM trying to figure out what questions to ask their lawyer in the morning

License
- MIT (see `LICENSE`).
