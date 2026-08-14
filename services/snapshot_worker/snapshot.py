"""Reserved contracts for future immutable product snapshot creation."""


class SnapshotWorkerNotImplementedError(NotImplementedError):
    """Signals that Snapshot Layer write logic is intentionally absent in the skeleton."""


def build_snapshot_candidates() -> None:
    """Placeholder for future read-only source mapping and snapshot construction."""

    raise SnapshotWorkerNotImplementedError("Snapshot creation is not implemented in v1 skeleton")
