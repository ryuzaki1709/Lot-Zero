"""Properties that protect Lot Zero's deterministic scope boundary."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from test_recall import evaluation_inputs

from lot_zero.domain.recall import exact_lot_match


@given(
    st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-", min_size=1).map(
        lambda value: f"X{value}"
    )
)
def test_arbitrary_nonmatching_lots_never_pass_exact_matching(candidate: str) -> None:
    assert exact_lot_match("ING-4417", candidate) is False


def test_permuted_inputs_produce_byte_equivalent_impact_json() -> None:
    from lot_zero.domain.recall import compute_impact

    scope, products, edges, inventory, shipments = evaluation_inputs()
    forward = compute_impact(scope, products, edges, inventory, shipments)
    reversed_inputs = compute_impact(
        scope,
        tuple(reversed(products)),
        tuple(reversed(edges)),
        tuple(reversed(inventory)),
        tuple(reversed(shipments)),
    )

    assert forward.model_dump_json() == reversed_inputs.model_dump_json()
