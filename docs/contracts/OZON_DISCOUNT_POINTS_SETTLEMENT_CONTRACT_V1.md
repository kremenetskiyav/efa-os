# EFA OS — Ozon Discount & Points Settlement Contract v1

**Version:** `1.0-draft`
**Date:** `2026-09-01`
**Status:** `CANONICAL DRAFT — READY FOR EMPIRICAL VALIDATION`
**Implementation status:** `NOT APPROVED FOR PRODUCTION`

## Required topic coverage

This index maps the required contract topics to the approved contract text below. It adds no financial interpretation.

| # | Required topic | Approved source section |
| ---: | --- | --- |
| 1 | Core Principle | 1. ОБЯЗАТЕЛЬНОЕ ПРАВИЛО |
| 2 | Price Layers | 1. ОБЯЗАТЕЛЬНОЕ ПРАВИЛО |
| 3 | Seller-funded discounts | 2. SELLER-FUNDED СКИДКИ |
| 4 | Ozon-funded discount | 3. OZON-FUNDED DISCOUNT И БАЛЛЫ |
| 5 | Buyer Other Price | 1. ОБЯЗАТЕЛЬНОЕ ПРАВИЛО; 3. OZON-FUNDED DISCOUNT И БАЛЛЫ |
| 6 | Green Price / Bank Price | 5. GREEN PRICE / BANK PRICE |
| 7 | Ozon Points | 3. OZON-FUNDED DISCOUNT И БАЛЛЫ; 7. БАЛЛЫ И УСЛУГИ |
| 8 | Double Counting Rule | 4. DOUBLE COUNTING ЗАПРЕЩЁН |
| 9 | Points accrual statuses | 10. RETURNS / REVERSALS; 11. ESTIMATED И SETTLED ECONOMICS |
| 10 | Points-eligible services | 7. БАЛЛЫ И УСЛУГИ |
| 11 | Non-eligible/pass-through services | 7. БАЛЛЫ И УСЛУГИ |
| 12 | Economic P&L vs Cash Settlement | 8. ECONOMIC P&L ≠ CASH SETTLEMENT |
| 13 | Excess Points | 9. EXCESS POINTS |
| 14 | Commission nominal/effective distinction | 6. COMMISSION |
| 15 | Green Price decomposition | 5. GREEN PRICE / BANK PRICE; 17. ОБЯЗАТЕЛЬНЫЕ ORDER-LEVEL ПОЛЯ |
| 16 | Economic Revenue | 3. OZON-FUNDED DISCOUNT И БАЛЛЫ; 14. UNIT PROFIT; 19. RULE 4 |
| 17 | Unit Profit | 14. UNIT PROFIT |
| 18 | Contribution Margin | 15. MARGIN |
| 19 | Advertising separation: CPC / CPO / Elastic | 16. ADVERTISING |
| 20 | Returns / reversals | 10. RETURNS / REVERSALS |
| 21 | Period settlement | 18. PERIOD-LEVEL SETTLEMENT |
| 22 | Estimated vs Settled economics | 11. ESTIMATED И SETTLED ECONOMICS |
| 23 | Source of Truth priority | 12. SOURCE OF TRUTH |
| 24 | Data confidence/statuses | 13. DATA STATUS |
| 25 | Required order-level fields | 17. ОБЯЗАТЕЛЬНЫЕ ORDER-LEVEL ПОЛЯ |
| 26 | Required period-level fields | 18. PERIOD-LEVEL SETTLEMENT |
| 27 | AI Analyst / Price Decision hard rules | 19. HARD RULES ДЛЯ AI ANALYST / PRICE DECISION |
| 28 | Current EFA example УФ 001Б | 21. CURRENT EFA EXAMPLE — УФ 001Б |
| 29 | Validation Cases #1–#5 | 22. EMPIRICAL VALIDATION |
| 30 | Calculator Safety Gates | 19. RULE 10; 23. IMPLEMENTATION GATE |
| 31 | Price Decision Gate | 20. PRICE DECISION; 23. IMPLEMENTATION GATE |
| 32 | Strategic Model | 20. ECONOMIC VIABILITY / MARKET COMPETITIVENESS |
| 33 | Current Contract Status | Document metadata |
| 34 | Implementation Gate | 23. IMPLEMENTATION GATE |
| 35 | FINAL INVARIANTS `INV-1` … `INV-10` | FINAL INVARIANTS |
| 36 | WORK / CODEX EXECUTION RULE | WORK / CODEX EXECUTION RULE |

