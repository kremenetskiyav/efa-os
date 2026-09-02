# Ozon Unit Economics — Official Reference V1

## A. Source

- **Primary official source:** https://seller-edu.ozon.ru/libra/finances-documents/additional-information/unit-ekonomika
- **Reviewed at:** `2026-09-02` (Europe/Moscow)
- **Official page date/version:** Ozon Seller Education не показывает дату публикации, дату изменения или номер версии на исследованной странице. `[OFFICIAL_EXPLICIT]`
- **Freshness status:** `CURRENT_AT_REVIEW_DATE / VOLATILE / REVALIDATION_REQUIRED`
- **Required warning:** `REVALIDATE_OFFICIAL_SOURCE_BEFORE_FINANCIAL_LOGIC_CHANGE`
- **Collection note:** содержание проверено в фактическом DOM официальных страниц, включая оглавления, таблицы, примеры, переключаемые временные правила и связанные ссылки. Firecrawl получил от Ozon `403 Forbidden`; этот технический отказ не ограничил браузерное чтение официальных страниц. `[INTERPRETATION]`

## B. Purpose

Этот документ — датированный reference snapshot официальной документации Ozon Seller Education для Work, Codex, AI Analyst, Calculator, Price Decision и других компонентов EFA OS.

Он не является:

- самостоятельным финансовым контрактом;
- подтверждением фактического settlement конкретного заказа;
- тарифным справочником на будущую дату;
- разрешением менять production financial logic.

Официальный раздел «Юнит-экономика» работает в тестовом режиме. `[OFFICIAL_EXPLICIT]`

### Source precedence

Для официальных определений показателей:

```
CURRENT OZON OFFICIAL DOCUMENTATION
>
EFA OFFICIAL REFERENCE SNAPSHOT
>
INTERNAL ASSUMPTIONS
```

Для фактического расчёта конкретного заказа:

```
FINAL OZON SETTLEMENT
>
ORDER FINANCE DETAIL
>
SELLER UNIT ECONOMICS
>
OFFICIAL DOCUMENTATION
>
EFA FORECAST
```

Правила приоритета выше являются policy EFA OS, а не утверждением Ozon. `[INTERPRETATION]`

## C. Official definitions

### C.1. Scope and period of Seller Unit Economics

| Ozon name | Definition | Inputs / period | Exclusions / limitations | Source status |
| --- | --- | --- | --- | --- |
| Юнит-экономика | Инструмент для определения прибыльных и убыточных товаров и выбора цены с учётом производства, маркетинга, продажи и доставки. | Данные по товарам и схемам FBO, FBS, realFBS. | Раздел тестовый; это аналитическое отображение, не финальный settlement. | `OFFICIAL_EXPLICIT` |
| Период | Последние 7 дней, месяц или произвольный период. | Не более 3 месяцев; выбор в пределах 3 лет; данные собираются с 1 июля 2025 года. | Нельзя выбрать единый период длиннее 3 месяцев. | `OFFICIAL_EXPLICIT` |
| Общие расходы | Сумма расходов на все проданные товары одного SKU за период. | Все учитываемые расходы по проданным единицам SKU. | Возвращённые товары исключаются из расчётного количества. | `OFFICIAL_EXPLICIT` |
| Расходы на единицу | Сумма расходов на продажу одного товара. | Учитываемые расходы, нормализованные на одну проданную единицу. | Официальная статья не раскрывает правило распределения каждого агрегированного расхода на единицу. | `OFFICIAL_EXPLICIT` / `OZON_UNCLEAR` |

Дополнительные правила периода:

- Количество отгруженных и доставленных товаров и расходы по ним Ozon показывает по дате создания заказа. `[OFFICIAL_EXPLICIT]`
- За дату возврата Ozon принимает день, когда покупатель передал товар Ozon. `[OFFICIAL_EXPLICIT]`
- Возвращённые товары не учитываются в юнит-экономике: в примере из 20 продаж и 5 возвратов расходы на продажу считаются для 15 товаров. `[OFFICIAL_EXPLICIT]`
- Отмены и невыкупы не входят в показатель «Возвращено товаров». `[OFFICIAL_EXPLICIT]`
- Официальная статья одновременно содержит расходную группу «Возвраты», поэтому точная связь между исключением возвращённой единицы и сохранением/исключением её возвратных расходов не раскрыта. `[INTERPRETATION]`

### C.2. Product and volume fields

