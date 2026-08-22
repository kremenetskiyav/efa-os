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
- Рекомендация по акции: **ВЫЙТИ**.
- Финансы периода: PBT **81.11 ₽**; прибыль/шт. **40.555 ₽**; маржа **6.49%**.
- Уверенность: **ВЫСОКАЯ**.
- Причина: Фактическая цена 624 ₽ совпадает с активной акцией; маржа 6.49% при 2 подтверждённых доставках.
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
        self.assertIn("Акция: выйти", payload["html"])
        self.assertIn("уверенность: высокая", payload["html"])
        self.assertIn("PBT: 81.11 ₽", payload["html"])
        self.assertIn("прибыль/шт.: 40.555 ₽", payload["html"])
        self.assertIn("маржа: 6.49%", payload["html"])
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

    def test_negative_pbt_keeps_missing_unit_profit_and_margin_as_not_available(self):
        report = REPORT.replace(
            "PBT **81.11 ₽**; прибыль/шт. **40.555 ₽**; маржа **6.49%**",
            "PBT **-6.43 ₽**; прибыль/шт. **н/д**; маржа **н/д**",
        ).replace("Рекомендация по акции: **ВЫЙТИ**", "Рекомендация по акции: **ПРОВЕРИТЬ**")

        _, skus, _ = parse_report(report)
        payload = render(report)

        self.assertEqual(skus[0].pbt, "-6.43 ₽")
        self.assertEqual(skus[0].profit_per_unit, "н/д")
        self.assertEqual(skus[0].margin, "н/д")
        self.assertEqual(skus[0].promo_action, "ПРОВЕРИТЬ")
        self.assertIn("PBT: -6.43 ₽ · прибыль/шт.: н/д · маржа: н/д", payload["text"])
        self.assertNotIn("маржа: 0%", payload["text"])


if __name__ == "__main__":
    unittest.main()