## Approved contract text

**Дата фиксации:** 01.09.2026
**Статус:** `CANONICAL DRAFT — READY FOR EMPIRICAL VALIDATION`
**Назначение:** обязательный финансовый контракт для Work/Codex при работе с Ozon Calculator, AI Analyst, Price Decision, акциями, скидками и маржинальностью.

## 1. ОБЯЗАТЕЛЬНОЕ ПРАВИЛО

Никогда не использовать публичную цену покупателя Ozon как экономическую выручку продавца без decomposition.

Разделять:

1. `BASE_SELLER_PRICE` — базовая цена продавца;
2. `SELLER_PROMO_DISCOUNT` — скидка за счёт продавца;
3. `SELLER_ECONOMIC_PRICE` — цена после seller-funded скидок;
4. `OZON_FUNDED_DISCOUNT` — дополнительная скидка площадки;
5. `BUYER_OTHER_PRICE` — публичная цена без Green/Bank механики;
6. `GREEN_PRICE / BANK_PRICE` — специальная цена при соответствующем способе оплаты;
7. `OZON_POINTS`;
8. `GREEN_PRICE_CASH_COMPENSATION`.

Главная экономическая цена:

`SELLER_ECONOMIC_PRICE = BASE_SELLER_PRICE - SELLER_FUNDED_DISCOUNTS`

Именно она является основным input для прогнозной unit economics.

---

## 2. SELLER-FUNDED СКИДКИ

К seller-funded относятся только подтверждённые скидки, финансируемые продавцом, включая применимые:

- Elastic Boost;
- seller-funded акции;
- ручное снижение цены;
- купоны продавца;
- другие акции за счёт продавца.

Seller-funded discount действительно уменьшает маржу.

Пример:

`BASE = 1290 ₽`
`ELASTIC = 660 ₽`

тогда:

`SELLER_PROMO_DISCOUNT = 630 ₽`

`SELLER_ECONOMIC_PRICE = 660 ₽`

Эти 630 ₽ нельзя считать компенсацией Ozon без отдельного settlement evidence.

---

## 3. OZON-FUNDED DISCOUNT И БАЛЛЫ

Если Ozon после seller economic price дополнительно снижает публичную цену:

`SELLER_ECONOMIC_PRICE = 660 ₽`
`BUYER_OTHER_PRICE = 436 ₽`

то разница:

`224 ₽`

может являться компенсируемой дополнительной скидкой Ozon.

До фактического settlement:

`224 ₽ = ESTIMATED_OZON_FUNDED_DISCOUNT`

а не подтверждённые баллы.

Основное правило:

`1 балл = 1 ₽ economic value`

Но баллы являются компенсацией скидки, а не дополнительной выручкой поверх seller economic price.

Запрещено:

`660 + 224 = 884 ₽`

Корректная логика при полной компенсации:

`436 ₽ cash realization + 224 ₽ compensation = 660 ₽ economic realization`

---

## 4. DOUBLE COUNTING ЗАПРЕЩЁН

Никогда не:

- прибавлять баллы поверх полного `SELLER_ECONOMIC_PRICE`;
- одновременно считать Ozon-funded discount расходом и затем добавлять компенсацию;
- считать расход нулевым только потому, что он был погашен баллами;
- считать Bank price seller revenue без decomposition.

---

## 5. GREEN PRICE / BANK PRICE