| Ozon name | Definition | Inputs | Exclusions / notes | Source |
| --- | --- | --- | --- | --- |
| Схема работы | FBO, FBS или realFBS. | Можно выбрать одну или все схемы. | Расходные компоненты различаются по схеме. | Unit Economics, «Что есть в таблице» |
| Себестоимость | Все затраты на производство или закупку, включая материалы и прочие издержки. | Значение, которое продавец указал в разделе «Цены на товары». | Затраты на площадке не входят. Если продавец не указал себестоимость, Ozon её не показывает. Налоги отдельно не названы. | Unit Economics, «Что есть в таблице» |
| Текущая цена | Стоимость товара в столбце «Ваша цена» раздела «Цены на товары». | Текущее установленное продавцом значение. | Это не определение фактической цены конкретной исторической продажи. | Unit Economics, «Что есть в таблице» |
| Отгружено товаров | Сколько товаров отгружено, передано в доставку или находится в пути. | Дата создания заказа. | Не является количеством завершённых продаж. | Unit Economics, «Что есть в таблице» |
| Доставлено товаров | Сколько товаров доставлено покупателям. | Дата создания заказа. | Не равно финальному количеству после будущих возвратов. | Unit Economics, «Что есть в таблице» |
| Возвращено товаров | Сколько товаров покупатели вернули после доставки. | Дата передачи товара Ozon покупателем. | Отмены и невыкупы исключены. | Unit Economics, «Что есть в таблице» |

Все строки таблицы выше имеют статус `OFFICIAL_EXPLICIT`.

### C.3. Sales and compensation fields

| Ozon name | Definition | Calculation/base | Exclusions / notes | Source status |
| --- | --- | --- | --- | --- |
| Выручка | Сумма продаж без учёта расходов и удержаний Ozon. | Сумма, уплаченная покупателем. | Не равна автоматически установленной продавцом цене; не включает отдельные строки компенсаций. | `OFFICIAL_EXPLICIT` |
| Баллы за скидки | Баллы, начисленные за продажу товаров с дополнительными скидками. | Разница между ценой продавца и фактической суммой продажи; 1 ₽ скидки = 1 балл. | Баллы показываются отдельно от «Выручки»; возврат может сторнировать начисление. | `OFFICIAL_EXPLICIT` |
| Программы партнёров | Сумма, возмещённая продавцу за участие в программах лояльности. | Денежные выплаты партнёров, включая применимую часть компенсации «Зелёной цены». | Не тождественно баллам. | `OFFICIAL_EXPLICIT` |
| Цена продавца | Стоимость товара в отчёте по начислениям после объединения компонентов реализации. | `Выручка + Программа лояльности + Баллы за скидки`. | Термин подтверждён для отчёта по начислениям; статья не называет его отдельным столбцом Unit Economics. | `OFFICIAL_EXPLICIT` |
| Продажи → Итого | База, которую Ozon использует в формулах прибыли Unit Economics. | Официальная статья не публикует общую символическую формулу строки. | Сопоставление с «Ценой продавца» логично, но не должно считаться доказанным без проверки выгрузки Seller. | `OZON_UNCLEAR` |

### C.4. Expense fields

| Ozon name | Official content | Included | Exclusions / limitations | Status |
| --- | --- | --- | --- | --- |
| Вознаграждение Ozon | Вознаграждение за продажу товара. | Ставка по схеме и категории на базе цены продавца после seller-defined скидок и акций, кроме дополнительной скидки за баллы. | Не включает логистику, другие услуги и эквайринг. | `OFFICIAL_EXPLICIT` |
| Эквайринг | Банковская услуга при безналичной оплате. | Фактическая сумма продажи, уплаченная покупателем, × тариф банка покупателя. | Может не возвращаться в отдельных сценариях возврата/отмены. | `OFFICIAL_EXPLICIT` |
| Доставка и размещение | Группа затрат на доставку и размещение. | Обработка отправления при доставке курьером или самостоятельно; логистика и партнёрские услуги realFBS; доставка до места выдачи; стоимость размещения. | Транспорт продавца до склада Ozon не назван отдельным включённым расходом Unit Economics. | `OFFICIAL_EXPLICIT` / `OZON_UNCLEAR` |
| Возвраты | Расходная группа возвратов. | Обратная логистика; обработка возврата и упаковка партнёрами Ozon. | Связь с общим правилом исключения возвращённых товаров не раскрыта. | `OFFICIAL_EXPLICIT` / `OZON_UNCLEAR` |
| Дополнительные услуги | Прочие начисления. | Утилизация, дополнительная обработка ОВХ, операционные ошибки; с 16 февраля 2026 года также штрафы. | Полный закрытый перечень не опубликован в статье Unit Economics. | `OFFICIAL_EXPLICIT` |
| Продвижение и реклама | Расходы на перечисленные инструменты продвижения. | «Оплата за клик», «Оплата за заказ», «Звёздные товары», «Продвижение брендов». | Точное правило распределения CPC и брендовых расходов на SKU/заказ в Unit Economics не опубликовано. | `OFFICIAL_EXPLICIT` / `OZON_UNCLEAR` |

