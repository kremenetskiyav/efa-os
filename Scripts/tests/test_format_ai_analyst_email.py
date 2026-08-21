import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_ai_analyst_email import render  # noqa: E402


REPORT = """# AI Analyst v1.2 — ежедневный отчёт EFA
## Сегодня: 2026-08-20 против 2026-08-19
### НАБЛЮДАТЬ · УФ 001Б
- Продажи: вчера **2 шт. / 1 248 ₽**, позавчера **н/д шт. / н/д**; изменение **н/д шт. / н/д**.
- Цена: **757 ₽** (2026-08-21); предыдущий снимок **757 ₽** (2026-08-16); изменение **0 ₽**.
- Остаток: **285 шт.** (2026-08-21); предыдущий снимок **285 шт.** (2026-08-13); изменение **0 шт.**.
- Почему: продажи за позавчера: н/д; изменение не рассчитано.
Данные продаж: **2026-08-14 — 2026-08-20**; сравнение: **2026-08-07 — 2026-08-13**.
## SKU: 1
### УФ 001Б · Ozon SKU 4601821825
#### ЦЕНА
- Рекомендация по цене: **НЕДОСТАТОЧНО ДАННЫХ**.
#### АКЦИИ
- Рекомендация по акции: **НЕ ТРОГАТЬ**.
- Причина: Цена: окно спроса неполное. Акции: экономика не отрицательная.
## Правила v1.2
diagnostic dump
"""


class CompactReportTests(unittest.TestCase):
    def test_renders_only_compact_decision_fields(self):
        payload = render(REPORT)
        self.assertEqual(payload["date"], "2026-08-20")
        self.assertIn("2 шт.", payload["html"])
        self.assertIn("1 248 ₽", payload["html"])
        self.assertIn("акция: оставить", payload["html"])
        self.assertNotIn("Правила v1.2", payload["html"])
        self.assertNotIn("diagnostic dump", payload["html"])
        self.assertLess(len(payload["html"]), 8000)


if __name__ == "__main__":
    unittest.main()
