from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from starlette.concurrency import run_in_threadpool

from harness.application import CommandActivity, Harness
from harness.persistence.catalog import ProjectEntry, WorkItemEntry
from harness.persistence.models import WorkItemStatus
from harness.queries import HarnessQueries


def build_mcp(harness: Harness, queries: HarnessQueries) -> MCPServer:
    server = MCPServer("Harness", instructions="Inspect and drive work items in the local Harness.")
    read_only = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

    @server.tool(annotations=read_only)
    async def list_projects() -> list[ProjectEntry]:
        """List the projects registered in this harness."""
        return await run_in_threadpool(queries.projects)

    @server.tool(annotations=read_only)
    async def list_work_items(project_id: int, status: WorkItemStatus = WorkItemStatus.IN_PROGRESS) -> list[WorkItemEntry]:
        """List a project's work items by status."""
        return await run_in_threadpool(queries.work_items, project_id, status)

    @server.tool(annotations=read_only)
    async def inspect_work_item(item_id: int) -> dict[str, Any]:
        """Show ready node IDs, blockers, conversations, and transitions."""
        return await run_in_threadpool(queries.inspect, item_id)

    @server.tool(annotations=read_only)
    async def work_item_activity(item_id: int) -> CommandActivity | None:
        """Get progress and the latest model turn outcome for this work item."""
        return await run_in_threadpool(queries.activity, item_id)

    @server.tool()
    async def register_project(name: str, repository_path: str) -> ProjectEntry:
        """Register an existing local Git repository by absolute path."""
        return await run_in_threadpool(harness.register_project, name, repository_path)

    @server.tool()
    async def create_work_item(project_id: int, message: str, title: str | None = None) -> WorkItemEntry:
        """Create a work item and start goal alignment with the opening message."""
        return await run_in_threadpool(harness.create_work_item, project_id, message, title)

    @server.tool()
    async def close_work_item(item_id: int) -> dict[str, Any]:
        """Move a work item to Complete and preserve its history, without recording review acceptance."""
        await run_in_threadpool(harness.close_work_item, item_id)
        return await run_in_threadpool(queries.inspect, item_id)

    @server.tool()
    async def send_message(item_id: int, node_id: int, message: str) -> dict[str, Any]:
        """Queue a follow-up in the specified node's existing conversation."""
        await run_in_threadpool(harness.follow_up, item_id, node_id, message)
        return await run_in_threadpool(queries.inspect, item_id)

    @server.tool()
    async def approve_edge(item_id: int, edge_id: int, data: dict[str, object] | None = None) -> dict[str, Any]:
        """Approve an edge, optionally updating its destination data before starting the first turn."""
        await run_in_threadpool(harness.approve_edge, item_id, edge_id, data)
        return await run_in_threadpool(queries.inspect, item_id)

    @server.tool()
    async def add_rollback(item_id: int, node_id: int, target_id: int, note: str) -> dict[str, Any]:
        """Add a rollback edge from the current node to an existing previous node."""
        await run_in_threadpool(harness.rollback, item_id, node_id, target_id, note)
        return await run_in_threadpool(queries.inspect, item_id)

    return server