### C.5. Result fields

| Ozon name | Definition | Formula/base | Limitations | Status |
| --- | --- | --- | --- | --- |
| Прибыль за единицу товара | Прибыль на одну проданную единицу. | «Продажи → Итого» минус себестоимость проданных товаров и все расходы таблицы, на единицу. | Налоги не названы отдельной строкой; скрытые пользователем столбцы продолжают участвовать. | `OFFICIAL_EXPLICIT` |
| Доля от продаж | Процент прибыли относительно продаж, рассчитываемый на единицу. | В примере: `Прибыль за единицу / Выручка на единицу`. | Общая формула для заказа с баллами и выплатами партнёров не дана; официальный текст о базе сформулирован неоднозначно. | `OFFICIAL_EXAMPLE` / `OZON_UNCLEAR` |
| Прибыль за период | Прибыль по всем проданным товарам одного SKU за период. | «Продажи → Итого» минус себестоимость и все расходы таблицы. | Не является документированным cash settlement периода. | `OFFICIAL_EXPLICIT` |
| Индекс цен | Насколько цена выгодна покупателям относительно конкурентов. | Формула в ветке Unit Economics не дана. | Не является прибылью или маржой. | `OFFICIAL_EXPLICIT` |
| Доступность товаров | Хватает ли товаров для покрытия спроса. | Формула в ветке Unit Economics не дана. | Не является финансовым settlement-показателем. | `OFFICIAL_EXPLICIT` |

### C.6. Terms not used as official Unit Economics metrics

- `Маржа` / `маржинальность`: исследованная статья использует термин «Доля от продаж», а не отдельный показатель «маржинальность». `[OFFICIAL_EXPLICIT]`
- `ROI` / `рентабельность`: отдельная формула в исследованной ветке не опубликована. `[OFFICIAL_EXPLICIT]`
- `Налог`: отдельная строка расходов Unit Economics не указана. Отсутствие строки нельзя интерпретировать как нулевой налог. `[OFFICIAL_EXPLICIT]` / `[INTERPRETATION]`
- `accruals_for_sale`: такое имя поля в исследованных официальных статьях не используется. `[OFFICIAL_EXPLICIT]`
- `Ожидаемые расходы на невыкуп`: отдельного прогнозного показателя в Seller Unit Economics нет. `[OFFICIAL_EXPLICIT]`

## D. Official formulas

В этом разделе нет формул, придуманных EFA OS.

### D.1. Unit Economics formulas

1. `Прибыль за единицу товара = Продажи → Итого − себестоимость проданных товаров − все расходы таблицы`, нормализовано на одну проданную единицу. `[OFFICIAL_EXPLICIT]`
2. `Прибыль за период = Продажи → Итого − себестоимость − все расходы таблицы` для всех проданных товаров одного SKU. `[OFFICIAL_EXPLICIT]`
3. Официальный пример:
   - `Количество продаж = 19 − 3 возврата = 16`. `[OFFICIAL_EXAMPLE]`
   - `Выручка = 16 × 1 020 ₽ = 16 320 ₽`. `[OFFICIAL_EXAMPLE]`
   - `Прибыль за период = 16 320 − 505 × 16 − 8 063 = 177 ₽`. `[OFFICIAL_EXAMPLE]`
   - `Прибыль за единицу = 177 ÷ 16 = 11 ₽` после округления, показанного Ozon. `[OFFICIAL_EXAMPLE]`
   - `Доля от продаж = 11 ÷ (16 320 ÷ 16) = 1,1%`. `[OFFICIAL_EXAMPLE]`

### D.2. Price and compensation formulas

1. `Цена продавца = Выручка + Программа лояльности + Баллы за скидки`. Формула следует из прямого правила отчёта по начислениям: сумма этих трёх данных образует «Цену продавца». `[OFFICIAL_EXPLICIT]`
2. `Баллы за скидки по продаже = Цена продавца − фактическая сумма продажи`, где `1 ₽ скидки = 1 балл`. `[OFFICIAL_EXPLICIT]`
3. `Всего начислено баллов = Баллы за скидки в блоке «Реализовано» − Баллы за скидки в блоке «Возвращено покупателем»`. `[OFFICIAL_EXPLICIT]`

### D.3. Commission and acquiring formulas

1. `Вознаграждение Ozon = цена, установленная продавцом, с учётом всех скидок и акций продавца, кроме дополнительной скидки за Баллы, × ставка вознаграждения`. Цена включает применимый НДС. `[OFFICIAL_EXPLICIT]`
2. `Эквайринг = фактическая сумма продажи, уплаченная покупателем, × тариф банка покупателя`. `[OFFICIAL_EXPLICIT]`

