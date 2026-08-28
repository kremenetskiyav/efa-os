import ast
import re
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import asyncpg  # noqa: F401
except ModuleNotFoundError:
    sys.modules["asyncpg"] = types.ModuleType("asyncpg")

import ai_analyst_v1 as analyst  # noqa: E402
import competitor_report_v1 as competitor  # noqa: E402
from format_ai_analyst_email import render  # noqa: E402


BASE_REPORT = """# AI Analyst v1.3 — Price Decision v1
## Сегодня: 2026-08-27 против 2026-08-26
### НАБЛЮДАТЬ · УФ 001Б
- Продажи: вчера **2 шт. / 1 248 ₽**, позавчера **1 шт. / 624 ₽**; изменение **1 шт. / 624 ₽**.
- Цена: **757 ₽** (2026-08-27); предыдущий снимок **757 ₽** (2026-08-26); изменение **0 ₽**.
- Остаток: **285 шт.** (2026-08-27); предыдущий снимок **285 шт.** (2026-08-26); изменение **0 шт.**.
- Почему: подтверждённых причин для изменения цены нет.
Данные продаж: **2026-08-21 — 2026-08-27**; сравнение: **2026-08-14 — 2026-08-20**.
## SKU: 1
### УФ 001Б · Ozon SKU 4601821825
#### PRICE DECISION V1
- Текущая цена: **757 ₽**.
- Фактическая цена продажи / цена активной акции: **624 ₽ / 624 ₽**.
- Рекомендация по цене: **ОСТАВИТЬ**.
- Рекомендуемая тестовая цена: **757 ₽**.
- Изменение: **0 ₽ / 0.0%**.
- Рекомендация по акции: **ОСТАВИТЬ**.
- Финансы периода: PBT **81.11 ₽**; прибыль/шт. **40.555 ₽**; маржа **6.49%**.
- Уверенность: **ВЫСОКАЯ**.
- Причина: подтверждённых причин для изменения цены нет.
"""


def current_summary() -> dict:
    watch = {
        "finding_key": "watch-own-005",
        "severity": "WATCH",
        "finding_type": "OWN_SEARCH_VISIBILITY_LOST",
        "message": (
            "УФ 005Б: наша карточка не найдена по OEM 647941 в пределах лимита "
            "текущего снимка; найдена по OEM 647975."
        ),
    }
    info = [
        {
            "finding_key": f"info-{index}",
            "severity": "INFO",
            "finding_type": "COMPETITOR_VISIBILITY_RESTORED",
            "message": f"Информационное событие {index}.",
        }
        for index in range(9)
    ]
    return {
        "contract_version": "competitor_monitor_summary.v1",
        "available": True,
        "status": "WATCH",
        "coverage": {
            "portfolio_sku_count": 5,
            "active_monitored_sku_count": 4,
        },
        "snapshot": {
            "reference_at": "2026-08-26T06:14:43.028Z",
            "freshness_status": "UNKNOWN",
        },
        "counts": {
            "important_count": 0,
            "watch_count": 1,
            "info_count": 9,
            "total_findings": 10,
        },
        "top_findings": [watch, *info],
        "own": {
            "own_findings": [
                watch,
                {
                    "finding_key": "own-restored-004",
                    "severity": "INFO",
                    "finding_type": "OWN_SEARCH_VISIBILITY_RESTORED",
                    "message": (
                        "УФ 004Б: наша карточка снова найдена по OEM 5Q0819644A, "
                        "5Q0819653, 5Q0819669 в пределах лимита текущего снимка."
                    ),
                },
            ]
        },
        "competitors": {
            "visibility_lost_count": 4,
            "visibility_restored_count": 3,
        },
        "prices": {
            "price_changes": [
                {
                    "offer_id": "УФ 005Б",
                    "role_label": "Дополнительный конкурент",
                    "previous_price": 689,
                    "current_price": 698,
                    "delta": 9,
                    "delta_pct": 1.3062409288824384,
                }
            ]
        },
    }


def rendered_payload(summary: dict | None = None) -> tuple[competitor.CompetitorPresentation, dict[str, str]]:
    presentation = competitor.build_presentation(summary or current_summary())
    report = BASE_REPORT + "\n" + competitor.render_source_section(presentation)
    return presentation, render(report)


