from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from pydantic_ai_harness.spend_limits import SpendRecordedEvent
from sqlalchemy import func, select

from .database import Database
from .models import ModelUsage, Node, WorkItem


@dataclass(frozen=True)
class UsageSummary:
    responses: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    estimated_api_usd: Decimal | None
    unpriced_responses: int
    unmeasured_requests: int
    codex_responses: int


class UsageRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def record(self, node_id: int, run_id: str | None, provider: str, event: SpendRecordedEvent) -> None:
        with self.database.session() as session:
            session.add(ModelUsage(
                node_id=node_id,
                run_id=run_id,
                recorded_at=datetime.now(UTC),
                provider=provider,
                model=event.model,
                input_tokens=event.usage.input_tokens,
                cached_input_tokens=event.usage.cache_read_tokens,
                output_tokens=event.usage.output_tokens,
                unmeasured_requests=event.usage.unmeasured_requests,
                priced=event.priced,
                estimated_api_nanodollars=round(event.usd.scaleb(9)) if event.priced or event.usd else None,
            ))

    def summarize(self, project_id: int, *, item_id: int | None = None) -> UsageSummary:
        totals = (
            select(
                func.count(ModelUsage.id).label("responses"),
                func.coalesce(func.sum(ModelUsage.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(ModelUsage.cached_input_tokens), 0).label("cached_input_tokens"),
                func.coalesce(func.sum(ModelUsage.output_tokens), 0).label("output_tokens"),
                func.sum(ModelUsage.estimated_api_nanodollars).label("estimated_api_nanodollars"),
                func.count().filter(~ModelUsage.priced).label("unpriced_responses"),
                func.coalesce(func.sum(ModelUsage.unmeasured_requests), 0).label("unmeasured_requests"),
                func.count().filter(ModelUsage.provider == "openai-codex").label("codex_responses"),
            )
            .select_from(ModelUsage)
            .join(Node, ModelUsage.node_id == Node.id)
            .join(WorkItem, Node.work_item_id == WorkItem.id)
            .where(WorkItem.project_id == project_id)
        )
        if item_id is not None:
            totals = totals.where(WorkItem.id == item_id)
        with self.database.session() as session:
            values = dict(session.execute(totals).mappings().one())
        nanodollars = values.pop("estimated_api_nanodollars")
        estimated_api_usd = Decimal(nanodollars).scaleb(-9) if nanodollars is not None else None
        return UsageSummary(estimated_api_usd=estimated_api_usd, **values)