### D.4. Advertising formulas

1. `Средняя стоимость клика = Расход на продвижение / Количество кликов`. `[OFFICIAL_EXPLICIT]`
2. CPC: `ДРР в продвижении = Расходы на продвижение / Продажи в продвижении`. `[OFFICIAL_EXPLICIT]`
3. CPC: `ДРР = Расходы на продвижение / Стоимость всех заказанных товаров с продвижением и без него`. `[OFFICIAL_EXPLICIT]`
4. CPO: `ДРР в продвижении = Расходы на продвижение / Продажи в продвижении`. `[OFFICIAL_EXPLICIT]`
5. В детализации скидок: `Доля рекламных расходов = (Расходы «Оплата за клик» + Расходы «Оплата за заказ») / Общая сумма полученных заказов за последние 30 дней × 100%`. `[OFFICIAL_EXPLICIT]`

ДРР рекламных кабинетов и «Доля от продаж» Unit Economics — разные показатели и не должны подменять друг друга. `[INTERPRETATION]`

## E. Price / discount / points model

### E.1. Official model

- Дополнительную скидку устанавливает Ozon, но официальная статья говорит, что скидка предоставляется за счёт продавца и от его имени; разница возвращается баллами. `[OFFICIAL_EXPLICIT]`
- Для продавца `1 ₽` такой скидки компенсируется `1 баллом`, который даёт `1 ₽` скидки на применимые услуги площадки. `[OFFICIAL_EXPLICIT]`
- Выручка Unit Economics основана на сумме, фактически уплаченной покупателем; баллы и программы партнёров показываются отдельными строками. `[OFFICIAL_EXPLICIT]`
- Это исключает трактовку баллов как дополнительной выручки поверх полной «Цены продавца». `[DERIVED_FROM_OFFICIAL_FORMULA]`

### E.2. Green Price

- «Зелёная цена» — цена при оплате продуктами банков-партнёров. Скидка предоставляется за счёт продавца и от его имени. `[OFFICIAL_EXPLICIT]`
- Банк-партнёр может компенсировать скидку полностью рублями или частично; непокрытая часть компенсируется баллами. `[OFFICIAL_EXPLICIT]`
- При наличии акции «Зелёная цена» рассчитывается от конечной цены по акции. `[OFFICIAL_EXPLICIT]`
- Официальный пример: `1 000 ₽ → цена по акции 900 ₽ → Зелёная цена 882 ₽`; разница `18 ₽` может состоять из `10 ₽` выплаты партнёра и `8 баллов`. `[OFFICIAL_EXAMPLE]`
- Рублёвая компенсация видна как «Выплаты по механикам лояльности партнёров» в отчёте о реализации; детализация — в отчёте по механикам лояльности партнёров. `[OFFICIAL_EXPLICIT]`

### E.3. Ozon term → EFA OS term mapping

| Ozon term | EFA OS term | Match status | Reason |
| --- | --- | --- | --- |
| Ваша цена / Текущая цена | `BASE_SELLER_PRICE` | `CLOSE_MATCH` | Ozon показывает текущий snapshot; EFA хранит экономический слой, который должен быть привязан ко времени заказа. |
| Цена с учётом скидок и акций продавца, кроме скидки за Баллы | `SELLER_ECONOMIC_PRICE` | `EXACT_MATCH` | Это официальная база вознаграждения и цена до дополнительной компенсируемой скидки. |
| Цена по акции | `SELLER_ECONOMIC_PRICE` | `CLOSE_MATCH` | Совпадает, если все применённые к цене акции финансируются продавцом и нет иных seller-funded слоёв. |
| Сумма, уплаченная покупателем / фактическая сумма продажи | `BUYER_OTHER_PRICE` | `CLOSE_MATCH` | Совпадает для обычной оплаты; при Green Price соответствует `BUYER_GREEN_PRICE`. |
| Стоимость с «Зелёной ценой» | `BUYER_GREEN_PRICE` | `EXACT_MATCH` | Публичная цена при соответствующем способе оплаты. |
| Дополнительная скидка, за которую начисляем баллы | `OZON_FUNDED_DISCOUNT` | `DIFFERENT_CONCEPT` | EFA-имя описывает экономическую компенсацию, а Ozon юридически называет скидку предоставленной за счёт продавца и от его имени. |
| Баллы за скидки | `OZON_POINTS` | `EXACT_MATCH` | 1 ₽ скидки = 1 балл; возможны начисления и сторно. |
| Программы партнёров / Выплаты по механикам лояльности партнёров | `GREEN_PRICE_CASH_COMPENSATION` | `CLOSE_MATCH` | Официальная строка шире Green Price и может включать другие партнёрские программы. |
| Цена продавца в отчёте по начислениям | `SELLER_ECONOMIC_PRICE` | `CLOSE_MATCH` | Официально равна сумме buyer cash, partner compensation и points; требуется order-level проверка границ термина. |
| Вознаграждение Ozon | `COMMISSION_AMOUNT` | `EXACT_MATCH` | Сумма вознаграждения; ставка и база должны храниться отдельно. |
| Доля от продаж | `CONTRIBUTION_MARGIN` | `CLOSE_MATCH` | Пример использует unit profit / unit sales; общая база при компенсациях не опубликована. |
| Продажи → Итого | экономическая выручка EFA | `CLOSE_MATCH` | Используется в прибыли, но официальная общая формула строки не раскрыта. |
| `accruals_for_sale` | `accruals_for_sale` | `NO_DIRECT_EQUIVALENT` | Поле не используется в исследованных официальных статьях. |

