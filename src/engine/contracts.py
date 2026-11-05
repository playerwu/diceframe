"""核心运行时协议的渐进式类型定义。

这些结构仍按原 JSON 字段序列化，TypedDict 只为编辑器和静态检查提供
跨模块字段契约，不改变旧存档、HTTP 或 Bot 消费格式。
"""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class PlayerData(TypedDict, total=False):
    user_id: str
    character_name: str
    character_sheet: dict[str, Any]
    # 谁在玩这个角色（human / ai / unclaimed），见 src.engine.player_control。
    # 它与 character_sheet 同级：控制器可以换，角色本身不换。
    control: dict[str, Any]


class ActionRecord(TypedDict, total=False):
    user_id: str
    text: str
    timestamp: str
    selected_attribute: str
    selected_skill: str
    target_text: str
    source: str
    dice_pending: bool
    dice_system: str
    dice_roll_source: str
    dice_value: int | None
    dice_rolls: list[int]
    check_request: dict[str, Any] | None
    combat_outcome: dict[str, Any]
    revision_count: int
    # 调用方自带的机器可读标记（例如服务器 AI 行动的 source / control_revision /
    # generated_for_round）。只用于去重与调试，绝不是规则权威。
    metadata: dict[str, Any]


class CheckRequest(TypedDict, total=False):
    check_id: str
    required: bool
    actor_uid: str
    actor_name: str
    dice_system: Literal["d20", "d100"]
    label: str
    intent: str
    skill: str
    attribute: str
    target: int
    circumstance_modifier: int
    advantage_mode: Literal["", "advantage", "disadvantage"]
    advantage_note: str | None
    dc_reason: str | None
    advantage_reason: str | None
    modifier_reason: str | None
    planner_notes: list[str]
    planner_dropped: dict[str, int | str]
    kind: Literal["check", "save", "attack"]
    opponent: str
    opponent_name: str
    opponent_roll: int
    opponent_modifier: int
    opponent_total: int
    assist: list[str]
    planner_source: str


class PercentileDice(TypedDict):
    units: int
    tens: list[int]
    candidates: list[int]
    taken_index: int
    bonus_dice: int
    penalty_dice: int


class CheckResult(TypedDict, total=False):
    attribute_key: str
    push: dict[str, Any]
    dice_mechanic: str
    percentile_dice: PercentileDice
    check_id: str
    label: str
    actor_uid: str
    actor_name: str
    delegate_name: str
    dice: str
    attribute: str | None
    skill: str
    roll: int
    rolls: list[int]
    threshold: int
    hard_threshold: int
    extreme_threshold: int
    modifier: int
    modifier_breakdown: str | None
    total: int
    dc: int
    difficulty: str
    kind: Literal["check", "save", "attack"]
    opponent: str
    opponent_name: str
    opponent_roll: int
    opponent_modifier: int
    opponent_total: int
    assist: list[str]
    planner_source: str
    verdict: str
    advantage_mode: str
    advantage_note: str | None
    dc_reason: str | None
    advantage_reason: str | None
    modifier_reason: str | None
    planner_notes: list[str]
    luck_spend_available: bool
    luck_cost: int | None
    luck_decision: Literal["pending", "spent", "declined"]
    is_critical: bool
    is_fumble: bool


class StoryRecap(TypedDict, total=False):
    id: str
    text: str
    from_round: int
    to_round: int
    created_at: str


class TableTalkExchange(TypedDict, total=False):
    """A public, read-only player/GM exchange outside the turn log."""

    id: str
    actor_uid: str
    actor_name: str
    question: str
    answer: str
    round: int
    created_at: str
    visibility: Literal["party"]


class RoundLogEntry(TypedDict, total=False):
    round: int
    actions: list[ActionRecord]
    gm_response: str
    story: NotRequired[dict[str, Any]]
    swipe_stories: NotRequired[list[dict[str, Any] | None]]
    state_changes: list[str]
    check_results: list[CheckResult]
    round_start_snapshot: dict[str, Any]
    combat_extension_round_start: dict[str, Any]
    pre_state_snapshot: dict[str, Any]
    pre_combat_extension_snapshot: dict[str, Any]
    pre_world_state: dict[str, Any]
    swipes: list[str]
    current_swipe: int
    timestamp: str
    tags_summary: NotRequired[dict[str, Any]]
    story_recaps: NotRequired[list[StoryRecap]]
    scene_image: NotRequired[dict[str, Any]]


TokenBudgetBump = TypedDict(
    "TokenBudgetBump",
    {"kind": str, "from": int, "to": int},
)
