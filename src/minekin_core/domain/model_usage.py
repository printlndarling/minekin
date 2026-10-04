"""Allowlisted step-time model accounting, never provider billing or credentials."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import cast

from minekin_core.domain.model_access import CostLedger, UnavailableReason


@dataclass(frozen=True, slots=True)
class ModelUsageTotals:
    calls: int
    spent_estimate_micro: int
    run_cap_micro: int
    cap_refusals: int
    incomplete_usage_calls: int
    request_rate_micro_per_million: int
    response_rate_micro_per_million: int

    @classmethod
    def capture(cls, ledger: CostLedger) -> ModelUsageTotals:
        return cls(
            ledger.calls,
            ledger.spent,
            ledger.run_cost_cap,
            ledger.cap_refusals,
            sum(
                1
                for record in ledger.records
                if record.reason is not UnavailableReason.RUN_COST_CAP_REACHED
                and (record.request_tokens is None or record.response_tokens is None)
            ),
            ledger.request_micro_per_million_tokens,
            ledger.response_micro_per_million_tokens,
        )

    def as_document(self) -> dict[str, object]:
        return {"schema_version": 1, "basis": "step_time_estimate", **asdict(self)}

    @classmethod
    def from_payload(cls, value: object) -> ModelUsageTotals | None:
        if not isinstance(value, Mapping):
            return None
        raw = cast("Mapping[str, object]", value)
        fields = tuple(cls.__dataclass_fields__)
        if (
            set(raw) != {"schema_version", "basis", *fields}
            or type(raw.get("schema_version")) is not int
            or raw["schema_version"] != 1
            or raw.get("basis") != "step_time_estimate"
        ):
            return None
        numbers: list[int] = []
        for key in fields:
            number = raw[key]
            if type(number) is not int:
                return None
            integer = number
            if not 0 <= integer < 2**63:
                return None
            numbers.append(integer)
        result = cls(*numbers)
        if result.run_cap_micro == 0 or result.incomplete_usage_calls > result.calls:
            return None
        return result

    def summary(self) -> str:
        return (
            f"截至该技能步: 账本调用 {self.calls}; 预算估算 {self.spent_estimate_micro}/"
            f"{self.run_cap_micro} 微单位; usage 不完整 {self.incomplete_usage_calls} 次; "
            f"预算拒绝 {self.cap_refusals} 次; 请求/响应费率 "
            f"{self.request_rate_micro_per_million}/{self.response_rate_micro_per_million} "
            "微单位/百万 token; 不是供应商账单"
        )
