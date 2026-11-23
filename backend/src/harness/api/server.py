import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic_ai.exceptions import AgentRunError, UserError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from harness.agents.harness import AgentHarness
from harness.application import Harness, WorkItemConflict
from harness.git.repository import GitError
from harness.operations.review import ReviewDecision
from harness.persistence.catalog import ProjectEntry, WorkItemEntry
from harness.persistence.database import Database
from harness.persistence.models import WorkItemStatus
from harness.runtime import RuntimeSettings

from .mcp_server import build_mcp


class ProjectRequest(BaseModel):
    name: str
    repository_path: str


class WorkItemRequest(BaseModel):
    title: str | None = None


class MessageRequest(BaseModel):
    message: str


class ApprovalRequest(BaseModel):
    base_ref: str | None = None


class ReviewRequest(BaseModel):
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

    @app.get("/api/projects/{project_id}/work-items")
    def work_items(project_id: int, status: WorkItemStatus = WorkItemStatus.IN_PROGRESS) -> list[WorkItemEntry]:
        return harness.work_items(project_id, status)

    @app.post("/api/projects/{project_id}/work-items", status_code=201)
    def create_work_item(project_id: int, body: WorkItemRequest) -> WorkItemEntry:
        return harness.create_work_item(project_id, body.title)

    @app.get("/api/work-items/{item_id}")
    def inspect(item_id: int) -> dict:
        return harness.inspect(item_id)

    @app.post("/api/work-items/{item_id}/messages")
    def talk(item_id: int, body: MessageRequest) -> dict:
        return harness.talk(item_id, body.message)

    @app.post("/api/work-items/{item_id}/approve")
    def approve(item_id: int, body: ApprovalRequest) -> dict:
        return harness.approve(item_id, body.base_ref)

    @app.post("/api/work-items/{item_id}/implement")
    def implement(item_id: int) -> dict:
        return harness.implement(item_id)

    @app.post("/api/work-items/{item_id}/review")
    def review(item_id: int, body: ReviewRequest) -> dict:
        return harness.review(item_id, body.decision, body.note, body.earlier_id)

    app.mount("/", mcp_app)
    return app


def main() -> None:
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