Разницу:

`BUYER_OTHER_PRICE - BANK_PRICE`

не считать автоматически:

- баллами;
- скидкой продавца;
- денежной компенсацией банка.

Использовать поля:

`green_price_discount`
`green_price_cash_compensation`
`green_price_points_compensation`
`green_price_unresolved_compensation`

До settlement:

`GREEN_PRICE_FUNDING_UNKNOWN`

если источник финансирования не подтверждён.

---

## 6. COMMISSION

Всегда разделять:

`COMMISSION_RATE_NOMINAL`

и

`COMMISSION_RATE_EFFECTIVE`.

Номинальные 47% нельзя автоматически считать фактической эффективной комиссией.

Приоритет источников:

1. фактический settlement конкретного заказа;
2. фактические post-tariff продажи SKU;
3. официальный действующий тариф;
4. stress assumption.

`COMMISSION_BASE` хранить отдельно.

Точную базу комиссии не фиксировать предположением до empirical validation.

---

## 7. БАЛЛЫ И УСЛУГИ

Разделять расходы:

`POINTS_ELIGIBLE`
`NOT_POINTS_ELIGIBLE`
`UNKNOWN`

Баллами могут погашаться собственные услуги Ozon, включая подтверждённые категории верхнего уровня:

- вознаграждение за продажу;
- логистику Ozon;
- размещение;
- продвижение;
- другие собственные услуги Ozon.

Партнёрские/pass-through услуги нельзя автоматически считать eligible.

Для каждого вида начисления eligibility должна определяться отдельно.

`UNKNOWN` запрещено автоматически преобразовывать в `ELIGIBLE`.

---

## 8. ECONOMIC P&L ≠ CASH SETTLEMENT

Если услуга стоимостью 100 ₽ была полностью оплачена баллами:

Economic P&L:

`expense = 100 ₽`

Cash settlement:

`cash paid = 0 ₽`

Баллы меняют форму оплаты, но не экономическую стоимость услуги.

---

## 9. EXCESS POINTS

Если после зачёта против eligible services остаются баллы, остаток может быть выплачен деньгами.

Не считать эту выплату новой прибылью второй раз.

Она является cash realization уже учтённой экономической компенсации.

---

## 10. RETURNS / REVERSALS

Модель обязана поддерживать:

`points_accrued`
`points_reversed`
`points_adjustment`
`points_net`

При возврате или иной корректировке ранее начисленные баллы могут быть сторнированы.

Нельзя считать provisional points окончательной прибылью до settlement lifecycle.

---

## 11. ESTIMATED И SETTLED ECONOMICS

Всегда иметь два режима.

### ESTIMATED

Допускает:

- estimated points;
- expected logistics;
- assumed commission;
- expected return/non-buyout;
- прогноз рекламы.

Статус:

`ESTIMATED`

### SETTLED

Использует:

- фактическую реализацию;
- фактическую commission;
- фактические points;
- фактическую logistics;
- фактические adjustments;
- фактические advertising costs.

Статус:

`SETTLED`

Нельзя представлять `ESTIMATED` как окончательный финансовый результат.

---

## 12. SOURCE OF TRUTH

При конфликте данных использовать приоритет:

1. финальный settlement / документы Ozon;
2. детализация начислений конкретного заказа;
3. Seller Finance / Unit Economics;
4. конфигурация цены и акции;
5. официальная документация Ozon;
6. Calculator forecast;
7. buyer interface.

Buyer interface является источником истины только для:

`WHAT CUSTOMER SEES`

но не для:

`WHAT SELLER EARNS`.

---

## 13. DATA STATUS

Финансовые значения должны иметь статус:

- `CONFIRMED_SETTLEMENT`
- `CONFIRMED_SELLER`
- `OFFICIAL_CONTRACT`
- `OBSERVED_BUYER_UI`
- `ESTIMATED`
- `ASSUMED`
- `UNKNOWN`

