from __future__ import annotations

from construction_scene_ready.fault_injection import EXPECTED_RULES
from construction_scene_ready.repair import WHITELIST
from construction_scene_ready.rule_registry import RULE_BY_ID, RULES


def test_rule_registry_is_complete_and_versioned() -> None:
    assert len(RULES) == 32
    assert len(RULE_BY_ID) == 32
    assert [item.rule_id for item in RULES] == [
        f"CSR-SCN-{index:03d}" for index in range(1, 33)
    ]
    versions = {item.rule_id: item.contract_version for item in RULES}
    assert all(
        versions[f"CSR-SCN-{index:03d}"] == "0.2.0" for index in range(1, 31)
    )
    assert versions["CSR-SCN-031"] == "0.3.0"
    assert versions["CSR-SCN-032"] == "0.3.0"
    expected = {
        rule_id
        for rule_ids in EXPECTED_RULES.values()
        for rule_id in rule_ids
    }
    assert expected <= set(RULE_BY_ID)


def test_repair_whitelist_matches_registry_policy() -> None:
    declared_safe = {
        item.rule_id for item in RULES if item.safe_auto_repair
    }
    assert set(WHITELIST) == declared_safe

