from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from starlette.concurrency import run_in_threadpool

from harness.application import Harness
from harness.operations.review import ReviewDecision
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
        """Show the current node, visible conversation, and recorded graph transitions."""
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
    async def send_message(item_id: int, message: str) -> dict[str, Any]:
        """Send a turn to the current goal alignment or planning conversation."""
        return await run_in_threadpool(harness.talk, item_id, message)

    @server.tool()
    async def approve_draft(item_id: int) -> dict[str, Any]:
        """Save the current draft as approved and advance to the next node."""
        return await run_in_threadpool(harness.approve, item_id)

    @server.tool()
    async def run_implementation(item_id: int) -> dict[str, Any]:
        """Run the current approved implementation on its branch and advance to review."""
        return await run_in_threadpool(harness.implement, item_id)

    @server.tool()
    async def record_review(
        item_id: int, decision: ReviewDecision, note: str = "", earlier_id: int | None = None,
    ) -> dict[str, Any]:
        """Record the user's review decision for the current node."""
        return await run_in_threadpool(harness.review, item_id, decision, note, earlier_id)

    return server
