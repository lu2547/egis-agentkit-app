"""仅供接入验收的 Java 协议服务；生产客户端始终连接配置的 Java 服务。

使用两份用户提供文档的真实说明片段验证协议与 UI，不实现知识库检索引擎。
/openapi/v1/* 校验独立 HMAC；用户原文入口校验测试 JWT Cookie。
仅显式运行本模块才启用，生产 App 不导入或回退到此模块。
"""

import hashlib
import hmac
import os
import time
from pathlib import Path

import jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse

app = FastAPI(title="知识库 Java 接口契约验收服务")
KB_ID = "kb_contract_docs"
KB_NAME = "接口契约验收库"
COOKIE_NAME = "kb_auth_token"
MAX_CLOCK_SKEW_SECONDS = 300
COOKIE_LIFETIME_SECONDS = 3600
NONCES = {}
METRICS = {"query_requests": 0, "catalog_requests": 0, "document_requests": 0}
DOCS = {
    "doc_api": {
        "title": "Java 接口规范（验收资料）",
        "section": "认证 / OpenAPI 签名",
        "snippet": "普通业务接口使用 kb_auth_token JWT Cookie 认证，无效或缺失时可尝试 CAS_SSO_COOKIE。OpenAPI 使用独立的 HMAC-SHA256 签名，必须提供 X-App-Id、X-Timestamp、X-Nonce、X-Signature；query.run 用于执行检索。应用权限与登录用户权限相互独立。",
        "file": "java-api.txt",
    },
    "doc_database": {
        "title": "知识库表结构（验收资料）",
        "section": "文档版本快照 / 版本正文快照",
        "snippet": "llm_document 管理文档主生命周期；llm_document_version 保存文档版本快照，(document_id, version_no) 唯一。llm_document_version_content 保存版本正文及 content_sha256；其 version_id 唯一并关联 llm_document_version.id，不通过 version_no 关联正文。父、子和摘要节点分别使用 llm_node_parent、llm_node_child、llm_node_summary。llm_integration_app 存储 OpenAPI 应用的 scopes 和 kb_scope。",
        "file": "database.txt",
    },
}


def envelope(data=None, *, code=0, message="OK", status=200):
    return JSONResponse(
        {"code": code, "message": message, "data": data, "success": code == 0},
        status_code=status,
    )


@app.middleware("http")
async def authenticate(request: Request, call_next):
    path = request.url.path.removeprefix("/knowledge")
    if path.startswith("/openapi/"):
        body = await request.body()
        now = int(time.time())
        try:
            timestamp = int(request.headers["X-Timestamp"])
            nonce = request.headers["X-Nonce"]
            assert abs(now - timestamp) <= MAX_CLOCK_SKEW_SECONDS
            assert (
                request.headers["X-App-Id"] == os.environ["AGENTKIT_KNOWLEDGE_APP_ID"]
            )
            assert nonce and nonce not in NONCES
            query = "&".join(
                f"{key}={value}"
                for key, value in sorted(request.query_params.multi_items())
            )
            canonical = "\n".join(
                (
                    request.method,
                    path,
                    query,
                    str(timestamp),
                    nonce,
                    hashlib.sha256(body).hexdigest(),
                )
            )
            signature = hmac.new(
                os.environ["AGENTKIT_KNOWLEDGE_SECRET"].encode(),
                canonical.encode(),
                hashlib.sha256,
            ).hexdigest()
            assert hmac.compare_digest(
                request.headers.get("X-Signature", ""), signature
            )
        except (KeyError, ValueError, AssertionError):
            return envelope(code=1001, message="契约验收签名无效", status=401)
        for value, expires in list(NONCES.items()):
            if expires < now:
                NONCES.pop(value, None)
        NONCES[nonce] = now + MAX_CLOCK_SKEW_SECONDS
    elif path.startswith(("/query/documents/", "/kb/")):
        try:
            jwt.decode(
                request.cookies.get(COOKIE_NAME, ""),
                os.environ["AGENTKIT_KNOWLEDGE_FIXTURE_COOKIE_SECRET"],
                algorithms=["HS256"],
                audience="kb-contract",
            )
        except jwt.PyJWTError:
            return envelope(code=1001, message="未登录或登录已过期", status=401)
    return await call_next(request)


@app.get("/knowledge/openapi/v1/kb")
async def list_bases():
    METRICS["catalog_requests"] += 1
    return envelope(
        [
            {
                "id": KB_ID,
                "name": KB_NAME,
                "category": "enterprise",
                "ownerId": "acceptance",
                "description": "只用于核验知识库接入效果，内容取自用户提供的接口和建表文档。",
            }
        ]
    )


@app.post("/knowledge/openapi/v1/query")
async def query(request: Request):
    data = await request.json()
    allowed = {"query", "topK", "threshold", "sort", "scope"}
    if (
        not isinstance(data, dict)
        or set(data) - allowed
        or not str(data.get("query", "")).strip()
    ):
        return envelope(code=1000, message="QueryRequest 不符合契约", status=400)
    if data.get("scope", {}).get("kbIds") != [KB_ID]:
        return envelope(code=1006, message="无权限访问该资源", status=403)
    METRICS["query_requests"] += 1
    references, items = [], []
    for index, (identifier, document) in enumerate(DOCS.items(), 1):
        references.append(
            {
                "refIndex": index,
                "parentId": "parent_" + identifier,
                "docId": identifier,
                "docName": document["title"],
                "kb": KB_NAME,
                "titlePath": document["section"],
                "snippet": document["snippet"],
                "score": 0.98,
            }
        )
        items.append(
            {
                "rank": index,
                "score": 0.98,
                "kb": KB_NAME,
                "doc": document["title"],
                "ver": "v1",
                "cpath": document["section"],
                "chunk": "parent_" + identifier,
                "match": document["snippet"],
                "full": document["snippet"],
            }
        )
    return envelope(
        {
            "total": len(items),
            "highRelevance": len(items),
            "costMs": 1,
            "items": items,
            "answer": "\n\n".join(document["snippet"] for document in DOCS.values()),
            "references": references,
        }
    )


@app.get("/knowledge/query/documents/{document_id}/raw")
@app.get("/knowledge/kb/{kb_id}/documents/{document_id}/raw/preview")
async def document_url(document_id: str, kb_id: str | None = None):
    if document_id not in DOCS or kb_id not in (None, KB_ID):
        return envelope(code=1004, message="文档不存在", status=404)
    METRICS["document_requests"] += 1
    return envelope({"url": "/knowledge/__contract/files/" + document_id})


@app.get("/knowledge/__contract/files/{document_id}")
async def file(document_id: str):
    if document_id not in DOCS:
        return PlainTextResponse("not found", status_code=404)
    source = Path(os.environ["AGENTKIT_KB_CONTRACT_DIR"]) / DOCS[document_id]["file"]
    return PlainTextResponse(
        source.read_text(),
        headers={
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'self'",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/knowledge/__contract/login")
async def login():
    token = jwt.encode(
        {
            "sub": "acceptance-user",
            "aud": "kb-contract",
            "exp": int(time.time()) + COOKIE_LIFETIME_SECONDS,
        },
        os.environ["AGENTKIT_KNOWLEDGE_FIXTURE_COOKIE_SECRET"],
        algorithm="HS256",
    )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        path="/knowledge",
        max_age=COOKIE_LIFETIME_SECONDS,
    )
    return response


@app.get("/knowledge/__contract/health")
async def health():
    return {"status": "contract-acceptance-only", **METRICS}
