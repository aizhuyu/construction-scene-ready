"""Language-model repair methods B2/B3 (frozen prompts and decoding).

B2 ``unconstrained-agent``: receives the faulty scene JSON and a
natural-language problem report (validator messages without rule authority),
and may rewrite the scene freely.  Its final scene is scored by independent
deterministic revalidation and equivalence against the pristine scene; its own
claims are never ground truth (docs/baseline-protocol.md).

B3 ``validator-grounded-agent``: receives typed rule findings and the approved
repair-tool registry, and selects which findings to repair with which tool.
The harness executes the selected whitelisted tools deterministically
(repair.py) and revalidates independently.

Frozen serving configuration: a self-hosted AWQ-quantized instruction model
behind an OpenAI-compatible endpoint.  Model id, weights path, decoding
parameters, and prompts are constants of this module; changing any of them
requires a new run id in docs/experiment-registry.csv.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from openai import OpenAI

from .detection_repair import (
    REPAIR_ESCALATED,
    REPAIR_FAILED,
    REPAIR_INCORRECT,
    REPAIR_VALID,
    _scene_equivalent,
)
from .fault_injection import inject_fault
from .repair import WHITELIST
from .validator import SceneValidator

# ---- frozen serving configuration (run B-CPU-LLM-0001) ----
MODEL_ID = "csr-qwen25-coder-14b-awq"
MODEL_WEIGHTS = "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ @ ~/llm_models/qwen25-coder-14b-instruct-awq"
ENDPOINT = "http://127.0.0.1:8399/v1"
TEMPERATURE = 0.7
TOP_P = 0.8
MAX_TOKENS = 4096
SEEDS = (0, 1, 2, 3, 4)

B2_SYSTEM = """You are a repair agent for construction scene models in JSON.

You will receive:
1. A scene JSON document describing a construction assembly scene.
2. A natural-language report of problems detected in that scene.

Rewrite the scene so that every reported problem is resolved. You may change
any part of the JSON. Preserve everything that is not problematic. Do not
invent physical parameters (mass, friction, tolerance) that the report does
not give you; if a required value cannot be determined from the input, reply
with ESCALATE instead of guessing.