## F. Cost model

### F.1. Commission

- База: установленная продавцом цена с учётом его скидок и акций, кроме дополнительной скидки за Баллы. `[OFFICIAL_EXPLICIT]`
- Ставка: действующая в момент заказа; начисление происходит, когда товар получает статус «Доставлен». `[OFFICIAL_EXPLICIT]`
- Возврат: ранее списанное вознаграждение возвращается. `[OFFICIAL_EXPLICIT]`
- Невыкуп или отмена: вознаграждение не списывается. `[OFFICIAL_EXPLICIT]`
- Конкретная ставка зависит от категории, типа товара, схемы и действующих условий; snapshot ставки нельзя переносить в будущие расчёты без проверки. `[OFFICIAL_EXPLICIT]` / `[INTERPRETATION]`

### F.2. Logistics

Официальная Unit Economics агрегирует, а не публикует полную тарифную модель.

- FBO: логистика включает обработку/подготовку товара, перевозку между кластерами и доставку до места выдачи; в Unit Economics также отражается размещение. `[OFFICIAL_EXPLICIT]`
- FBS: возможны доставка до СЦ, обработка отправления или грузоместа, логистика и доставка до места выдачи. На отдельных способах отгрузки обработка включена в логистику, на партнёрских ПВЗ/ППЗ может перевыставляться отдельно. `[OFFICIAL_EXPLICIT]`
- realFBS: Ozon может показывать партнёрские услуги/перевыставления, агентское вознаграждение или сервисный сбор; собственные транспортные расходы продавца Ozon автоматически не знает. `[OFFICIAL_EXPLICIT]`
- Поставка продавцом на склад Ozon не названа в составе Unit Economics как отдельная расходная строка. Нельзя считать её автоматически включённой. `[OFFICIAL_EXPLICIT]` / `[INTERPRETATION]`
- Предварительные логистические значения могут отличаться от итоговой стоимости по факту услуги и фактического объёма. `[OFFICIAL_EXPLICIT]`

### F.3. Returns, non-buyouts and cancellations

- «Возврат» — покупатель получил товар, после чего вернул его. `[OFFICIAL_EXPLICIT]`
- «Невыкуп» — покупатель отказался от части товаров при получении; невыкупленные позиции переходят в «Отменено». `[OFFICIAL_EXPLICIT]`
- «Отмена/невостреб» — покупатель не получил отправление, оно перешло в «Отменено». `[OFFICIAL_EXPLICIT]`
- В Unit Economics отмены и невыкупы не входят в «Возвращено товаров». `[OFFICIAL_EXPLICIT]`
- Отдельная прогнозная формула ожидаемого невыкупа в официальной Unit Economics не опубликована. `[OFFICIAL_EXPLICIT]`

### F.4. Advertising

- Unit Economics включает CPC, CPO, «Звёздные товары» и «Продвижение брендов». `[OFFICIAL_EXPLICIT]`
- CPC начисляется в момент клика; закрывающие документы выставляются раз в месяц. `[OFFICIAL_EXPLICIT]`
- CPO начисляется в момент оплаты заказа покупателем; заказ может быть атрибутирован после отключения продвижения, если попадает в официальное 30-дневное окно. `[OFFICIAL_EXPLICIT]`
- CPC-статистика атрибутирует заказ в течение 10 дней после клика или 30 дней после добавления из продвигаемой позиции в корзину/избранное; заказ появляется после оплаты. `[OFFICIAL_EXPLICIT]`
- Рекламная статистика CPC/CPO сохраняет оплаченные заказы, которые позже отменены или возвращены. Это отличается от правила Unit Economics об исключении возвращённых товаров. `[OFFICIAL_EXPLICIT]` / `[INTERPRETATION]`
- «Звёздные товары» после бесплатного периода тарифицируются процентом от установленной продавцом цены каждого товара, заказанного в период использования услуги. `[OFFICIAL_EXPLICIT]`
- Точная SKU/order-алокация CPC, «Продвижения брендов» и задержка их появления именно в Unit Economics не опубликованы. `[OZON_UNCLEAR]`

