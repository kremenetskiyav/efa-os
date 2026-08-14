"""Reserved contracts for future deterministic PRICE_CHANGED detection."""

from snapshot import SnapshotWorkerNotImplementedError


def detect_price_changes() -> None:
    """Placeholder for future comparison of two valid immutable snapshots."""

    raise SnapshotWorkerNotImplementedError(
        "PRICE_CHANGED detection is not implemented in v1 skeleton"
    )
