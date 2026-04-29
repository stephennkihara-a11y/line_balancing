"""
Claude API explanation layer.

Generates a natural-language narrative for a balancing run and answers
free-text "what-if" questions, with prompt caching on the static system
context (so repeated queries against the same run are cheap).
"""
from __future__ import annotations

from typing import Any

from anthropic import Anthropic, APIError

from ..config import get_settings


SYSTEM_PROMPT = """You are an expert industrial engineer specialising in apparel manufacturing line balancing.
You analyse the output of a CP-SAT line-balancing solver and explain it in clear, actionable language to factory IEs and supervisors.

Always:
- be concise (max ~250 words unless asked otherwise)
- highlight bottleneck stations and root causes (skill gap, machine type, SAM imbalance)
- recommend concrete actions: cross-train operator X on op Y, add SNLS machine, split bottleneck op, etc.
- quote efficiency, takt and balance-loss numbers when relevant
- never invent operator names, op codes, or numbers — use only what is in the supplied context
"""


def _client() -> Anthropic | None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    return Anthropic(api_key=settings.anthropic_api_key)


def _build_context(run_summary: dict[str, Any]) -> str:
    lines = [
        f"Style: {run_summary.get('style_code')} ({run_summary.get('style_name')})",
        f"Line: {run_summary.get('line_code')}",
        f"Target output: {run_summary.get('target_output_hour')}/hr",
        f"Working minutes: {run_summary.get('working_minutes')}",
        f"Takt time: {run_summary.get('takt_time'):.3f} min/piece",
        f"Theoretical ops: {run_summary.get('theoretical_ops')}",
        f"Stations used: {run_summary.get('stations_used')}",
        f"Line efficiency: {run_summary.get('line_efficiency')}%",
        f"Balance loss: {run_summary.get('balance_loss')}%",
        f"Bottleneck station: {run_summary.get('bottleneck_station')} "
        f"({run_summary.get('bottleneck_op_code')}) "
        f"@ {run_summary.get('bottleneck_cycle_min'):.3f} min",
        "",
        "Station loads (min):",
    ]
    for s in run_summary.get("station_summary", []):
        lines.append(
            f"  Station {s['station']}: operator={s['operator_name']} "
            f"ops={','.join(s['op_codes'])} machine={s['machine_type']} "
            f"load={s['cycle_time']:.3f} ({s['load_pct']:.1f}%)"
        )
    if run_summary.get("warnings"):
        lines.append("")
        lines.append("Solver warnings:")
        for w in run_summary["warnings"]:
            lines.append(f"  - {w}")
    return "\n".join(lines)


def explain_balance(run_summary: dict[str, Any], question: str | None = None) -> str:
    """Return a Claude-generated narrative.

    Falls back to a deterministic summary if no API key is configured.
    """
    settings = get_settings()
    context = _build_context(run_summary)

    client = _client()
    if client is None:
        return _fallback(run_summary)

    user_msg = question or (
        "Please summarise this line-balance run for a production manager. "
        "Call out the bottleneck, root cause, and 2–3 concrete improvement actions."
    )

    try:
        resp = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=600,
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": user_msg}],
        )
        # Concatenate text blocks
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    except APIError as e:
        return f"[Claude API error: {e}]\n\n{_fallback(run_summary)}"
    except Exception as e:
        return f"[Claude unavailable: {e}]\n\n{_fallback(run_summary)}"


def _fallback(s: dict[str, Any]) -> str:
    eff = s.get("line_efficiency", 0)
    bl = s.get("balance_loss", 0)
    bs = s.get("bottleneck_station")
    bop = s.get("bottleneck_op_code")
    msg = (
        f"Line efficiency {eff}% (balance loss {bl}%). "
        f"Bottleneck is station {bs} running operation {bop}. "
    )
    if eff < 80:
        msg += "Consider splitting the bottleneck op, cross-training a faster operator onto it, "
        msg += "or adding a parallel machine of the same type."
    elif eff < 90:
        msg += "Balance is acceptable but tightening operator skill on the bottleneck op should push efficiency above 90%."
    else:
        msg += "Balance is strong — monitor real-time output and re-balance if it deviates >15%."
    return msg