## G. Period / settlement rules

### G.1. Unit Economics attribution

- Продажи/количество и расходы связываются с датой создания заказа; возврат — с датой передачи возвращаемого товара Ozon. `[OFFICIAL_EXPLICIT]`
- Unit Economics доступна за агрегированный период и не объявлена финальным закрывающим документом. `[OFFICIAL_EXPLICIT]` / `[INTERPRETATION]`
- Текущая цена является текущим значением из «Цен на товары», поэтому её нельзя автоматически считать исторической ценой каждой продажи периода. `[DERIVED_FROM_OFFICIAL_FORMULA]`

### G.2. Points lifecycle from 1 July 2026

- Начисленные баллы отражаются в реальном времени. `[OFFICIAL_EXPLICIT]`
- Списанные баллы отражаются после закрытия периода: в первые 5 рабочих дней следующего месяца, но не позднее 8-го числа. `[OFFICIAL_EXPLICIT]`
- После закрытия месяца баллы дают скидку до 99%: сначала на вознаграждение за продажу, затем пропорционально на доставку, возвраты и применимую часть других собственных услуг Ozon. `[OFFICIAL_EXPLICIT]`
- Услуги партнёров-исполнителей не входят в эту часть списания; Ozon приводит примеры: эквайринг, доставка до места выдачи, обработка возвратов. `[OFFICIAL_EXPLICIT]`
- Если баллов больше стоимости применимых услуг, остаток перечисляется рублями и отражается как премия. `[OFFICIAL_EXPLICIT]`
- Если баллов меньше, остаток стоимости услуг удерживается рублями. `[OFFICIAL_EXPLICIT]`
- Возврат сторнирует ранее начисленные баллы; возврат следующего месяца уменьшает баллы следующего периода и может сформировать отрицательный итог. `[OFFICIAL_EXPLICIT]`
- Финальный размер вознаграждения, услуг, начисленных и списанных баллов виден в закрывающих документах в начале следующего периода. `[OFFICIAL_EXPLICIT]`
- Документы отражают взаиморасчёты в рублях; сами начисленные/потраченные баллы не отражаются в бухгалтерском учёте и налоговой декларации как баллы. `[OFFICIAL_EXPLICIT]`

### G.3. Provisional vs final

| Layer | Official signal | EFA status |
| --- | --- | --- |
| Начисленные баллы текущего периода | Реальное время; возможны последующее сторно и перерасчёт | `PROVISIONAL / ESTIMATED_FOR_SETTLEMENT` |
| Списанные баллы после закрытия | Появляются после закрытия периода | `SETTLED_FOR_PERIOD`, но при последующем возврате возможна корректировка |
| Unit Economics current period | Агрегированное аналитическое отображение; finality не заявлена | `PROVISIONAL` |
| Закрывающие документы | Финальные суммы периода по опубликованному lifecycle | `CONFIRMED_SETTLEMENT`, с учётом последующих УКД/корректировок |

Статусы EFA в правом столбце — интерпретация для безопасной работы системы. `[INTERPRETATION]`

## H. EFA OS mapping and gap analysis

### H.1. Settlement Contract V1

