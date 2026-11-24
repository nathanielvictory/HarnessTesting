from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from starlette.concurrency import run_in_threadpool

from harness.application import Harness
from harness.operations.review import ReviewDecision
from harness.operations.work_session import ScopedWork
from harness.persistence.catalog import ProjectEntry, WorkItemEntry
from harness.persistence.models import WorkItemStatus


def build_mcp(harness: Harness) -> MCPServer:
    server = MCPServer("Harness", instructions="Inspect and drive work items in the local Harness.")
    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

    @server.tool(annotations=read_only)
    async def list_projects() -> list[ProjectEntry]:
        """List the projects registered in this harness."""
        return await run_in_threadpool(harness.projects)

    @server.tool(annotations=read_only)
    async def list_work_items(project_id: int, status: WorkItemStatus = WorkItemStatus.IN_PROGRESS) -> list[WorkItemEntry]:
        """List a project's work items by status."""
        return await run_in_threadpool(harness.work_items, project_id, status)

    @server.tool(annotations=read_only)
    async def inspect_work_item(item_id: int) -> dict[str, Any]:
        """Show ready node IDs, blockers, conversations, and transitions."""
        return await run_in_threadpool(harness.inspect, item_id)

    @server.tool()
    async def register_project(name: str, repository_path: str) -> ProjectEntry:
        """Register an existing local Git repository by absolute path."""
        return await run_in_threadpool(harness.register_project, name, repository_path)

    @server.tool()
    async def create_work_item(project_id: int, title: str | None = None) -> WorkItemEntry:
        """Create a work item at goal alignment."""
        return await run_in_threadpool(harness.create_work_item, project_id, title)

    @server.tool()
    async def close_work_item(item_id: int) -> dict[str, Any]:
        """Move a work item to Complete and preserve its history, without recording review acceptance."""
        return await run_in_threadpool(harness.close_work_item, item_id)

    @server.tool()
    async def start_node(item_id: int, node_id: int, message: str = '') -> dict[str, Any]:
        """Start the subagent on the specified ready node. The opening message is optional."""
        return await run_in_threadpool(harness.start, item_id, node_id, message)

    @server.tool()
    async def send_message(item_id: int, node_id: int, message: str) -> dict[str, Any]:
        """Send a follow-up in the specified ready node's existing conversation."""
        return await run_in_threadpool(harness.follow_up, item_id, node_id, message)

    @server.tool()
    async def approve_draft(item_id: int, node_id: int,
                            pieces: list[ScopedWork] | None = None) -> dict[str, Any]:
        """Approve a ready draft; optionally delegate a plan to pieces (zero-based dependency indexes)."""
        return await run_in_threadpool(harness.approve, item_id, node_id, pieces)

    @server.tool()
    async def discover_work(item_id: int, node_id: int, pieces: list[ScopedWork]) -> dict[str, Any]:
        """Suspend a ready step until its new scoped prerequisites are accepted."""
        return await run_in_threadpool(harness.discover, item_id, pieces, node_id)

    @server.tool()
    async def reopen_step(item_id: int, node_id: int, note: str) -> dict[str, Any]:
        """Replace a brief, plan, or implementation without deleting its history."""
        return await run_in_threadpool(harness.reopen, item_id, node_id, note)

    @server.tool()
    async def record_review(
        item_id: int, node_id: int, decision: ReviewDecision, note: str = "", earlier_id: int | None = None,
    ) -> dict[str, Any]:
        """Record the user's review decision for the specified review node."""
        return await run_in_threadpool(harness.review, item_id, node_id, decision, note, earlier_id)

    return server