Запрещено повышать статус данных без источника.

---

## 14. UNIT PROFIT

Canonical preliminary formula:

`UNIT_PROFIT =`

`SELLER_ECONOMIC_PRICE`
`- COMMISSION`
`- OZON_LOGISTICS`
`- FULFILMENT_PROCESSING`
`- LAST_MILE`
`- ACQUIRING`
`- EXPECTED_RETURN_NONBUYOUT_COST`
`- ADVERTISING_COST`
`- TAX`
`- COGS`
`- OTHER_VARIABLE_COSTS`

При полностью компенсируемой Ozon-funded скидке она не вычитается из `SELLER_ECONOMIC_PRICE` второй раз.

---

## 15. MARGIN

Основная маржа:

`CONTRIBUTION_MARGIN = UNIT_PROFIT / SELLER_ECONOMIC_PRICE`

Не использовать Bank price в знаменателе основной unit economics, если Bank price сформирована дополнительными компенсируемыми скидками.

---

## 16. ADVERTISING

Разделять:

- CPC;
- CPO;
- other paid promotion;
- Elastic seller-funded discount.

Elastic Boost не записывать как обычный рекламный расход.

Его экономическая стоимость:

`BASE_SELLER_PRICE - SELLER_ECONOMIC_PRICE`

CPC/CPO учитывать отдельной строкой.

Если рекламная услуга была погашена баллами, её economic cost не становится нулём.

---

## 17. ОБЯЗАТЕЛЬНЫЕ ORDER-LEVEL ПОЛЯ

Минимум:

`order_id`
`offer_id`
`sku`

`base_seller_price`
`seller_promo_discount`
`seller_economic_price`

`buyer_other_price`
`buyer_green_price`

`ozon_funded_discount_estimated`
`ozon_points_accrued`
`ozon_points_reversed`

`green_price_cash_compensation`
`green_price_points_compensation`

`commission_base`
`commission_rate_nominal`
`commission_rate_effective`
`commission_amount`

`logistics_cost`
`processing_cost`
`last_mile_cost`
`acquiring_cost`
`advertising_cost`
`tax_cost`
`cogs`
`other_variable_cost`

`unit_profit_estimated`
`unit_profit_settled`
`margin_estimated`
`margin_settled`

`settlement_status`

---

## 18. PERIOD-LEVEL SETTLEMENT

Хранить отдельно:

`period_start`
`period_end`

`points_accrued_total`
`points_reversed_total`
`points_net`

`eligible_service_cost_total`
`points_used_total`
`cash_service_cost_total`

`excess_points_cash_premium`
`negative_points_adjustment`

`reconciliation_difference`
`settlement_status`

Нельзя полностью реконструировать месячный cash settlement простым суммированием unit profit.

---

## 19. HARD RULES ДЛЯ AI ANALYST / PRICE DECISION

### RULE 1

`BUYER_PRICE != SELLER_REVENUE`

без decomposition.

### RULE 2

Никогда не прибавлять points поверх полного `SELLER_ECONOMIC_PRICE`.

### RULE 3

Seller-funded discount всегда уменьшает seller economics.

### RULE 4

Ozon-funded compensated discount при полной компенсации не уменьшает economic revenue.

### RULE 5

Оплата расхода баллами не отменяет economic expense.

### RULE 6

`ECONOMIC P&L != CASH SETTLEMENT`.

### RULE 7

Все прогнозные баллы маркировать `ESTIMATED`.

### RULE 8

При неизвестной комиссии использовать:

`COMMISSION_UNCONFIRMED`.

### RULE 9

При неизвестном источнике Green Price:

`GREEN_PRICE_FUNDING_UNKNOWN`.

### RULE 10

При settlement mismatch запрещать автоматический Price Decision.

---

## 20. PRICE DECISION

Price Decision должен работать от:

`SELLER_ECONOMIC_PRICE`

а не от Bank price.

Отдельно рассчитываются:

