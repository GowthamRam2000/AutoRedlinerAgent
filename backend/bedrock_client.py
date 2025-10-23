import json
import os
import uuid
from typing import Any, Dict, Optional

import boto3


def get_bedrock_runtime(region: str = None):
    region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    return boto3.client("bedrock-runtime", region_name=region)


def get_bedrock_agent_runtime(region: str = None):
    region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    return boto3.client("bedrock-agent-runtime", region_name=region)


def converse_json(model_id: str, prompt: str, max_tokens: int = 2500, temperature: float = 0.2) -> str:
    client = get_bedrock_runtime()
    try:
        resp = client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={
                "maxTokens": max_tokens,
                "temperature": temperature,
                "topP": 0.9,
            },
        )
        return resp["output"]["message"]["content"][0]["text"]
    except client.exceptions.ValidationException:
        body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": max_tokens,
                "temperature": temperature,
                "stopSequences": []
            }
        })
        resp = client.invoke_model(modelId=model_id, body=body)
        payload = json.loads(resp.get("body").read()) if hasattr(resp.get("body"), "read") else json.loads(resp.get("body"))
        return payload.get("results", [{}])[0].get("outputText") or payload.get("generated_text") or json.dumps(payload)


def converse_agentic(
    model_id: str,
    user_text: str,
    tools: list,
    tool_runner,
    max_tokens: int = 2500,
    temperature: float = 0.2,
    max_rounds: int = 3,
) -> str:
    client = get_bedrock_runtime()
    messages = [{"role": "user", "content": [{"text": user_text}]}]
    tool_config = {"tools": tools}

    last_resp = None
    for _ in range(max_rounds):
        resp = client.converse(
            modelId=model_id,
            messages=messages,
            toolConfig=tool_config,
            inferenceConfig={
                "maxTokens": max_tokens,
                "temperature": temperature,
                "topP": 0.9,
            },
        )
        last_resp = resp
        assistant_message = resp["output"]["message"]
        content = assistant_message.get("content", [])

        messages.append({"role": "assistant", "content": content})
        texts = [c.get("text") for c in content if "text" in c and c.get("text")]
        tool_uses = [c.get("toolUse") for c in content if "toolUse" in c and c.get("toolUse")]

        if tool_uses:
            result_contents = []
            for tu in tool_uses:
                name = tu.get("name")
                input_json = tu.get("input", {})
                tool_use_id = tu.get("toolUseId")
                try:
                    result_text = tool_runner(name, input_json)
                except Exception as e:
                    result_text = f"Tool {name} failed: {e}"
                result_contents.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"text": result_text}],
                    }
                })
            messages.append({"role": "user", "content": result_contents})
            continue

        if texts:
            return "\n".join(texts)
    return json.dumps((last_resp or {}).get("output", {}))


def invoke_agent_text(
    agent_id: str,
    agent_alias_id: str,
    input_text: str,
    session_id: Optional[str] = None,
    region: Optional[str] = None,
) -> str:

    client = get_bedrock_agent_runtime(region)
    sid = session_id or uuid.uuid4().hex
    resp = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=sid,
        inputText=input_text,
    )

    out = []
    stream = resp.get("completion") or resp.get("responseStream")
    if stream is not None:
        for event in stream:
            chunk = event.get("chunk") or event.get("bytes") or event.get("completion")
            if chunk:
                text = chunk.get("text") if isinstance(chunk, dict) else None
                if text:
                    out.append(text)
                else:
                    b = chunk.get("bytes") if isinstance(chunk, dict) else None
                    if b:
                        try:
                            out.append(b.decode("utf-8", errors="ignore"))
                        except Exception:
                            pass
    if not out:
        msg = resp.get("output") or resp.get("response") or {}
        if isinstance(msg, dict):
            # Try common shapes
            content = msg.get("message", {}).get("content")
            if isinstance(content, list):
                texts = [c.get("text") for c in content if isinstance(c, dict) and c.get("text")]
                out.extend(texts)
        if not out:
            return json.dumps(resp)
    return "\n".join(out).strip()