class CompetitorPresentationTests(unittest.TestCase):
    def test_01_current_watch_summary_is_rendered(self):
        _, payload = rendered_payload()
        self.assertIn("Наблюдать", payload["html"])
        self.assertIn("OEM 647941", payload["text"])

    def test_02_own_watch_is_always_individual(self):
        presentation, _ = rendered_payload()
        self.assertEqual(1, len(presentation.priority_items))
        self.assertEqual("WATCH", presentation.priority_items[0][0])

    def test_03_one_own_restoration_info_is_allowed_in_email(self):
        _, payload = rendered_payload()
        self.assertIn("УФ 004Б", payload["html"])
        self.assertNotIn("УФ 004Б", competitor.render_telegram_text(competitor.build_presentation(current_summary())))

    def test_04_competitor_events_are_aggregated(self):
        _, payload = rendered_payload()
        self.assertIn("−4 / +3", payload["html"])
        self.assertIn("Конкуренты: −4 / +3.", payload["text"])

    def test_05_one_price_event_is_rendered_factually(self):
        _, payload = rendered_payload()
        self.assertIn("689 → 698 ₽ (+9 ₽; +1.3%)", payload["html"])
        self.assertIn("689 → 698 ₽ (+9 ₽; +1.3%)", payload["text"])

    def test_06_nine_info_findings_are_not_dumped(self):
        _, payload = rendered_payload()
        for index in range(9):
            self.assertNotIn(f"Информационное событие {index}", payload["html"])
            self.assertNotIn(f"Информационное событие {index}", payload["text"])

    def test_07_valid_zero_finding_state_is_explicit(self):
        summary = current_summary()
        summary.update(status="NORMAL", top_findings=[])
        summary["counts"] = dict(
            important_count=0, watch_count=0, info_count=0, total_findings=0
        )
        summary["own"] = {"own_findings": []}
        summary["competitors"] = {
            "visibility_lost_count": 0,
            "visibility_restored_count": 0,
        }
        summary["prices"] = {"price_changes": []}
        _, payload = rendered_payload(summary)
        self.assertIn(competitor.ZERO_FINDINGS_TEXT, payload["html"])
        self.assertNotIn(competitor.UNAVAILABLE_TEXT, payload["text"])

    def test_08_degraded_state_is_explicit(self):
        presentation = competitor.build_presentation(
            {"contract_version": "competitor_monitor_summary.v1", "available": False}
        )
        self.assertIn(competitor.UNAVAILABLE_TEXT, competitor.render_email_html(presentation))
        self.assertIn(competitor.UNAVAILABLE_TEXT, competitor.render_telegram_text(presentation))

    def test_09_unavailable_is_not_reported_as_zero(self):
        text = competitor.render_telegram_text(competitor.unavailable_presentation())
        self.assertNotIn("0 изменений", text)
        self.assertNotIn(competitor.ZERO_FINDINGS_TEXT, text)

    def test_10_coverage_is_dynamic(self):
        summary = current_summary()
        summary["coverage"] = {
            "portfolio_sku_count": 5,
            "active_monitored_sku_count": 3,
        }
        _, payload = rendered_payload(summary)
        self.assertIn("3 из 5 SKU", payload["html"])

    def test_11_unknown_freshness_has_no_fresh_claim(self):
        _, payload = rendered_payload()
        self.assertIn("Свежесть: не определена.", payload["text"])
        self.assertNotIn("свежие данные", payload["text"].lower())
        self.assertNotIn("сегодняшний мониторинг актуален", payload["text"].lower())

    def test_12_snapshot_timestamp_is_factual_moscow_time(self):
        _, payload = rendered_payload()
        self.assertIn("снимок 26.08 09:14 МСК", payload["text"])

    def test_13_forbidden_disappearance_wording_is_suppressed(self):
        summary = current_summary()
        summary["top_findings"][0]["message"] = "УФ 005Б: карточка пропала."
        _, payload = rendered_payload(summary)
        for wording in competitor.FORBIDDEN_VISIBILITY_WORDING:
            self.assertNotIn(wording, payload["html"].lower())
            self.assertNotIn(wording, payload["text"].lower())

    def test_14_email_section_is_compact_and_complete(self):
        presentation = competitor.build_presentation(current_summary())
        section = competitor.render_email_html(presentation)
        self.assertIn("IMPORTANT 0 · WATCH 1 · INFO 9", section)
        self.assertLessEqual(section.count("<p>"), 6)

    def test_15_telegram_is_shorter_than_email(self):
        presentation = competitor.build_presentation(current_summary())
        email_text = re.sub(r"<[^>]+>", "", competitor.render_email_html(presentation))
        telegram = competitor.render_telegram_text(presentation)
        self.assertLess(len(telegram), len(email_text))
        self.assertLessEqual(len(telegram.splitlines()), 5)

    def test_16_both_channels_use_one_round_tripped_presentation(self):
        original = competitor.build_presentation(current_summary())
        parsed = competitor.parse_source_section(competitor.render_source_section(original))
        self.assertEqual(original, parsed)
        self.assertIn("647941", competitor.render_email_html(parsed))
        self.assertIn("647941", competitor.render_telegram_text(parsed))

    def test_18_degraded_competitor_does_not_suppress_unrelated_report(self):
        report = BASE_REPORT + "\n" + competitor.render_source_section(
            competitor.unavailable_presentation()
        )
        payload = render(report)
        self.assertIn("ЦЕНОВЫЕ РЕШЕНИЯ", payload["text"])
        self.assertIn("УФ 001Б", payload["text"])
        self.assertIn(competitor.UNAVAILABLE_TEXT, payload["text"])

    def test_19_source_contains_no_raw_competitor_sql_or_runtime_json(self):
        source = Path(competitor.__file__).read_text(encoding="utf-8")
        self.assertNotIn("public.competitor_", source)
        self.assertNotIn("COMPETITOR_MONITOR_SUMMARY_V1.json", source)
        tree = ast.parse(source)
        sql_strings = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and re.search(r"\b(SELECT|WITH)\b", node.value, re.I)
        ]
        for sql in sql_strings:
            self.assertNotRegex(
                sql,
                r"\b(INSERT\s+INTO|UPDATE\s+\S+\s+SET|DELETE\s+FROM|ON\s+CONFLICT|TRUNCATE)\b",
            )


class CompetitorReadIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_17_summary_failure_does_not_fail_analyst_module(self):
        with patch.object(
            analyst,
            "read_competitor_summary",
            new=AsyncMock(side_effect=RuntimeError("database unavailable")),
        ):
            presentation = await analyst._competitor_presentation(object())
        self.assertFalse(presentation.available)

    async def test_20_current_read_path_is_three_selects_and_has_no_writes(self):
        class Transaction:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

        class Connection:
            def __init__(self):
                self.calls = []

            def transaction(self):
                return Transaction()

            async def fetchrow(self, sql):
                self.calls.append(("fetchrow", sql))
                return {"finding_set_id": "00000000-0000-0000-0000-000000000001"}

            async def fetch(self, sql, *_args):
                self.calls.append(("fetch", sql))
                return []

        connection = Connection()
        expected = {"contract_version": "competitor_monitor_summary.v1", "available": True}
        with patch.object(competitor, "build_summary", return_value=expected):
            actual = await competitor.read_summary(connection)
        self.assertEqual(expected, actual)
        self.assertEqual(competitor.SUMMARY_SELECT_COUNT, len(connection.calls))
        for _, sql in connection.calls:
            self.assertRegex(sql, r"(?is)^\s*SELECT")
            self.assertNotRegex(sql, r"(?i)\b(INSERT|UPDATE|DELETE|ON\s+CONFLICT)\b")

    async def test_21_asyncpg_json_fields_are_decoded_for_summary_builder(self):
        decoded = competitor._decode_record(
            {"evidence": '{"queries": []}', "details": '{"membership_status": "PRIMARY"}'}
        )
        self.assertEqual({"queries": []}, decoded["evidence"])
        self.assertEqual("PRIMARY", decoded["details"]["membership_status"])


if __name__ == "__main__":
    unittest.main()
