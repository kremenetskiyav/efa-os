# OZON-CONTENT-COPY-2026-08-17

Status: `FACT_COLLECTION / EVIDENCE_REGISTRY`

Terminology: `SUSPECTED_UNAUTHORIZED_CONTENT_REUSE` and
`OBSERVED_CONTENT_CONTRADICTION`. Nothing in this incident record establishes
copyright infringement, counterfeit goods, fraud or exclusive rights.

## Incident boundary

On 2026-08-17 the owner observed Ozon's `Есть дешевле` surface for EFA offer
`УФ 004Б` and identified four third-party product cards that appear to reuse EFA
product-card material. Three URLs identify `УФ 004Б`; the fourth explicitly
identifies `УФ 005Б` and is classified accordingly. No complaint, seller
contact, Ozon contact, authenticated UI scraping or commercial change has been
made.

Owner screenshots reportedly show some combination of EFA/ЭФА branding,
packaging, article codes, OEM numbers, product photography, infographic layout
and `Сделано в России`. At least one observed third-party card also showed
China-related country/manufacturer context. The specific card carrying that
contradiction has not yet been assigned, so it remains an incident-level
`OBSERVED_CONTENT_CONTRADICTION / NEEDS_CAPTURE`.

## Canonical EFA product map

The values below come from the production `products` mapping. `product_id` is
the Seller API product identifier. It is not treated as a public Ozon card ID.

| offer_id | Seller API product_id | SKU | public original card ID/URL | current known title |
|---|---:|---:|---|---|
| УФ 001Б | 4861934525 | 4601821825 | NOT_CONFIRMED | Салонный угольный фильтр для Honda Civic 8 (FD,FA), Civic IX (FK_) / CR-V 3 /4, Accord 8 / 9, Фильтр салона Хонда Цивик, Аккорд |
| УФ 002Б | 4861934539 | 4642158029 | NOT_CONFIRMED | Салонный угольный фильтр для Volkswagen Polo 5 / 6 Sedan, Skoda Rapid 1 / 2, Fabia 2 / 3, Audi A1 8X, Фильтр салона Поло 5 Поло Седан 6 Седан, Шкода Рапид, Фабиа, Ауди А1 |
| УФ 003Б | 4861934541 | 4671345564 | NOT_CONFIRMED | Салонный угольный фильтр для Hyundai Elantra AD, Tucson 3, Kia Ceed 3, Cerato 4, Sportage 4, Фильтр салона Хендай Элантра ад, Туксон, Киа Сид, Церато, Спортейдж |
| УФ 004Б | 4861934500 | 4642180551 | NOT_CONFIRMED | Салонный угольный фильтр для Audi A3 (8V), Skoda Octavia A7/A8, Volkswagen Tiguan 2, Passat B8, Golf 7 / 8, Jetta 7, Фильтр салона Ауди а3 Шкода Октавиа а7 а8 Фольксваген Тигуан Пассат Гольф Джетта |
| УФ 005Б | 4861934542 | 4671328307 | NOT_CONFIRMED | Салонный угольный фильтр для Citroen C4 1 и 2, Peugeot 308 1, Фильтр салона Ситроен С4 1 2, Пежо 308 |

## Scale assessment

Confirmed owner-supplied suspected-card coverage is:

| offer | confirmed suspected cards | status |
|---|---:|---|
| УФ 001Б | 0 | NOT_CHECKED |
| УФ 002Б | 0 | NOT_CHECKED |
| УФ 003Б | 0 | NOT_CHECKED |
| УФ 004Б | 3 | OWNER_CONFIRMED |
| УФ 005Б | 1 | OWNER_CONFIRMED |

This does not prove that the first three offers are unaffected. Automated
public discovery is not claimed: Ozon anti-bot controls must not be bypassed,
and authenticated Seller UI scraping is prohibited. Scale completion therefore
requires the manual checklist below.

## Owner evidence inventory

Available from owner but not yet collected:

- `ORIGINAL_SOURCE_FILES`;
- `DATED_TELEGRAM_CORRESPONDENCE`;
- `DESIGN_ITERATIONS`;
- `EARLIER_EFA_PUBLICATION` evidence;
- screenshots supporting the four supplied cases.

Do not resave or alter original design files. Preserve originals, filesystem
timestamps and exports outside Git.

## Minimal owner checklist

For each of the five canonical offers:

1. Open the original EFA card and record its URL, public card ID, seller name,
   date and time.
2. Open `Есть дешевле` or the public product results manually and record every
   suspected card URL and seller URL without relying on title-only matching.
3. Save a full-page screenshot with the browser URL visible.
4. Save the copied-looking images separately where the UI provides the original
   media, without editing or recompressing them.
5. Capture article code, EFA branding, packaging, OEM numbers, country,
   manufacturer and characteristics.
6. Record `NOT_FOUND` explicitly where no suspected card is observed.

For EFA originals, preserve source artwork, original metadata, dated Telegram
discussion/iterations and the earliest known publication evidence.

## Preservation and support readiness

Local-only evidence root:

`C:\Users\Andrey\.efa-os\evidence\ozon_content_copy\2026-08-17\`

Subdirectories: `originals`, `third_party`, `telegram`, `screenshots`,
`exports`. Nothing from these directories belongs in Git.

Owner-observed Ozon support guidance says a complaint should include the
original card link, suspected card link, a signed claim and evidence supporting
rights to the content. This is `OWNER_OBSERVED_SUPPORT_GUIDANCE`, not an
independently verified legal policy. The package is `NOT_READY`: original EFA
card URLs/IDs, immutable case captures and rights/provenance evidence are still
missing. No complaint draft is part of this phase.

