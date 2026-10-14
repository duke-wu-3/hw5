"""Builds the five-agent team and runs each agent loop with a step-by-step audit.

- Model: gpt-6-luna only, through Portkey (PORTKEY_API_KEY).
- Shop facts: only the Campus Customs MCP server (mcp_server/server.py),
  attached in-process. Each agent sees only the MCP tools its role needs.
- Delegation: every agent has an ask_<other> tool for each of the other four
  (full connectivity), guarded by a depth cap, a no-loop rule and a
  team-wide delegation budget.
- Token limits: one RunUsage is shared by every nested run, so UsageLimits
  cap the whole team, not each agent separately.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from typing import Any

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv  # noqa: E402

# PORTKEY_API_KEY can come from the shell or from hw5/.env (see .env.example).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from openai import AsyncOpenAI  # noqa: E402
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import (
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits
from pydantic_core import to_json

import audit
from agents import accounting, boss, customer_service, facilities, inventory
from models import AgentName, TeamDeps, TeamReport

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
PROMPTS = BACKEND / "prompts"
sys.path.insert(0, str(ROOT / "mcp_server"))

MODEL_NAME = "gpt-6-luna"  # the only model allowed in this project
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Token and loop guardrails (team-wide for one run).
MAX_DEPTH = 2  # boss -> specialist -> one more specialist, no deeper
MAX_DELEGATIONS = 12
MAX_OUTPUT_TOKENS = 6000  # per model response
LIMITS = UsageLimits(request_limit=60, tool_calls_limit=90, total_tokens_limit=400_000)
PREVIEW_CHARS = 800

SPECS = {m.NAME: m for m in (boss, inventory, accounting, facilities, customer_service)}

_model: OpenAIResponsesModel | None = None
_mcp: MCPToolset | None = None
_agents: dict[str, Agent[TeamDeps, Any]] = {}


def _get_model() -> OpenAIResponsesModel:
    global _model
    if _model is None:
        key = os.getenv("PORTKEY_API_KEY", "").strip()
        if not key:
            raise RuntimeError("PORTKEY_API_KEY is not set.")
        client = AsyncOpenAI(
            api_key=key, base_url=PORTKEY_BASE_URL, default_headers={"x-portkey-api-key": key}
        )
        _model = OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
    return _model


async def _sign_ticket_updates(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict):
    """Stamp update_ticket notes with the real calling agent, so an agent
    cannot sign a note as someone else."""
    if name == "update_ticket":
        args = {**args, "agent": ctx.deps.agent}
    return await call_tool(name, args)


def _get_mcp() -> MCPToolset:
    global _mcp
    if _mcp is None:
        from server import mcp as campus_customs_mcp

        _mcp = MCPToolset(campus_customs_mcp, process_tool_call=_sign_ticket_updates)
    return _mcp


def _preview(value: Any) -> str:
    text = value if isinstance(value, str) else to_json(value).decode("utf-8", "replace")
    text = " ".join(text.split())
    return text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1] + "…"


def _usage(u: RunUsage) -> dict[str, int]:
    return {
        "requests": u.requests,
        "tool_calls": u.tool_calls,
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
    }


def _add_delegation_tools(agent: Agent[TeamDeps, Any], me: str) -> None:
    for target in SPECS:
        if target == me:
            continue

        def make(target: AgentName):
            async def ask(ctx: RunContext[TeamDeps], request: str, ticket_ids: list[int]) -> Any:
                deps = ctx.deps
                if target in deps.chain:
                    return {"refused": f"{target} is already in this chain ({' > '.join(deps.chain)}); no loops. Decide with what you have."}
                if deps.depth >= MAX_DEPTH:
                    return {"refused": f"Delegation depth {MAX_DEPTH} reached. Finish your own work and name {target} as a follow-up."}
                if deps.budget.delegations >= MAX_DELEGATIONS:
                    return {"refused": f"Team delegation budget ({MAX_DELEGATIONS}) used up. Finish with what you have."}
                deps.budget.delegations += 1
                prompt = f"Request from {deps.agent} about ticket(s) {ticket_ids}:\n{request}"
                child = TeamDeps(run_id=deps.run_id, chain=[*deps.chain, target], budget=deps.budget)
                report = await run_agent(target, prompt, child, usage=ctx.usage)
                return report.model_dump()

            ask.__name__ = f"ask_{target}"
            ask.__doc__ = (
                f"Delegate a focused question or task to the {target} agent "
                f"({SPECS[target].PERSONA}) and get its structured report back. "
                "Give the ticket ids and exactly what you need."
            )
            return ask

        agent.tool(make(target))


def get_agent(name: str) -> Agent[TeamDeps, Any]:
    if name not in _agents:
        spec = SPECS[name]
        allowed = set(spec.MCP_TOOLS)
        agent = Agent(
            _get_model(),
            name=name,
            deps_type=TeamDeps,
            output_type=spec.OUTPUT_TYPE,
            instructions=(PROMPTS / spec.PROMPT_FILE).read_text(encoding="utf-8"),
            toolsets=[_get_mcp().filtered(lambda ctx, td, allowed=allowed: td.name in allowed)],
            model_settings=OpenAIResponsesModelSettings(
                max_tokens=MAX_OUTPUT_TOKENS, openai_reasoning_summary="auto"
            ),
            retries=2,
        )
        _add_delegation_tools(agent, name)
        _agents[name] = agent
    return _agents[name]


async def run_agent(name: str, prompt: str, deps: TeamDeps, usage: RunUsage) -> Any:
    """Run one agent loop, appending every step to output/audit_trail.json."""
    agent = get_agent(name)
    base = {
        "run_id": deps.run_id,
        "agent": name,
        "persona": SPECS[name].PERSONA,
        "chain": " > ".join(deps.chain),
        "depth": deps.depth,
        "model": MODEL_NAME,
    }
    step = 0

    def log(kind: str, **detail: Any) -> None:
        audit.append({**base, "step": step, "kind": kind, **detail, "team_usage": _usage(usage)})

    try:
        async with agent.iter(prompt, deps=deps, usage=usage, usage_limits=LIMITS) as run:
            async for node in run:
                step += 1
                if Agent.is_user_prompt_node(node):
                    log("start", prompt=prompt)
                elif Agent.is_model_request_node(node):
                    results, retries = [], []
                    for part in node.request.parts:
                        if isinstance(part, ToolReturnPart):
                            results.append({"tool": part.tool_name, "call_id": part.tool_call_id, "result": _preview(part.content)})
                        elif isinstance(part, RetryPromptPart):
                            retries.append({"tool": part.tool_name, "error": _preview(part.content)})
                        elif isinstance(part, UserPromptPart) and step > 2:
                            results.append({"user": _preview(part.content)})
                    log("model_request", tool_results=results, retries=retries)
                elif Agent.is_call_tools_node(node):
                    resp = node.model_response
                    log(
                        "model_response",
                        thinking=[p.content for p in resp.parts if isinstance(p, ThinkingPart) and p.content],
                        text=[p.content for p in resp.parts if isinstance(p, TextPart) and p.content],
                        tool_calls=[
                            {"tool": p.tool_name, "call_id": p.tool_call_id, "args": p.args_as_dict()}
                            for p in resp.parts
                            if isinstance(p, ToolCallPart)
                        ],
                        finish_reason=resp.finish_reason,
                        response_tokens={"input": resp.usage.input_tokens, "output": resp.usage.output_tokens},
                    )
                elif Agent.is_end_node(node):
                    log("final_output", output=node.data.output.model_dump())
        return run.result.output
    except Exception as exc:
        step += 1
        log("error", error=f"{type(exc).__name__}: {exc}"[:500])
        raise


async def run_team(
    prompt: str = "Work every open ticket in the queue and give me the team report.",
) -> TeamReport:
    """Entry point: Boss runs the queue and delegates to the others."""
    deps = TeamDeps(run_id=uuid.uuid4().hex[:12], chain=["boss"])
    return await run_agent("boss", prompt, deps, usage=RunUsage())
