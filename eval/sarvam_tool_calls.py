"""Opt-in live routing evaluation. Never classify mock responses as model accuracy."""

import argparse
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "api"))
from ai import sarvam_chat
from billing.agent import execute_call

parser = argparse.ArgumentParser()
parser.add_argument(
    "--live", action="store_true", help="Explicitly allow billed Sarvam requests"
)
parser.add_argument("--limit", type=int, default=3, choices=range(1, 11))
args = parser.parse_args()
if not args.live or not sarvam_chat.enabled():
    print(
        json.dumps(
            {
                "status": "NOT_RUN",
                "reason": "Requires --live, SARVAM_CHAT_ENABLED=true and a server-side key",
                "model_accuracy": None,
            }
        )
    )
    raise SystemExit(2)
cases = json.loads((root / "eval/sarvam_tool_cases.json").read_text())[: args.limit]
rows = []
for case in cases:
    call, trace = sarvam_chat.route(case["text"], case["merchant"], "day")
    failed = any(t["status"] == "rejected" for t in trace)
    chosen = call.tool if call else "clarify"
    matches = chosen == case["tool"] and not failed
    if call:
        matches = matches and all(
            call.model_dump()["replace" if k == "product" else k] == v
            for k, v in case["arguments"].items()
        )
    try:
        result = execute_call(case["merchant"], call, "Sarvam live evaluation")
        grounded = bool(result.get("guard_passed", result["tool"] == "clarify"))
    except ValueError:
        grounded = False
    rows.append(
        {
            "expected_tool": case["tool"],
            "chosen_tool": chosen,
            "arguments_match": matches,
            "execution_guard_passed": grounded,
            "trace": trace,
        }
    )
    if failed:
        # Stop on provider/contract failure rather than consuming the rest of the credit budget.
        break
print(
    json.dumps(
        {
            "status": "LIVE_CHECK",
            "case_count": len(rows),
            "passed": sum(
                r["arguments_match"] and r["execution_guard_passed"] for r in rows
            ),
            "cases": rows,
        },
        ensure_ascii=False,
        indent=2,
    )
)
