import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_ai_analyst_email import parse_report, render  # noqa: E402


REPORT = """# AI Analyst v1.3 — Price Decision v1
## Сегодня: 2026-08-20 против 2026-08-19
### НАБЛЮДАТЬ · УФ 001Б
- Продажи: вчера **2 шт. / 1 248 ₽**, позавчера **н/д шт. / н/д**; изменение **н/д шт. / н/д**.
- Цена: **757 ₽** (2026-08-21); предыдущий снимок **757 ₽** (2026-08-16); изменение **0 ₽**.
- Остаток: **285 шт.** (2026-08-21); предыдущий снимок **285 шт.** (2026-08-13); изменение **0 шт.**.
- Почему: продажи за позавчера: н/д; изменение не рассчитано.
Данные продаж: **2026-08-14 — 2026-08-20**; сравнение: **2026-08-07 — 2026-08-13**.
## SKU: 1
### УФ 001Б · Ozon SKU 4601821825
#### PRICE DECISION V1
- Текущая цена: **757 ₽**.
- Фактическая цена продажи / цена активной акции: **624 ₽ / 624 ₽**.
- Рекомендация по цене: **ОСТАВИТЬ**.
- Рекомендуемая тестовая цена: **757 ₽**.
- Изменение: **0 ₽ / 0.0%**.
- Рекомендация по акции: **ОСТАВИТЬ**.
- Расчётная текущая маржа: **13.6%** до налога; подтверждено доставок: **3**.
- Уверенность: **ВЫСОКАЯ**.
- Причина: Фактическая цена 624 ₽ совпадает с активной акцией; маржа 13.6% при 3 подтверждённых доставках.
## Правила Price Decision v1
diagnostic dump
"""


class CompactReportTests(unittest.TestCase):
    def test_renders_only_compact_decision_fields(self):
        payload = render(REPORT)
        self.assertEqual(payload["date"], "2026-08-20")
        self.assertIn("2 шт.", payload["html"])
        self.assertIn("1 248 ₽", payload["html"])
        self.assertIn("757 ₽ → 757 ₽", payload["html"])
        self.assertIn("Акция: оставить", payload["html"])
        self.assertIn("уверенность: высокая", payload["html"])
        self.assertNotIn("Правила Price Decision v1", payload["html"])
        self.assertNotIn("diagnostic dump", payload["html"])
        self.assertLess(len(payload["html"]), 8000)

    def test_missing_daily_fact_keeps_sku_and_does_not_turn_it_into_zero(self):
        report = REPORT.replace(
            "вчера **2 шт. / 1 248 ₽**",
            "вчера **н/д шт. / н/д**",
        )

        _, skus, _ = parse_report(report)
        payload = render(report)

        self.assertEqual(len(skus), 1)
        self.assertIsNone(skus[0].sales)
        self.assertIn("УФ 001Б", payload["html"])
        self.assertIn("Продажи вчера: н/д шт. / н/д", payload["text"])


if __name__ == "__main__":
    unittest.main()
