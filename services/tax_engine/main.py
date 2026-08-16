from __future__ import annotations

import argparse
import json
from pathlib import Path

from .calculator import calculate_tax_state
from .models import TaxpayerConfig


def load_config(path: str) -> TaxpayerConfig:
    return TaxpayerConfig.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only deterministic Tax Engine v0.1")
    parser.add_argument("--config", default="config/taxpayer.2026.json")
    args = parser.parse_args()
    config = load_config(args.config)
    confirmed_zero = [f"2026-{month:02d}" for month in range(1, 6)]
    expected_through_july = [f"2026-{month:02d}" for month in range(1, 8)]
    state = calculate_tax_state([], config, confirmed_zero, expected_through_july)
    print(json.dumps(state, default=str, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
