"""PydanticAI agent wiring, typed tools, history, and observable streaming events."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic_ai import (
    Agent,
    AgentRunResultEvent,
    FunctionToolCallEvent,
    PartDeltaEvent,
    PartStartEvent,
    RunContext,
    TextPart,
    TextPartDelta,
)
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from emporio.config import Settings
from emporio.models import (
    AuthError,
    NotFound,
    OrderStatus,
    PolicyChunk,
    ProductDetails,
    ProductSummary,
)
from emporio.persona import PERSONA_INSTRUCTIONS
from emporio.retrieval import PolicyRetriever
from emporio.tools import (
    get_order_status as lookup_order_status,
)
from emporio.tools import (
    get_product_details as lookup_product_details,
)
from emporio.tools import (
    search_products as lookup_products,
)


@dataclass
class AgentDependencies:
    settings: Settings
    policy_retriever: PolicyRetriever


@dataclass(frozen=True)
class ToolCallTrace:
    name: str
    arguments: dict[str, Any] | str


@dataclass
class TurnResult:
    output: str
    history: list[ModelMessage]
    tool_calls: list[ToolCallTrace]


def _openai_model(settings: Settings) -> OpenAIResponsesModel:
    provider_prefix, separator, model_name = settings.model.partition(":")
    if separator != ":" or provider_prefix != "openai" or not model_name:
        raise ValueError("MODEL must use the `openai:model-name` format for this prototype.")
    return OpenAIResponsesModel(
        model_name,  # type: ignore[arg-type]
        provider=OpenAIProvider(api_key=settings.require_openai_api_key()),
    )


def build_agent(
    settings: Settings, policy_retriever: PolicyRetriever
) -> Agent[AgentDependencies, str]:
    """Build one reusable agent and register its four public tools."""

    agent = Agent(
        _openai_model(settings),
        deps_type=AgentDependencies,
        instructions=PERSONA_INSTRUCTIONS,
        model_settings={"temperature": 0.1},
    )

    @agent.instructions
    def add_reference_date(ctx: RunContext[AgentDependencies]) -> str:
        today = ctx.deps.settings.reference_date or date.today()
        return f"A data de referência desta conversa é {today.isoformat()}."

    @agent.tool
    def search_products(
        ctx: RunContext[AgentDependencies],
        query: str | None = None,
        category: str | None = None,
        max_price: float | None = None,
        min_price: float | None = None,
    ) -> list[ProductSummary]:
        """Search currently available instruments by text, category, and effective price."""

        return lookup_products(
            ctx.deps.settings.database_path,
            query=query,
            category=category,
            max_price=max_price,
            min_price=min_price,
        )

    @agent.tool
    def get_product_details(
        ctx: RunContext[AgentDependencies], product_name: str
    ) -> ProductDetails | NotFound:
        """Get current price, promotion, stock, description, and specs for one instrument."""

        return lookup_product_details(ctx.deps.settings.database_path, product_name)

    @agent.tool
    def get_order_status(
        ctx: RunContext[AgentDependencies],
        customer_phone_or_email: str,
        order_id: int | None = None,
    ) -> list[OrderStatus] | AuthError:
        """Get only the identified customer's orders; an order number is optional."""

        return lookup_order_status(
            ctx.deps.settings.database_path,
            customer_phone_or_email=customer_phone_or_email,
            order_id=order_id,
        )

    @agent.tool
    def search_policies(ctx: RunContext[AgentDependencies], question: str) -> list[PolicyChunk]:
        """Search store policies for hours, payment, returns, shipping, warranty, or privacy."""

        return ctx.deps.policy_retriever.search(question)

    return agent


async def run_turn(
    agent: Agent[AgentDependencies, str],
    dependencies: AgentDependencies,
    prompt: str,
    history: Sequence[ModelMessage] | None = None,
    on_text: Callable[[str], None] | None = None,
    on_tool_call: Callable[[ToolCallTrace], None] | None = None,
) -> TurnResult:
    """Run one complete turn while exposing text deltas and tool-call metadata."""

    prior_history = list(history or [])
    tool_calls: list[ToolCallTrace] = []
    final_result = None
    async with agent.run_stream_events(
        prompt,
        deps=dependencies,
        message_history=prior_history,
    ) as events:
        async for event in events:
            if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                if on_text and event.part.content:
                    on_text(event.part.content)
            elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                if on_text and event.delta.content_delta:
                    on_text(event.delta.content_delta)
            elif isinstance(event, FunctionToolCallEvent):
                trace = ToolCallTrace(event.part.tool_name, event.part.args)
                tool_calls.append(trace)
                if on_tool_call:
                    on_tool_call(trace)
            elif isinstance(event, AgentRunResultEvent):
                final_result = event.result

    if final_result is None:
        raise RuntimeError("Agent stream ended without a final result.")
    return TurnResult(
        output=final_result.output,
        history=[*prior_history, *final_result.new_messages()],
        tool_calls=tool_calls,
    )
