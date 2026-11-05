"""Exploration execution for class-feature capabilities (the Second Wind family).

Out of combat, a heal capability that needs no hostile target is settled
end-to-end by the exploration engine: the canonical class resource is spent,
the heal dice are rolled server-side, and the narrative layer is never asked
to invent numbers. Capabilities that need an enemy actor or resolve anything
other than heals are not offered and cannot be forged into the payload.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.engine.game_instance import GameInstance
from src.engine.modules import ruleset_runtime
from src.rulesets.dnd2024.exploration import Dnd2024ExplorationEngine
from src.rulesets.dnd2024.runtime import Dnd2024Runtime

from tests.rulesets.test_dnd2024_combat import _character


class FixedRng:
    """Deterministic dice: every roll lands on ``value``."""

    def __init__(self, value: int) -> None:
        self.value = value

    def randint(self, minimum: int, maximum: int) -> int:
        assert minimum <= self.value <= maximum
        return self.value


def _instance(
    preset_id: str = "stalwart_guardian",
    *,
    hp: int | None = None,
    charges: int | None = None,
    conditions: dict[str, Any] | None = None,
) -> tuple[Dnd2024Runtime, GameInstance, Dnd2024ExplorationEngine]:
    runtime = Dnd2024Runtime()
    instance = GameInstance(
        game_key=("test", "dnd2024-explore-features", "bot"),
        rule_id="dnd2024_srd", gm_uid="gm", language="en",
    )
    sheet = _character(runtime, preset_id, "Arden")
    canonical = sheet["ruleset_character"]
    if hp is not None:
        canonical["resources"]["hp"] = hp
    if charges is not None:
        canonical["resources"]["class"]["second_wind"]["current"] = charges
    if conditions is not None:
        canonical["conditions"] = conditions
    instance.players["gm"] = {"character_name": "Arden", "character_sheet": sheet}
    assert instance.bind_ruleset_runtime(sheet["rule_binding"])
    engine = Dnd2024ExplorationEngine(runtime.load_bundle("en"), locale="en")
    return runtime, instance, engine


def _version(instance: GameInstance) -> int:
    return int(ruleset_runtime.state(instance).get("version", 0) or 0)


def _canonical(instance: GameInstance) -> dict[str, Any]:
    return instance.players["gm"]["character_sheet"]["ruleset_character"]


def _feature_action(
    engine: Dnd2024ExplorationEngine, instance: GameInstance,
) -> dict[str, Any] | None:
    for action in engine.available_intents(instance, "player:gm"):
        if action["type"] == "exploration.use_class_feature":
            return action
    return None


def _use(
    engine: Dnd2024ExplorationEngine, instance: GameInstance, rng: Any,
    *, intent_id: str = "exp-feature", capability_id: str = "second_wind",
    submitted_by: str = "gm", expected_version: int | None = None,
) -> dict[str, Any]:
    return engine.resolve_intent(instance, {
        "intent_id": intent_id,
        "type": "exploration.use_class_feature",
        "expected_version": (
            _version(instance) if expected_version is None else expected_version
        ),
        "submitted_by": submitted_by,
        "actor_id": "player:gm",
        "capability_id": capability_id,
    }, rng)


def test_second_wind_is_offered_out_of_combat_with_its_resource_cost():
    _, instance, engine = _instance(hp=4)
    action = _feature_action(engine, instance)
    assert action is not None
    capability = next(
        item for item in action["capabilities"]
        if item["capability_id"] == "second_wind"
    )
    assert capability["available"] is True
    assert capability["requires_target"] is False
    resource_costs = [
        cost for cost in capability["costs"] if cost["kind"] == "resource"
    ]
    assert len(resource_costs) == 1
    assert resource_costs[0]["name"] == "Second Wind"
    assert resource_costs[0]["amount"] == 1
    assert resource_costs[0]["current"] == 2
    assert resource_costs[0]["maximum"] == 2
    # The action-economy price is displayed but never spent in exploration.
    action_costs = [
        cost for cost in capability["costs"] if cost["kind"] != "resource"
    ]
    assert [cost["kind"] for cost in action_costs] == ["bonus_action"]


def test_second_wind_heals_and_spends_the_charge():
    _, instance, engine = _instance(hp=4)
    result = _use(engine, instance, FixedRng(10))
    assert result["ok"] is True
    applied = engine.apply_batch(instance, result["event_batch"])
    assert applied["applied"] is True
    canonical = _canonical(instance)
    # 1d10 (fixed 10) + 1 fighter level, clamped at max HP 12.
    assert canonical["resources"]["hp"] == 12
    assert canonical["resources"]["class"]["second_wind"]["current"] == 1
    assert _version(instance) == 1
    heal_event = next(
        event for event in result["events"]
        if event["type"] == "resource.changed"
    )
    assert heal_event["healing"] is True
    assert heal_event["rolls"] == [10]
    assert heal_event["hp_after"] == 12
    spend_events = [
        event for event in result["events"]
        if event["type"] == "dnd2024.class_resource.spent"
    ]
    assert spend_events == [{
        "type": "dnd2024.class_resource.spent", "actor_id": "player:gm",
        "resource_id": "second_wind", "amount": 1,
    }]


def test_second_wind_replay_is_idempotent():
    _, instance, engine = _instance(hp=4)
    result = _use(engine, instance, FixedRng(10))
    engine.apply_batch(instance, result["event_batch"])
    replay = engine.apply_batch(instance, result["event_batch"])
    assert replay["duplicate"] is True
    assert replay["applied"] is False
    canonical = _canonical(instance)
    assert canonical["resources"]["class"]["second_wind"]["current"] == 1
    assert canonical["resources"]["hp"] == 12


def test_third_second_wind_is_rejected_and_changes_nothing():
    _, instance, engine = _instance(hp=4)
    first = _use(engine, instance, FixedRng(6), intent_id="exp-first")
    assert first["ok"] is True
    engine.apply_batch(instance, first["event_batch"])
    second = _use(engine, instance, FixedRng(6), intent_id="exp-second")
    assert second["ok"] is True
    engine.apply_batch(instance, second["event_batch"])
    # Both charges spent: not offered, and a forged submission is rejected
    # without touching canonical state.
    assert _feature_action(engine, instance) is None
    before = dict(_canonical(instance)["resources"])
    result = _use(engine, instance, FixedRng(6), intent_id="exp-third")
    assert result["ok"] is False
    assert _canonical(instance)["resources"] == before


def test_combat_active_hides_and_rejects_class_features():
    _, instance, engine = _instance(hp=4)
    state = ruleset_runtime.state(instance)
    state.setdefault("combat", {"status": "none"})["status"] = "active"
    assert _feature_action(engine, instance) is None
    result = _use(engine, instance, FixedRng(10))
    assert result["ok"] is False
    assert _canonical(instance)["resources"]["class"]["second_wind"]["current"] == 2


@pytest.mark.parametrize(
    "conditions",
    [
        {"dead": {"source": "death_saves"}},
        {"unconscious": {"source": "test"}},
    ],
)
def test_ineligible_actors_cannot_use_class_features(conditions):
    _, instance, engine = _instance(hp=4, conditions=conditions)
    assert _feature_action(engine, instance) is None
    result = _use(engine, instance, FixedRng(10))
    assert result["ok"] is False


def test_zero_hp_actor_is_not_eligible():
    _, instance, engine = _instance(hp=0)
    assert engine.available_intents(instance, "player:gm") == []


def test_forged_submitter_is_rejected():
    _, instance, engine = _instance(hp=4)
    result = _use(engine, instance, FixedRng(10), submitted_by="someone-else")
    assert result["ok"] is False
    assert _canonical(instance)["resources"]["class"]["second_wind"]["current"] == 2


def test_forged_capability_id_is_rejected():
    _, instance, engine = _instance(hp=4)
    # "rage" exists in the catalog but belongs to the barbarian; the fighter
    # never owns it, and non-heal capabilities are never valid here anyway.
    result = _use(engine, instance, FixedRng(10), capability_id="rage")
    assert result["ok"] is False
    result = _use(engine, instance, FixedRng(10), capability_id="action_surge")
    assert result["ok"] is False
    assert _canonical(instance)["resources"]["class"]["second_wind"]["current"] == 2


def test_non_heal_capabilities_are_not_projected_for_other_classes():
    # A barbarian owns rage (a condition action, not a heal): it must not be
    # offered out of combat, and no feature intent should appear at all.
    _, instance, engine = _instance("relentless_vanguard")
    assert _feature_action(engine, instance) is None
    result = engine.resolve_intent(instance, {
        "intent_id": "exp-forge", "type": "exploration.use_class_feature",
        "expected_version": _version(instance), "submitted_by": "gm",
        "actor_id": "player:gm", "capability_id": "rage",
    }, FixedRng(10))
    assert result["ok"] is False


def test_cannot_regain_hp_blocks_the_heal_but_still_spends_the_charge():
    _, instance, engine = _instance(hp=4, conditions={"cannot_regain_hp": {}})
    result = _use(engine, instance, FixedRng(10))
    assert result["ok"] is True
    engine.apply_batch(instance, result["event_batch"])
    canonical = _canonical(instance)
    assert canonical["resources"]["hp"] == 4
    assert canonical["resources"]["class"]["second_wind"]["current"] == 1
    heal_event = next(
        event for event in result["events"]
        if event["type"] == "resource.changed"
    )
    assert heal_event["delta"] == 0
    assert heal_event["blocked_by"] == "cannot_regain_hp"


def test_expected_version_conflict_is_rejected():
    _, instance, engine = _instance(hp=4)
    result = _use(engine, instance, FixedRng(10), expected_version=99)
    assert result["ok"] is False
    assert _canonical(instance)["resources"]["class"]["second_wind"]["current"] == 2
