"""The R3 operator corpus.

Five PowerUnits operator intents that R0 and R2 already cover. Each case is
expressed once, as user intent, and then dispatched with equivalent arguments
against both systems under comparison:

    CURRENT_FORK        this fork's built-in ``tools/powerunits_*`` wrappers
    MODERN_HERMES_PROOF the standalone plugin behind the generic bounded client

The corpus is deliberately not tuned toward either side: the argument payload
comes from the frozen R0 contracts, not from anything written for R3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tests.powerunits_golden.contracts import (
    BoundedHttpContract,
    args_for,
    contract_by_operation,
)


@dataclass(frozen=True)
class CorpusCase:
    """One operator intent, plus how each system answers it."""

    case_id: str
    intent: str
    current_fork_tool: str
    modern_tool: str | None
    contract_operation: str | None
    # Non-empty only when the modern proof has no equivalent safe path today.
    modern_gap: str = ""

    @property
    def has_modern_equivalent(self) -> bool:
        return self.modern_tool is not None

    @property
    def contract(self) -> BoundedHttpContract:
        if self.contract_operation is None:
            raise LookupError(f"{self.case_id} is not a bounded HTTP operation")
        return contract_by_operation()[self.contract_operation]

    def args(self) -> dict[str, Any]:
        return args_for(self.contract)


CORPUS: tuple[CorpusCase, ...] = (
    CorpusCase(
        case_id="coverage_snapshot",
        intent=(
            "Operator asks for the current coverage / data-health snapshot for a "
            "country and time window."
        ),
        current_fork_tool="read_powerunits_coverage_snapshot_v1",
        modern_tool="read_powerunits_coverage_snapshot_v1",
        contract_operation="read_powerunits_coverage_snapshot_v1",
    ),
    CorpusCase(
        case_id="coverage_inventory",
        intent="Operator asks which bounded coverage inventory exists for a window.",
        current_fork_tool="inventory_powerunits_bounded_coverage_v1",
        modern_tool="inventory_powerunits_bounded_coverage_v1",
        contract_operation="inventory_powerunits_bounded_coverage_v1",
    ),
    CorpusCase(
        case_id="entsoe_bzn_price_readiness",
        intent="Operator asks whether ENTSO-E BZN prices are ready for the window.",
        current_fork_tool="read_powerunits_entsoe_bzn_price_readiness_v1",
        modern_tool="read_powerunits_entsoe_bzn_price_readiness_v1",
        contract_operation="read_powerunits_entsoe_bzn_price_readiness_v1",
    ),
    CorpusCase(
        case_id="option_d_readiness_window",
        intent="Operator asks whether the model / readiness window is usable.",
        current_fork_tool="readiness_powerunits_option_d_bounded_window",
        modern_tool="readiness_powerunits_option_d_bounded_window",
        contract_operation="readiness_powerunits_option_d_bounded_window",
    ),
    CorpusCase(
        case_id="methodology_doc",
        intent=(
            "Operator asks a methodology / documentation question that has a safe, "
            "non-production answer path."
        ),
        current_fork_tool="read_powerunits_doc",
        modern_tool=None,
        contract_operation=None,
        modern_gap=(
            "R2 ported the four bounded HTTP reads only. The docs surface is not a "
            "bounded Repo-B operation, so it is neither in the plugin nor reachable "
            "under an operator cap that allows only powerunits_bounded_reads."
        ),
    ),
)

BOUNDED_CASES: tuple[CorpusCase, ...] = tuple(
    case for case in CORPUS if case.has_modern_equivalent
)

CORPUS_BY_ID: dict[str, CorpusCase] = {case.case_id: case for case in CORPUS}
