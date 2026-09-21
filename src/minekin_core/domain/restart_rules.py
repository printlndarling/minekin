# ruff: noqa: RUF001
"""What a restart keeps, and what must happen before the Kin acts on it again.

The persistence contract's principle is three clauses — memory is continuous,
reality is re-verified, actions are not resumed — and its table is what each of
them means for each kind of thing a Kin has. This module is that table, plus the
rule stated just after it:

  "Remembering that I was at the front door last time" and "confirming I am at the
  front door now" are two different things. The startup prompt may say "I remember
  repairing the roof", but until the client has reconnected and seen the inventory
  and the scene, it may not keep placing blocks.

That sentence is a rule about *acting*, and it is the one thing here that is not
already true by construction. The invalidated rows are: input leases are not
persisted at all (`domain/recovery.py` says so where it decides what may be
replayed), the arbiter starts with no lease, and nothing replays a GUI handle or an
entity token across a restart. What no code holds yet is the difference between a
fact that is *remembered* and a fact that has been *re-established* — which is why
`LAST_KNOWN_STATE` requires an observation and `INPUT_CONTROL` requires a lease to
be taken again rather than one to be remembered.

The classification is the contract's, not this module's invention, and it is
deliberately not a name-based check on the ledger: recording *that* a lease was
granted is evidence, and evidence is what a ledger is for. What must not survive is
the lease as a *live capability*, which is a different question from whether its id
may be written down.

The table's row labels are quoted from the contract, punctuation included, so that
reading the two side by side is a comparison rather than a paraphrase — which is
what the file-level `noqa` below is for.
"""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class Durability(StrEnum):
    """What a restart does to one kind of thing."""

    #: Kept as it is: who I am, what I know, what I lived through.
    KEPT = "KEPT"
    #: Kept, and re-judged against whatever the world looks like now. A restart is
    #: not a pardon: relationships come back and then get re-evaluated.
    KEPT_AND_REEVALUATED = "KEPT_AND_REEVALUATED"
    #: Kept as an intention, with its preconditions to be checked before it is acted
    #: on — remembering what I meant to do is not permission to do it.
    KEPT_AND_REVERIFIED = "KEPT_AND_REVERIFIED"
    #: Not kept and not zeroed: worked out again from how long it has been. A mood is
    #: neither frozen at the moment of the crash nor reset to calm.
    RECOMPUTED = "RECOMPUTED"
    #: Kept as a *memory* of what was true, and superseded by observation.
    HISTORICAL_ONLY = "HISTORICAL_ONLY"
    #: Must not survive: taking it again is the only way to have it.
    INVALIDATED = "INVALIDATED"
    #: Answers to questions that were in flight. Late results default to expired,
    #: because a result that arrives after a restart can hijack the new session.
    EXPIRED = "EXPIRED"


class ResumptionPrecondition(StrEnum):
    """What has to be true again before a remembered thing may be acted on."""

    #: Nothing: it is the Kin itself, or knowledge, and neither goes stale.
    NONE = "NONE"
    #: The relationship is judged again against evidence, which is what stops a
    #: restart from laundering one.
    REEVALUATED = "REEVALUATED"
    #: The goal's own preconditions hold again.
    PRECONDITIONS_REVERIFIED = "PRECONDITIONS_REVERIFIED"
    #: The client has seen the world again — the rule about not placing blocks.
    WORLD_RE_OBSERVED = "WORLD_RE_OBSERVED"
    #: Worked out again from the elapsed time rather than from the stored value.
    RECOMPUTED = "RECOMPUTED"
    #: Taken again: a lease, a handle, a token, a request. Having had one before the
    #: restart is not having one now.
    RE_ACQUIRED = "RE_ACQUIRED"


@dataclass(frozen=True, slots=True)
class RestartRule:
    """One row of the contract's table, in the contract's own words."""

    #: The kind of thing, as a stable token: the contract's row in one word.
    kind: str
    #: The contract's name for the row, so the transcription can be checked against
    #: the document rather than believed.
    what: str
    durability: Durability
    #: The contract's own reason, which is what makes the class arguable rather than
    #: arbitrary.
    reason: str
    precondition: ResumptionPrecondition

    def as_document(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "what": self.what,
            "durability": self.durability.value,
            "reason": self.reason,
            "resumption_precondition": self.precondition.value,
        }