### ECONOMIC VIABILITY

Можно ли продавать прибыльно.

### MARKET COMPETITIVENESS

Насколько конкурентна публичная buyer price.

Эти две величины нельзя смешивать.

---

## 21. CURRENT EFA EXAMPLE — УФ 001Б

Текущее наблюдение:

`BASE_SELLER_PRICE = 1290 ₽`

`SELLER_ECONOMIC_PRICE / ELASTIC = 660 ₽`

`BUYER_OTHER_PRICE = 436 ₽`

`BUYER_GREEN_PRICE = 393 ₽`

Derived:

`SELLER_PROMO_DISCOUNT = 630 ₽`

`ESTIMATED_OZON_DISCOUNT = 224 ₽`

`GREEN_PRICE_DIFFERENCE = 43 ₽`

До settlement:

`224 ₽ = ESTIMATED`

`43 ₽ funding = UNKNOWN`

Запрещено утверждать:

`points = 267 ₽`

без settlement evidence.

---

## 22. EMPIRICAL VALIDATION

До изменения production Calculator провести минимум следующие проверки.

### CASE #1 — ECONOMIC REVENUE

На первом доставленном Elastic-заказе получить:

- Base price;
- Elastic/action price;
- buyer Other price;
- buyer Green price;
- actual sale amount;
- points;
- Green Price compensation;
- commission;
- logistics;
- processing;
- acquiring;
- advertising;
- net payout.

Проверить decomposition до рубля.

### CASE #2 — COMMISSION BASE

Установить фактическую базу комиссии.

### CASE #3 — POINTS SETTLEMENT

Проверить:

`points accrued → eligible services → points applied → cash payment`.

### CASE #4 — EXCESS POINTS

Проверить денежную выплату остатка.

### CASE #5 — RETURN

Проверить reversal баллов и связанных начислений на первом возврате.

---

## 23. IMPLEMENTATION GATE

До завершения как минимум Validation Cases #1–#3:

`NO PRODUCTION CALCULATOR PATCH`

Разрешены:

- READ-ONLY анализ;
- спецификация;
- reconciliation;
- тестовые расчёты;
- unit tests подтверждённых правил.

После фактической сверки:

создать:

`Ozon Discount & Points Settlement Contract v1.1`

Только после APPROVE v1.1 разрешается менять production Calculator / Price Decision.

---

# FINAL INVARIANTS

`INV-1`
Buyer price не равна seller economic price при наличии компенсируемой скидки.

`INV-2`
Seller-funded discount уменьшает маржу.

`INV-3`
Полностью компенсированная Ozon-funded скидка не уменьшает economic revenue.

`INV-4`
Points не являются дополнительной выручкой поверх seller economic price.

`INV-5`
Погашение расхода баллами не устраняет economic expense.

`INV-6`
Economic P&L и cash settlement — разные модели.

`INV-7`
Только settled data считается финальной.

`INV-8`
Unknown остаётся UNKNOWN до подтверждения.

`INV-9`
Price Decision запрещено строить от Bank price как seller revenue.

`INV-10`
Никакой points-related value не может быть учтён дважды.

---

# WORK / CODEX EXECUTION RULE

При любой последующей задаче, затрагивающей:

- Calculator;
- unit economics;
- Price Decision;
- AI Analyst;
- акции Ozon;
- Elastic Boost;
- Green Price;
- Баллы за скидки;
- комиссии;
- расчёт минимальной цены;
- расчёт маржинальности;

Work/Codex обязан использовать настоящий контракт как обязательный prerequisite.

Если новая задача противоречит контракту:

**STOP**

и вернуть:

`CONTRACT_CONFLICT`

с описанием противоречия.

Если для расчёта отсутствуют settlement-critical данные:

не угадывать.

Вернуть:

`INSUFFICIENT_SETTLEMENT_DATA`.

Не менять production-код, формулы или финансовый контракт без отдельного APPROVE пользователя.
