import os
from contextlib import asynccontextmanager
from html import escape

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from pydantic_ai.exceptions import AgentRunError, UserError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from harness.agents.harness import AgentHarness
from harness.application import Harness, WorkItemConflict
from harness.git.repository import GitError
from harness.operations.review import ReviewDecision
from harness.operations.work_session import ScopedWork
from harness.persistence.catalog import ProjectEntry, WorkItemEntry
from harness.persistence.database import Database
from harness.persistence.models import WorkItemStatus
from harness.persistence.usage import UsageSummary
from harness.runtime import RuntimeSettings

from .mcp_server import build_mcp


class ProjectRequest(BaseModel):
    name: str
    repository_path: str


class WorkItemRequest(BaseModel):
    title: str | None = None


class NodeRequest(BaseModel):
    node_id: int


class StartRequest(NodeRequest):
    message: str = ""


class MessageRequest(NodeRequest):
    message: str


class ScopedRequest(NodeRequest):
    pieces: list[ScopedWork]


class ApprovalRequest(NodeRequest):
    pieces: list[ScopedWork] | None = None


class ReopenRequest(BaseModel):
    node_id: int
    note: str


class ReviewRequest(NodeRequest):
    decision: ReviewDecision
    note: str = ""
    earlier_id: int | None = None


def create_app(settings: RuntimeSettings | None = None, *, agents: AgentHarness | None = None) -> FastAPI:
    settings = settings or RuntimeSettings.from_environment()
    database = Database(settings.state_dir / "harness.sqlite3")
    harness = Harness(database, settings, agents=agents)
    mcp = build_mcp(harness)
    mcp_app = mcp.streamable_http_app(stateless_http=True, json_response=True)

    @asynccontextmanager
    async def lifespan(_app):
        database.initialize()
        try:
            async with mcp.session_manager.run():
                yield
        finally:
            database.close()

    app = FastAPI(title="Harness", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    ports = (os.environ.get("HARNESS_FRONTEND_PORT", "5173"), os.environ.get("HARNESS_API_PORT", "8000"))
    origins = {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost") for port in ports}

    @app.middleware("http")
    async def local_browser(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.url.path.startswith("/api/") and origin is not None and origin not in origins:
            return JSONResponse({"detail": "This browser origin is not allowed."}, status_code=403)
        return await call_next(request)

    error_codes = {
        LookupError: 404, WorkItemConflict: 409, ValueError: 400,
        GitError: 400, UserError: 400, AgentRunError: 502,
    }

    async def operation_error(_request: Request, error: Exception):
        status = next(code for error_type, code in error_codes.items() if isinstance(error, error_type))
        return JSONResponse({"detail": str(error)}, status_code=status)

    for error_type in error_codes:
        app.add_exception_handler(error_type, operation_error)

    @app.get("/api/projects")
    def projects() -> list[ProjectEntry]:
        return harness.projects()

    @app.post("/api/projects", status_code=201)
    def register_project(body: ProjectRequest) -> ProjectEntry:
        return harness.register_project(body.name, body.repository_path)

    @app.get("/api/projects/{project_id}/usage")
    def project_usage(project_id: int) -> UsageSummary:
        return harness.project_usage(project_id)

    @app.get("/api/projects/{project_id}/work-items")
    def work_items(project_id: int, status: WorkItemStatus = WorkItemStatus.IN_PROGRESS) -> list[WorkItemEntry]:
        return harness.work_items(project_id, status)

    @app.post("/api/projects/{project_id}/work-items", status_code=201)
    def create_work_item(project_id: int, body: WorkItemRequest) -> WorkItemEntry:
        return harness.create_work_item(project_id, body.title)

    @app.get("/api/work-items/{item_id}")
    def inspect(item_id: int) -> dict:
        return harness.inspect(item_id)

    @app.get("/api/work-items/{item_id}/usage")
    def work_item_usage(item_id: int) -> UsageSummary:
        return harness.work_item_usage(item_id)

    @app.get("/api/work-items/{item_id}/activity")
    def activity(item_id: int) -> dict | None:
        return harness.activity(item_id)

    @app.get("/api/work-items/{item_id}/nodes/{node_id}/file", response_class=HTMLResponse)
    def repository_file(item_id: int, node_id: int, path: str = Query(max_length=4096)) -> HTMLResponse:
        content = harness.repository_file(item_id, node_id, path)
        filename = escape(path)
        lines = "".join(
            f'<span id="L{number}"><a href="#L{number}">{number}</a>{escape(line)}\n</span>'
            for number, line in enumerate(content.splitlines(), 1)
        )
        return HTMLResponse(
            f'''<!doctype html><html lang="en"><meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>{filename}</title><style>
            body {{ font: 1rem system-ui, sans-serif; margin: 1.5rem; color: #182334; }}
            h1 {{ font-size: 1.2rem; overflow-wrap: anywhere; }} pre {{ overflow: auto; line-height: 1.5; }}
            span {{ display: block; }} span:target {{ background: #e8f0fa; }}
            a {{ display: inline-block; width: 5ch; margin-right: 1ch; color: #54657b; text-align: right; }}
            </style><h1>{filename}</h1><pre>{lines}</pre></html>''',
            headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'"},
        )

    @app.get("/api/work-items/{item_id}/nodes/{node_id}/diff")
    def implementation_diff(item_id: int, node_id: int) -> dict:
        return harness.implementation_diff(item_id, node_id)

    @app.get("/api/work-items/{item_id}/nodes/{node_id}/diff/files/{file_index}")
    def implementation_file_diff(item_id: int, node_id: int, file_index: int, commit: str) -> dict:
        return harness.implementation_file_diff(item_id, node_id, file_index, commit)

    @app.post("/api/work-items/{item_id}/close")
    def close_work_item(item_id: int) -> dict:
        return harness.close_work_item(item_id)

    @app.post("/api/work-items/{item_id}/start")
    def start(item_id: int, body: StartRequest) -> dict:
        return harness.start(item_id, body.node_id, body.message)

    @app.post("/api/work-items/{item_id}/messages")
    def follow_up(item_id: int, body: MessageRequest) -> dict:
        return harness.follow_up(item_id, body.node_id, body.message)

    @app.post("/api/work-items/{item_id}/approve")
    def approve(item_id: int, body: ApprovalRequest) -> dict:
        return harness.approve(item_id, body.node_id, body.pieces)

    @app.post('/api/work-items/{item_id}/discover')
    def discover(item_id: int, body: ScopedRequest) -> dict:
        return harness.discover(item_id, body.pieces, body.node_id)

    @app.post('/api/work-items/{item_id}/reopen')
    def reopen(item_id: int, body: ReopenRequest) -> dict:
        return harness.reopen(item_id, body.node_id, body.note)

    @app.post("/api/work-items/{item_id}/review")
    def review(item_id: int, body: ReviewRequest) -> dict:
        return harness.review(item_id, body.node_id, body.decision, body.note, body.earlier_id)

    app.mount("/", mcp_app)
    return app


def main() -> None:
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