| Area | Status | Finding |
| --- | --- | --- |
| Buyer price is not seller economic revenue without decomposition | `ALIGNED` | Ozon отдельно показывает buyer-paid «Выручку», баллы и программы партнёров. |
| No double counting of points | `ALIGNED` | Официальная формула «Цена продавца» складывает компоненты один раз. |
| 1 point = 1 ₽ economic compensation | `ALIGNED` | Ozon прямо устанавливает 1 ₽ скидки = 1 балл = 1 ₽ скидки на услуги. |
| `OZON_FUNDED_DISCOUNT` naming | `CONFLICT` | Ozon говорит, что дополнительная скидка предоставлена за счёт продавца и от его имени, хотя разница компенсируется баллами/партнёром. |
| Green Price decomposition | `ALIGNED` | Официально возможны рублёвая компенсация банка и баллы в любой комбинации. |
| Unknown Green funding before settlement | `ALIGNED` | Публичной разницы цен недостаточно для определения cash/points split. |
| Points order and eligible services | `ALIGNED` | Текущая документация с 1 июля 2026 года подтверждает порядок и исключение partner-executor услуг. |
| Economic P&L versus cash settlement | `PARTIALLY_ALIGNED` | Ozon подтверждает рублёвый settlement после скидки баллами, но не определяет внутренний EFA economic-cost view. |
| Returns/reversals | `ALIGNED` | Начисления сторнируются, в том числе в следующем периоде. |
| Excess points cash premium | `ALIGNED` | Остаток выплачивается рублями как премия. |
| Commission base | `PARTIALLY_ALIGNED` | Официальная база теперь описана явно; фактическая ставка и сумма всё равно требуют order settlement. |
| Unit profit | `PARTIALLY_ALIGNED` | Структура «sales total − COGS − all table costs» согласуется, но Ozon не показывает налоги и expected non-buyout как отдельные строки. |
| Contribution margin denominator | `OZON_UNCLEAR` | Пример использует buyer-paid revenue; общая база при points/partner compensation не опубликована. |
| CPC/CPO separation | `ALIGNED` | Инструменты и их моменты начисления различены. |
| CPC allocation and lag in Unit Economics | `OZON_UNCLEAR` | Официальная SKU/order-алокация не дана. |
| Source-of-truth priority | `ALIGNED` | Закрывающие документы и order finance detail дают более сильное settlement evidence, чем аналитическая Unit Economics. |

### H.2. Ozon Price Calculator V1 architecture

| Area | Status | Finding |
| --- | --- | --- |
| `seller_price` as base price input | `CONFLICT` | Архитектура V1 запрещает `marketing_seller_price` как forecast input, а более новый Settlement Contract использует цену после seller-funded скидок. Официальная база вознаграждения — цена после скидок/акций продавца. Требуется отдельное решение, не patch этого reference. |
| Commission percentage and base | `PARTIALLY_ALIGNED` | Формула процента корректна только при актуальной ставке и официальной price base; исторический Golden checkpoint не является текущим тарифом. |
| Logistics fixed monetary inputs | `PARTIALLY_ALIGNED` | Допустимо для versioned snapshot, но официальные тарифы зависят от даты, цены, объёма, маршрута и способа оказания услуги. |
| Expected non-buyout formula | `NO_DIRECT_EQUIVALENT` | Это прогнозная модель EFA/EcomUnit, не показатель официальной Seller Unit Economics. |
| Tax line | `DIFFERENT_CONCEPT` | Calculator включает налог; официальная Unit Economics не публикует отдельную налоговую строку. |
| Advertising cost | `NOT_IMPLEMENTED` | В основной формуле V1 нет отдельного CPC/CPO/other promotion input; `other_expenses` не обеспечивает официальную семантику и provenance. |
| Discount points and partner loyalty | `NOT_IMPLEMENTED` | Архитектура V1 не декомпозирует buyer payment, points и partner compensation. |
| Green Price | `NOT_IMPLEMENTED` | В архитектуре V1 нет official cash/points funding split. |
| Settlement statuses | `NOT_IMPLEMENTED` | V1 — forecast calculator; official provisional/final lifecycle не моделируется. |

`STOP / CONTRACT_CONFLICT`: конфликт `seller_price` между Calculator V1 и Settlement Contract V1 нельзя разрешать изменением production logic в рамках этого исследования.

## I. Known ambiguities

1. Ozon не публикует формулу «Продажи → Итого» непосредственно на странице Unit Economics. `[OZON_UNCLEAR]`
2. Не указано, использует ли «Доля от продаж» buyer-paid «Выручку» или полный compensated sales total при баллах/Green Price. `[OZON_UNCLEAR]`
3. Не раскрыто, какие баллы на вкладке Unit Economics считаются provisional и какие уже прошли закрытие периода. `[OZON_UNCLEAR]`
4. Статья говорит, что баллы начисляются после оформления заказа или при статусе «Доставлено»; единый обязательный trigger не указан. `[OZON_UNCLEAR]`
5. Не раскрыта точная алокация CPC и брендовых расходов на SKU, заказ и единицу в Unit Economics. `[OZON_UNCLEAR]`
6. Не указана задержка появления рекламных расходов именно в Unit Economics. `[OZON_UNCLEAR]`
7. Правило исключения возвращённых товаров сосуществует с отдельной строкой расходов «Возвраты»; точная агрегация не описана. `[OZON_UNCLEAR]`
8. Не указано, входит ли доставка поставки FBO до склада Ozon в какие-либо автоматические строки Unit Economics. `[OZON_UNCLEAR]`
9. «Текущая цена» — current snapshot; не указано, как UI сопоставляет её с историческими транзакциями периода. `[OZON_UNCLEAR]`
10. Официальные страницы не используют поле `accruals_for_sale`. `[OZON_UNCLEAR]`
11. Страница не показывает дату/версию; staleness можно контролировать только датой review и повторной проверкой. `[OFFICIAL_EXPLICIT]`
12. В детализации скидок встречается официальный текст «акция “Баллы без скидки”» в формулах выручки, хотя контекст страницы — «Баллы за скидки»; это нельзя нормализовать без подтверждения Ozon. `[OFFICIAL_EXPLICIT]` / `[INTERPRETATION]`

