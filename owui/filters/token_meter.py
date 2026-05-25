"""
title: Token Meter
author: Ken Enda
version: 1.7.0
required_open_webui_version: 0.5.0
description: |
  Displays conversation-wide context usage rate using real usage data returned from SGLang.

  Display:
      🟢 4.2% [█░░░░░░░] | 11.0k/262k | IN 10.0k / OUT 1.0k

  Aggregation (cumulative per conversation):
      in (IN)   = latest prompt_tokens
                  (the input of the last SGLang call = cumulative input of the entire conversation)
      out (OUT) = cumulative total of all completion_tokens (state-persisted)
      total     = in + out

  - inlet does not reset to 0 (maintains cumulative per conversation)
  - inlet injects stream_options.include_usage=True
  - stream captures usage and updates status each time
  - outlet re-emits the same state as a final confirmation
    (because the stream's final emit can sometimes be lost)

  Important: OWUI shares Filter instances across the entire process (singleton in
  app.state.FUNCTIONS). Storing request-scoped state (current chat_id, event_emitter)
  on self would be overwritten by concurrent requests from other chats/users.
  All handlers receive __metadata__ and __event_emitter__ as arguments, and self only
  holds pure cumulative state (chat_state dict) keyed by chat_id.

changelog:
  1.7.0: Generalized single warn_threshold_pct to warn_levels: list[WarnLevel(pct, message)].
         Each entry holds a pct and injection message as a single pair, allowing any number
         of threshold levels. Default is 2 levels at 50% / 80%, with messages written as
         "behavioral directives for the model" rather than user-facing text (concise response
         directive, suppression of new lengthy tasks, etc.).
         When multiple thresholds are crossed in the same turn, only the highest fires and
         lower ones are marked as done (noise prevention). Each pct resets individually when
         usage falls below it -> re-triggers on next crossing. Empty array disables the feature.
         Additionally added debug_inject_context valve (default True) which injects current
         context usage as a system message every inlet. A temporary line for verifying whether
         the model actually reads system injections (recommend OFF after confirmation).
  1.6.0: 1) Changed _fmt_num to 1024-based (262144 -> "256.0k").
         2) On the first turn where context usage crosses the threshold (default 75%),
            a system message is injected once to inform the model itself of context pressure.
            Injection position is just before the latest user message (preserves upstream
            prefix without breaking prompt cache). Flag resets when usage falls below
            threshold, enabling re-warning next time.
  1.5.0: On inlet only, appends "calculating..." to hint to the user that this is a token
         usage indicator. Replaced by actual numeric display in stream/outlet.
  1.4.0: Fixed session cross-leak during concurrent requests. Since Filter is an OWUI
         singleton (shared via app.state.FUNCTIONS), storing request-scoped values in
         self.current_key / self.event_emitter would emit other chat/user values to
         the wrong WS or update the wrong chat's state in stream().
         Changed all handlers to receive __metadata__ / __event_emitter__ as arguments.
  1.3.1: Fixed key retrieval bug in outlet. The outlet body has a different chat_id
         structure on the response side, resulting in a different key from _chat_key
         that generated an empty state -> overwriting with 0%. Now uses the current_key
         established in inlet. Does not emit if state is empty.
  1.3.0: Changed to gauge notation ([bars]) and IN/OUT labels. Improved visibility
         for clinical environments.
  1.2.0: Switched to cumulative per conversation. Out accumulation keyed by conversation ID.
  1.1.0: Accurate in/out from user perspective
  1.0.0: Real usage
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _fmt_num(n: int) -> str:
    # 1024-based. Displays 262144 (= 256 * 1024) as "256.0k".
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f}M"
    if n >= 1024:
        return f"{n / 1024:.1f}k"
    return str(n)


def _bar(pct: float, length: int = 8) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(length * pct / 100.0))
    return "[" + "█" * filled + "░" * (length - filled) + "]"


def _signal(pct: float) -> str:
    if pct >= 90:
        return "\U0001f534"
    if pct >= 75:
        return "\U0001f7e0"
    if pct >= 50:
        return "\U0001f7e1"
    return "\U0001f7e2"


def _build(
    in_tokens: int,
    out_tokens: int,
    context_size: int,
    bar_length: int,
) -> str:
    total = in_tokens + out_tokens
    pct = (total / context_size * 100.0) if context_size > 0 else 0.0
    sig = _signal(pct)
    bar = _bar(pct, bar_length)
    in_out = f"IN {_fmt_num(in_tokens)} / OUT {_fmt_num(out_tokens)}"
    total_str = f"{_fmt_num(total)}/{_fmt_num(context_size)}"
    return f"{sig} {pct:.1f}% {bar} | {total_str} | {in_out}"


def _build_inlet(
    in_tokens: int,
    out_tokens: int,
    context_size: int,
    bar_length: int,
) -> str:
    # First turn: no values available, so just show "calculating".
    # Subsequent turns: show cumulative from previous turns + append "calculating..."
    #                   to indicate this status is a token usage meter.
    if in_tokens == 0 and out_tokens == 0:
        return "⏳ Calculating token usage..."
    base = _build(in_tokens, out_tokens, context_size, bar_length)
    return f"{base} ... calculating"


def _chat_key(metadata: Optional[dict], user: Optional[dict]) -> Optional[str]:
    """Key to identify the conversation. Uses chat_id if available,
    otherwise falls back to user+session. Returns None if neither available (no-op)."""
    md = metadata or {}
    chat_id = md.get("chat_id")
    if chat_id:
        return f"chat:{chat_id}"
    session_id = md.get("session_id") or ""
    user_id = (user or {}).get("id") or ""
    if session_id or user_id:
        return f"sess:{user_id}:{session_id}"
    return None


async def _emit(
    event_emitter: Optional[Callable[[Any], Awaitable[None]]],
    description: str,
) -> None:
    if event_emitter is None:
        return
    try:
        await event_emitter(
            {
                "type": "status",
                "data": {"description": description, "done": True},
            }
        )
    except Exception as e:
        logger.error(f"[TokenMeter] emit FAIL: {e!r}")


class WarnLevel(BaseModel):
    pct: float = Field(description="Threshold (%). Message is injected once on the first turn this % is exceeded")
    message: str = Field(description="System message body to inject")


_DEFAULT_LEVELS: list[WarnLevel] = [
    WarnLevel(
        pct=50.0,
        message=(
            "From now on, prioritize conciseness in responses. Avoid lengthy quotations "
            "and repetition of previous statements. If the user submits a large new document, "
            "suggest summarizing existing context before incorporating it."
        ),
    ),
    WarnLevel(
        pct=80.0,
        message=(
            "Approaching context limit. Do not start new lengthy tasks. In the current turn, "
            "explicitly state conclusions, state, and code diffs that should be preserved. "
            "If continued work is needed, prompt the user to split into a new chat."
        ),
    ),
]


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=100, description="Run after other filters")
        context_size: int = Field(
            default=262144,
            description="Context window for this model (Kimi K2.6 = 262144)",
        )
        bar_length: int = Field(default=8, description="Number of bar segments")
        warn_levels: list[WarnLevel] = Field(
            default_factory=lambda: list(_DEFAULT_LEVELS),
            description=(
                "Pairs of context usage threshold percentages and messages. "
                "Evaluated in ascending order; when multiple are crossed in the same turn, "
                "only the highest fires (lower ones marked as done). "
                "Each pct resets individually when usage falls below it, enabling re-warning "
                "on next crossing. Empty array disables the feature."
            ),
        )
        debug_inject_context: bool = Field(
            default=True,
            description=(
                "Debug: Inject current context usage as a system message every inlet. "
                "For verifying whether the model reads system messages; turn OFF when no longer needed."
            ),
        )

    def __init__(self):
        self.file_handler = False
        self.valves = self.Valves()
        # Cumulative state per conversation (chat_id -> state).
        # Since this is an OWUI singleton shared across all users/chats,
        # the key is chat_id so reading/writing here does not contaminate other chats.
        # state: {"in": int, "out": int, "prev_prompt": int|None, "prev_completion": int|None,
        #         "emitter": Callable|None, "warned": set[float]}
        # emitter is kept per key so stream() (sync) can access the latest emit target.
        # warned is a set of fired pct values to ensure single-fire system injection.
        self.chat_state: dict[str, dict] = {}
        logger.error("[TokenMeter] __init__ v1.7.0")

    def _get_state(self, key: str) -> dict:
        if key not in self.chat_state:
            self.chat_state[key] = {
                "in": 0,
                "out": 0,
                "prev_prompt": None,
                "prev_completion": None,
                "emitter": None,
                "warned": set(),
            }
        return self.chat_state[key]

    def _maybe_inject_warning(self, body: dict, state: dict) -> None:
        levels = [lvl for lvl in (self.valves.warn_levels or []) if lvl.pct > 0]
        context_size = self.valves.context_size
        if not levels or context_size <= 0:
            return
        total = state["in"] + state["out"]
        pct = total / context_size * 100.0

        # Remove thresholds that are no longer exceeded from warned, enabling re-warning
        state["warned"] = {t for t in state["warned"] if pct >= t}

        # Sort ascending, fire only the highest "exceeded & not yet warned"
        sorted_levels = sorted(levels, key=lambda lvl: lvl.pct)
        fired: Optional[WarnLevel] = None
        for lvl in reversed(sorted_levels):
            if pct >= lvl.pct and lvl.pct not in state["warned"]:
                fired = lvl
                break
        if fired is None:
            return

        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            return

        remaining = max(0, context_size - total)
        # Written as a directive for the model with explicit marker and context metadata.
        # Not user-facing text, but behavioral guidelines the model should follow.
        warning = (
            f"[System directive] Context usage {pct:.1f}% "
            f"(threshold {fired.pct:.0f}% exceeded, approx {_fmt_num(remaining)} tokens remaining). "
            f"{fired.message}"
        )

        # Insert just before the latest user message. Does not break upstream prefix so prompt cache is preserved.
        insert_pos = len(messages) - 1
        if messages[insert_pos].get("role") != "user":
            insert_pos = len(messages)
        messages.insert(insert_pos, {"role": "system", "content": warning})
        body["messages"] = messages

        # When highest level fires, lower levels in the same turn are considered covered (no double injection)
        state["warned"].update(
            {lvl.pct for lvl in sorted_levels if lvl.pct <= fired.pct}
        )
        logger.error(
            f"[TokenMeter] WARN injected pct={pct:.1f} fired_threshold={fired.pct:.0f}"
        )

    def _inject_context_debug(self, body: dict, state: dict) -> None:
        """Debug path that injects current token usage as a system message every inlet.
        Separate from threshold warning; always injected for verifying whether the model
        actually reads system injections. No-op if Valves.debug_inject_context is False."""
        if not self.valves.debug_inject_context:
            return
        context_size = self.valves.context_size
        if context_size <= 0:
            return
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            return

        total = state["in"] + state["out"]
        pct = total / context_size * 100.0
        msg = (
            f"[context-status] in={state['in']} out={state['out']} "
            f"total={total}/{context_size} ({pct:.2f}%) "
            f"[human: in={_fmt_num(state['in'])} out={_fmt_num(state['out'])} "
            f"total={_fmt_num(total)}/{_fmt_num(context_size)}]"
        )
        insert_pos = len(messages) - 1
        if messages[insert_pos].get("role") != "user":
            insert_pos = len(messages)
        messages.insert(insert_pos, {"role": "system", "content": msg})
        body["messages"] = messages
        logger.error(f"[TokenMeter] context-status injected: {msg}")

    # --------------------------------------------------------
    # inlet
    # --------------------------------------------------------
    async def inlet(
        self,
        body: dict,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]] = None,
        __metadata__: Optional[dict] = None,
        __user__: Optional[dict] = None,
    ) -> dict:
        # Have SGLang return usage (always, regardless of state)
        stream_options = body.get("stream_options") or {}
        if not isinstance(stream_options, dict):
            stream_options = {}
        stream_options["include_usage"] = True
        body["stream_options"] = stream_options

        key = _chat_key(__metadata__, __user__)
        if key is None:
            return body

        state = self._get_state(key)

        # Reset prev for next-turn delta calculation
        state["prev_prompt"] = None
        state["prev_completion"] = None

        # Store emitter per chat key for later reference from stream() (sync)
        state["emitter"] = __event_emitter__

        # Inject system message if threshold exceeded (once only)
        self._maybe_inject_warning(body, state)

        # Debug: inject current context usage as system message every turn (can be turned OFF via valve)
        self._inject_context_debug(body, state)

        description = _build_inlet(
            state["in"],
            state["out"],
            self.valves.context_size,
            self.valves.bar_length,
        )
        await _emit(__event_emitter__, description)
        logger.error(
            f"[TokenMeter] inlet key={key} in={state['in']} out={state['out']}"
        )
        return body

    # --------------------------------------------------------
    # stream
    # --------------------------------------------------------
    def stream(
        self,
        event: dict,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]] = None,
        __metadata__: Optional[dict] = None,
        __user__: Optional[dict] = None,
    ) -> dict:
        key = _chat_key(__metadata__, __user__)
        if key is None:
            return event

        usage = None
        try:
            usage = event.get("usage")
            if usage is None:
                choices = event.get("choices") or []
                if choices and isinstance(choices[0], dict):
                    usage = choices[0].get("usage")
        except Exception as e:
            logger.error(f"[TokenMeter] stream exception: {e!r}")
            return event

        if not isinstance(usage, dict):
            return event

        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        if not isinstance(prompt, int) or not isinstance(completion, int):
            return event

        state = self._get_state(key)

        # in: The latest prompt_tokens directly represents "cumulative conversation input"
        # However, the first prompt includes all out from turns up to N-1, so
        # "true user input in" = prompt - cumulative out.
        # state["out"] is the cumulative from previous turns; current turn's out is added on top.
        if state["prev_prompt"] is None:
            # First usage in this turn
            new_in = prompt - state["out"]
            if new_in < state["in"]:
                # Can decrease due to history trimming etc.; respect previous value
                new_in = state["in"]
            state["in"] = new_in
        else:
            # 2nd+ usage within the same turn (tool calls): add the increment from tool results
            in_delta = prompt - (state["prev_prompt"] + (state["prev_completion"] or 0))
            if in_delta > 0:
                state["in"] += in_delta

        # out: accumulate completion
        state["out"] += completion

        state["prev_prompt"] = prompt
        state["prev_completion"] = completion

        description = _build(
            state["in"],
            state["out"],
            self.valves.context_size,
            self.valves.bar_length,
        )

        # stream() is sync, so emit is dispatched as a background task.
        # Priority: emitter passed at invocation > emitter saved in inlet
        emitter = __event_emitter__ or state.get("emitter")
        if emitter is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(_emit(emitter, description))
            except RuntimeError:
                pass

        logger.error(
            f"[TokenMeter] key={key} prompt={prompt} completion={completion} "
            f"-> in={state['in']} out={state['out']}"
        )
        return event

    # --------------------------------------------------------
    # outlet (final confirmation)
    # --------------------------------------------------------
    async def outlet(
        self,
        body: dict,
        __event_emitter__: Optional[Callable[[Any], Awaitable[None]]] = None,
        __metadata__: Optional[dict] = None,
        __user__: Optional[dict] = None,
    ) -> dict:
        key = _chat_key(__metadata__, __user__)
        if key is None:
            return body
        state = self.chat_state.get(key)
        if state is None:
            # If inlet was not hit (state is empty), do not emit a final confirmation
            return body

        description = _build(
            state["in"],
            state["out"],
            self.valves.context_size,
            self.valves.bar_length,
        )
        await _emit(__event_emitter__, description)
        return body