Reply with EXACTLY one of:
- the complete corrected scene JSON inside a single ```json code fence, or
- the line "ESCALATE: <reason>"."""

B3_SYSTEM = """You are a repair-planning agent for construction scene models.

You will receive:
1. A scene JSON document describing a construction assembly scene.
2. Typed rule findings (rule_id, path, message) detected in that scene.
3. The approved repair-tool registry mapping rule_ids to repair tools.

Select the findings that should be repaired. Each selected finding is
repaired deterministically by its registered tool using trusted engineering
evidence; you cannot and must not supply repair values yourself. If a finding
has no registered tool, or its repair would require values not present in
trusted evidence, mark it as escalate.

Reply with EXACTLY one JSON object inside a single ```json code fence:
{"repair": [{"rule_id": "...", "path": "..."}, ...],
 "escalate": [{"rule_id": "...", "reason": "..."}]}"""

_JSON_FENCE = re.compile(r"```json\s*(.*?)```", re.DOTALL)


def _client() -> OpenAI:
    return OpenAI(base_url=ENDPOINT, api_key="frozen-local-endpoint")


def _chat(client: OpenAI, system: str, user: str, seed: int) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=MAX_TOKENS,
        seed=seed,
    )
    choice = response.choices[0]
    return {
        "content": choice.message.content or "",
        "finish_reason": choice.finish_reason,
        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
        "completion_tokens": response.usage.completion_tokens if response.usage else None,
    }


def _extract_json(text: str) -> Any:
    match = _JSON_FENCE.search(text)
    payload = match.group(1) if match else text
    return json.loads(payload)


def prose_report(issues: tuple) -> str:
    """Natural-language problem report for B2: messages and paths, no rule ids."""
    lines = [
        f"- At {issue.path}: {issue.message}" for issue in issues
    ]
    return "Problems detected in this scene:\n" + "\n".join(lines)


def tool_registry_doc() -> str:
    """Human-readable frozen registry for the B3 prompt."""
    lines = [
        f"- {rule_id}: {tool_name}" for rule_id, (tool_name, _fn) in sorted(WHITELIST.items())
    ]
    return "Approved repair-tool registry:\n" + "\n".join(lines)


def run_b2_case(
    scene: dict[str, Any], fault_id: str, seed: int, *, client: OpenAI | None = None,
) -> dict[str, Any]:
    """One unconstrained-agent episode; returns the episode record."""
    client = client or _client()
    validator = SceneValidator()
    faulty = inject_fault(scene, fault_id)
    expected = set(faulty["fault_ground_truth"]["expected_rules"])
    before = validator.validate(faulty)

    user = (
        "Scene JSON:\n```json\n" + json.dumps(faulty, indent=1) + "\n```\n\n"
        + prose_report(before.issues)
    )
    reply = _chat(client, B2_SYSTEM, user, seed)
    record: dict[str, Any] = {
        "method": "unconstrained-agent", "seed": seed, "llm": reply,
        "prompt_version": "B2_SYSTEM@1",
    }
    content = reply["content"]
    if content.strip().upper().startswith("ESCALATE"):
        record.update(outcome=REPAIR_ESCALATED, parse_error=False)
        return record
    try:
        final_scene = _extract_json(content)
        if not isinstance(final_scene, dict):
            raise ValueError("agent reply is not a JSON object")
    except Exception as exc:  # unparseable reply = failed repair
        record.update(outcome=REPAIR_FAILED, parse_error=True, error=str(exc))
        return record

    after = validator.validate(final_scene)
    if not after.passed:
        record.update(outcome=REPAIR_FAILED, parse_error=False,
                      residual_rules=sorted({i.rule_id for i in after.issues}))
    elif _scene_equivalent(final_scene, scene):
        record.update(outcome=REPAIR_VALID, parse_error=False)
    else:
        record.update(outcome=REPAIR_INCORRECT, parse_error=False)
    record["resolved_rules"] = sorted(expected - {i.rule_id for i in after.issues})
    return record


def run_b3_case(
    scene: dict[str, Any], fault_id: str, seed: int, *, client: OpenAI | None = None,
    typed: bool = True,
) -> dict[str, Any]:
    """One validator-grounded-agent episode; returns the episode record.

    ``typed=False`` is ablation A5: findings are rendered as prose (no rule
    ids); the agent must map the prose to registry rule_ids itself.
    """
    client = client or _client()
    validator = SceneValidator()
    faulty = inject_fault(scene, fault_id)
    before = validator.validate(faulty)

    findings = [issue.to_dict() for issue in before.issues]
    if typed:
        findings_doc = ("Typed rule findings:\n```json\n"
                        + json.dumps(findings, indent=1) + "\n```\n\n")
    else:
        findings_doc = prose_report(before.issues) + "\n\n"
    user = (
        "Scene JSON:\n```json\n" + json.dumps(faulty, indent=1) + "\n```\n\n"
        + findings_doc
        + tool_registry_doc()
    )
    reply = _chat(client, B3_SYSTEM, user, seed)
    record: dict[str, Any] = {
        "method": "validator-grounded-agent" if typed else "ablation-prose-diagnostics",
        "seed": seed, "llm": reply,
        "prompt_version": "B3_SYSTEM@1" if typed else "B3_SYSTEM@1+prose",
    }
    try:
        plan = _extract_json(reply["content"])
        selections = plan.get("repair", [])
        escalations = plan.get("escalate", [])
        if not isinstance(selections, list) or not isinstance(escalations, list):
            raise ValueError("plan fields must be lists")
    except Exception as exc:
        record.update(outcome=REPAIR_FAILED, parse_error=True, error=str(exc))
        return record

    candidate = copy.deepcopy(faulty)
    events: list[dict[str, Any]] = []
    blocked: list[str] = [str(item.get("rule_id")) for item in escalations]
    by_path = {(issue.rule_id, issue.path): issue for issue in before.issues}
    for selection in selections:
        key = (str(selection.get("rule_id")), str(selection.get("path")))
        issue = by_path.get(key)
        tool_entry = WHITELIST.get(str(selection.get("rule_id")))
        if issue is None or tool_entry is None:
            blocked.append(str(selection.get("rule_id")))
            continue
        tool_name, function = tool_entry
        changed = function(candidate, scene, issue)
        events.append({"rule_id": issue.rule_id, "tool": tool_name,
                       "changed_paths": changed})
    after = validator.validate(candidate)
    record["events"] = events
    record["escalated_rule_ids"] = sorted(set(blocked))
    if blocked:
        record.update(outcome=REPAIR_ESCALATED, parse_error=False)
    elif not after.passed:
        record.update(outcome=REPAIR_FAILED, parse_error=False,
                      residual_rules=sorted({i.rule_id for i in after.issues}))
    elif _scene_equivalent(candidate, scene):
        record.update(outcome=REPAIR_VALID, parse_error=False)
    else:
        record.update(outcome=REPAIR_INCORRECT, parse_error=False)
    return record