#: The contract's table, row for row, with the acting rule attached to each. Kept in
#: the contract's order so that reading it beside the document is a comparison and
#: not a search.
RESTART_RULES: Final[tuple[RestartRule, ...]] = (
    RestartRule(
        "IDENTITY",
        "身份、自称、选填个人信息、人格种子与慢变价值观",
        Durability.KEPT,
        "决定「我是谁」",
        ResumptionPrecondition.NONE,
    ),
    RestartRule(
        "EXPERIENCE",
        "亲历事件、证据、信念与修订链",
        Durability.KEPT,
        "决定「发生过什么、我怎样理解」",
        ResumptionPrecondition.NONE,
    ),
    RestartRule(
        "RELATIONSHIPS",
        "关系、旧怨、亏欠、承诺",
        Durability.KEPT_AND_REEVALUATED,
        "防止重启洗白关系",
        ResumptionPrecondition.REEVALUATED,
    ),
    RestartRule(
        "GOALS",
        "长中短期目标、项目、放弃理由",
        Durability.KEPT_AND_REVERIFIED,
        "记得「我原本想做什么」，但不盲做",
        ResumptionPrecondition.PRECONDITIONS_REVERIFIED,
    ),
    RestartRule(
        "PLACES_AND_ASSETS",
        "地点、权属、资产和传送门链路",
        Durability.HISTORICAL_ONLY,
        "离线世界可能已变化",
        ResumptionPrecondition.WORLD_RE_OBSERVED,
    ),
    RestartRule(
        "KNOWLEDGE",
        "知识画像、世界书版本、研究笔记",
        Durability.KEPT,
        "不因模型会话消失而重新变小白",
        ResumptionPrecondition.NONE,
    ),
    RestartRule(
        "SKILLS",
        "技能定义、尝试、成功/失败范围",
        Durability.KEPT_AND_REVERIFIED,
        "继续后天学习，但不虚称仍可执行",
        ResumptionPrecondition.PRECONDITIONS_REVERIFIED,
    ),
    RestartRule(
        "MOOD",
        "心境与需求快照",
        Durability.RECOMPUTED,
        "不永远冻结愤怒，也不重启清零",
        ResumptionPrecondition.RECOMPUTED,
    ),
    RestartRule(
        "LAST_KNOWN_STATE",
        "最后已知生命、背包、位置、时间",
        Durability.HISTORICAL_ONLY,
        "服务器可能继续运行或回档",
        ResumptionPrecondition.WORLD_RE_OBSERVED,
    ),
    RestartRule(
        "INPUT_CONTROL",
        "按键、输入 lease、视角控制、战斗目标",
        Durability.INVALIDATED,
        "旧动作重放会伤人或送死",
        ResumptionPrecondition.RE_ACQUIRED,
    ),
    RestartRule(
        "GUI_HANDLES",
        "GUI syncId/revision、游标、运行时配方 ID",
        Durability.INVALIDATED,
        "只对当前会话有效",
        ResumptionPrecondition.RE_ACQUIRED,
    ),
    RestartRule(
        "ENTITY_TOKENS",
        "实体 ID、观察 target token、短时碰撞探针",
        Durability.INVALIDATED,
        "实体 ID/场景会变化，例外不得入长期信念",
        ResumptionPrecondition.RE_ACQUIRED,
    ),
    RestartRule(
        "IN_FLIGHT_REQUESTS",
        "在途 LLM/网页请求与旧 intent_generation",
        Durability.EXPIRED,
        "防止迟到结果劫持新会话",
        ResumptionPrecondition.RE_ACQUIRED,
    ),
)

_BY_KIND: Final[dict[str, RestartRule]] = {rule.kind: rule for rule in RESTART_RULES}


@dataclass(frozen=True, slots=True)
class ResumptionDecision:
    """Whether a remembered thing may be acted on yet, and what is missing."""

    admitted: bool
    missing: ResumptionPrecondition | None = None

    def __str__(self) -> str:
        if self.admitted:
            return "RESUMED"
        return f"NOT_RESUMED:{self.missing}"

    def as_document(self) -> dict[str, object]:
        return {
            "admitted": self.admitted,
            "missing": None if self.missing is None else self.missing.value,
        }


def rule_for(kind: str) -> RestartRule | None:
    """The rule for one kind of thing, or None when this module knows of no such kind."""

    return _BY_KIND.get(kind)


def admit_resumption(kind: str, *, established: Set[ResumptionPrecondition]) -> ResumptionDecision:
    """Whether a remembered thing of this kind may be acted on.

    A kind this module does not know is refused rather than allowed: the answer to
    "may I act on this" for a thing nobody has classified is not yes. That is the
    same reading the recovery policy takes of an effect it cannot read, and the same
    one the census of a work package takes of a case it cannot place.
    """

    rule = _BY_KIND.get(kind)
    if rule is None:
        return ResumptionDecision(False, ResumptionPrecondition.RE_ACQUIRED)
    if rule.precondition is ResumptionPrecondition.NONE:
        # Nothing to re-establish: this is the Kin itself, or what it knows. Spelled
        # out rather than left to the set, because "already established" and "needs
        # no establishing" are different reasons to admit the same thing.
        return ResumptionDecision(True)
    if rule.precondition in established:
        return ResumptionDecision(True)
    return ResumptionDecision(False, rule.precondition)