## J. Implementation warnings

1. Не использовать buyer-paid «Выручку» как полную seller economic revenue при наличии points/partner compensation. `[INTERPRETATION]`
2. Не прибавлять баллы поверх уже полной «Цены продавца». `[DERIVED_FROM_OFFICIAL_FORMULA]`
3. Не считать всю разницу Green Price баллами: часть или вся сумма может быть выплачена банком-партнёром рублями. `[DERIVED_FROM_OFFICIAL_FORMULA]`
4. Не считать «Текущую цену» исторической ценой каждой продажи. `[INTERPRETATION]`
5. Не использовать рекламные «Продажи» и ДРР как эквивалент продаж Unit Economics: рекламная статистика сохраняет отмены и возвраты. `[INTERPRETATION]`
6. Не считать скрытый столбец исключённым из прибыли: Ozon продолжает учитывать скрытые столбцы. `[OFFICIAL_EXPLICIT]`
7. Не считать отсутствие налоговой строки нулевым налогом. `[INTERPRETATION]`
8. Не переносить тарифы, ставки и даты этого snapshot в production без повторной проверки официального источника. `[INTERPRETATION]`
9. Не превращать `OZON_UNCLEAR` в формулу Calculator или Price Decision. `[INTERPRETATION]`
10. Не менять Calculator, Price Decision, AI Analyst, settlement contract, PostgreSQL, n8n или Ozon на основании этого reference без отдельного approval и empirical settlement validation. `[INTERPRETATION]`

`REVALIDATE_OFFICIAL_SOURCE_BEFORE_FINANCIAL_LOGIC_CHANGE`

## K. Official source links

Только официальные источники Ozon:

1. Юнит-экономика — https://seller-edu.ozon.ru/libra/finances-documents/additional-information/unit-ekonomika
2. Баллы за скидки — https://seller-edu.ozon.ru/libra/finances-documents/additional-information/bally-za-skidki
3. Детализация по скидкам, за которые начисляем баллы — https://seller-edu.ozon.ru/libra/finances-documents/additional-information/bally-za-skidki-vygody
4. Работа с финансами в личном кабинете / Экономика магазина — https://seller-edu.ozon.ru/libra/finances-documents/calculations-documents/work-with-finance
5. Вознаграждение Ozon за продажу товаров — https://seller-edu.ozon.ru/libra/commissions-tariffs/commissions-tariffs-ozon/komissii-tovary-uslugi
6. Расходы на доставку до покупателя — https://seller-edu.ozon.ru/libra/commissions-tariffs/commissions-tariffs-ozon/rashody-na-dostavku
7. Расходы при возвратах, невыкупах, отменах — https://seller-edu.ozon.ru/libra/commissions-tariffs/commissions-tariffs-ozon/rashody-na-otmenu-vozvraty
8. Что такое «Оплата за клик» — https://seller-edu.ozon.ru/libra/how-to-sell-effectively/advertising-of-goods/oplata-za-klik/chto-takoe-oplata-za-klik
9. Результаты кампании «Оплата за клик» — https://seller-edu.ozon.ru/libra/how-to-sell-effectively/advertising-of-goods/oplata-za-klik/rezultaty-v-oplate-za-klik
10. Что такое «Оплата за заказ» — https://seller-edu.ozon.ru/libra/how-to-sell-effectively/advertising-of-goods/oplata-za-zakaz/chto-takoe-oplata-za-zakaz
11. Результаты «Оплаты за заказ» — https://seller-edu.ozon.ru/libra/how-to-sell-effectively/advertising-of-goods/oplata-za-zakaz/rezultaty-oplata-za-zakaz
12. Программа лояльности «Зелёная цена» — https://seller-edu.ozon.ru/libra/how-to-sell-effectively/loyalty/zelenaya-cena
13. Программа лояльности «Звёздные товары» — https://seller-edu.ozon.ru/libra/how-to-sell-effectively/loyalty/star-goods

## Review state

- Reference completeness: `READY_FOR_REVIEW`
- Production implementation: `NOT_AUTHORIZED`
- Contract implementation gate: unchanged
- Final marker: `OZON_UNIT_ECONOMICS_OFFICIAL_REFERENCE_READY_FOR_REVIEW`
