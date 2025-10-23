import json
import os
import tempfile
import time
import uuid
from typing import Dict

import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from .models import PresignRequest, PresignResponse, AnalyzeRequest, AnalyzeResult, HealthResponse, Issue
from .parsers import detect_type_from_key, parse_pdf, parse_docx
from .analyzer import analyze_with_bedrock, analyze_with_bedrock_agent, locate_snippet_pages


REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
UPLOADS_BUCKET = os.environ.get("UPLOADS_BUCKET", os.environ.get("AWS_S3_UPLOADS_BUCKET", ""))
MAX_PAGES = int(os.environ.get("MAX_PAGES", "20"))
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "5"))
USE_BEDROCK_AGENT = (os.environ.get("USE_BEDROCK_AGENT", "0").strip().lower() in {"1", "true", "yes"})
AGENT_ID = os.environ.get("BEDROCK_AGENT_ID", "")
AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "")

_s3 = boto3.client("s3", region_name=REGION)

app = FastAPI(title="Auto Redliner (India)")

allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        region=REGION,
        model_id=MODEL_ID,
        bucket=UPLOADS_BUCKET,
        limits={"max_pages": MAX_PAGES, "max_file_mb": MAX_FILE_MB, "agent": USE_BEDROCK_AGENT},
    )


@app.post("/upload-url", response_model=PresignResponse)
def create_upload_url(req: PresignRequest):
    if not UPLOADS_BUCKET:
        raise HTTPException(status_code=500, detail="UPLOADS_BUCKET not configured")
    if req.ext not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="Only pdf or docx supported")

    key = f"uploads/{int(time.time())}-{uuid.uuid4().hex}.{req.ext}"
    content_type = "application/pdf" if req.ext == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    url = _s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": UPLOADS_BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=900,
    )
    headers = {"Content-Type": content_type}
    return PresignResponse(key=key, url=url, headers=headers, content_type=content_type)


@app.post("/analyze", response_model=AnalyzeResult)
def analyze(req: AnalyzeRequest):
    if not UPLOADS_BUCKET:
        raise HTTPException(status_code=500, detail="UPLOADS_BUCKET not configured")
    if not req.s3_key:
        raise HTTPException(status_code=400, detail="s3_key required")

    ftype = detect_type_from_key(req.s3_key)

    with tempfile.TemporaryDirectory() as td:
        local_path = os.path.join(td, os.path.basename(req.s3_key))
        try:
            _s3.download_file(UPLOADS_BUCKET, req.s3_key, local_path)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"File not found: {e}")

        size_mb = os.path.getsize(local_path) / (1024 * 1024)
        if size_mb > MAX_FILE_MB:
            raise HTTPException(status_code=400, detail=f"File too large: {size_mb:.1f} MB > {MAX_FILE_MB} MB")

        if ftype == "pdf":
            pages, total = parse_pdf(local_path, max_pages=MAX_PAGES)
        elif ftype == "docx":
            pages, total = parse_docx(local_path, max_pages=MAX_PAGES)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

    if not any(pages):
        raise HTTPException(status_code=400, detail="No extractable text found in document")

    if USE_BEDROCK_AGENT and AGENT_ID and AGENT_ALIAS_ID:
        data = analyze_with_bedrock_agent(AGENT_ID, AGENT_ALIAS_ID, pages)
    else:
        data = analyze_with_bedrock(MODEL_ID, pages)

    issues_payload = []
    for idx, raw_issue in enumerate(data.get("issues", []), start=1):
        try:
            snippet = raw_issue.get("exact_text_snippet")
            page_nums = locate_snippet_pages(pages, snippet) if snippet else []
            issue = Issue(
                issue_id=str(raw_issue.get("issue_id") or f"i{idx}"),
                category=str(raw_issue.get("category") or "general"),
                severity=str(raw_issue.get("severity") or "medium").lower(),
                risk_summary=str(raw_issue.get("risk_summary") or ""),
                recommendation=str(raw_issue.get("recommendation") or ""),
                exact_text_snippet=snippet,
                page_hint=raw_issue.get("page_hint"),
                page_numbers=page_nums,
                redline_suggestion=raw_issue.get("redline_suggestion"),
            )
            issues_payload.append(issue)
        except Exception:
            continue

    result = AnalyzeResult(
        issues=issues_payload,
        summary=str(data.get("summary") or ""),
        total_issues=len(issues_payload),
    )
    return result


handler = Mangum(app)
