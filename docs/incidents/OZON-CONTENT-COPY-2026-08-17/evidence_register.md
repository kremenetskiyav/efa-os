# Evidence register

Discovery date: `2026-08-17`

Incident classification: `SUSPECTED_UNAUTHORIZED_CONTENT_REUSE`

Legal status for every case: `NOT_ASSESSED`

Owner evidence references below are registry placeholders only. Binary evidence
must remain under the local evidence root outside Git.

## Cases

| case_id | affected offer | original EFA card | original EFA identifier | third-party seller | seller URL | suspected card URL | third-party card ID | observed price | evidence status | owner evidence reference | priority |
|---|---|---|---|---|---|---|---:|---:|---|---|---|
| OCC-2026-08-17-01 | УФ 004Б | NEEDS_CAPTURE | SKU 4642180551; public original card ID NOT_CONFIRMED | Генерал Джо&Pg№8 | https://www.ozon.ru/seller/general-dzho-pg-8-3938431/ | https://www.ozon.ru/product/efa-filtr-salonnyy-art-uf-004b-1-sht-5168563559/ | 5168563559 | 391 RUB | OWNER_CONFIRMED / NEEDS_CAPTURE / NEEDS_COMPARISON | `screenshots/OCC-2026-08-17-01-*` | P1 |
| OCC-2026-08-17-02 | УФ 004Б | NEEDS_CAPTURE | SKU 4642180551; public original card ID NOT_CONFIRMED | Восточный выбор&Ry№7 | https://www.ozon.ru/seller/vostochnyy-vybor-ry-7-3548885/products/?text=фильтр+салон | https://www.ozon.ru/product/efa-filtr-salonnyy-art-uf-004b-1-sht-5156853618/ | 5156853618 | 445 RUB | OWNER_CONFIRMED / NEEDS_CAPTURE / NEEDS_COMPARISON | `screenshots/OCC-2026-08-17-02-*` | P2 |
| OCC-2026-08-17-03 | УФ 004Б | NEEDS_CAPTURE | SKU 4642180551; public original card ID NOT_CONFIRMED | верхушка айсберга & KD№7 | https://www.ozon.ru/seller/verhushka-aysberga-kd-7-3938303/ | https://www.ozon.ru/product/filtr-salonnyy-art-uf-004b-1-sht-5153733382/ | 5153733382 | 391 RUB | OWNER_CONFIRMED / NEEDS_CAPTURE / NEEDS_COMPARISON | `screenshots/OCC-2026-08-17-03-*` | P1 |
| OCC-2026-08-17-04 | УФ 005Б | NEEDS_CAPTURE | SKU 4671328307; public original card ID NOT_CONFIRMED | Хоге & Lb№5 | https://www.ozon.ru/seller/hoge-lb-5-3495021/ | https://www.ozon.ru/product/efa-filtr-salonnyy-art-uf-005b-1-sht-5007822312/ | 5007822312 | 445 RUB | OWNER_CONFIRMED / NEEDS_CAPTURE / NEEDS_COMPARISON | `screenshots/OCC-2026-08-17-04-*` | P2 |

All four records carry `legal_status=NOT_ASSESSED`. Their common observed-copy
indicator is the owner's report of apparently reused EFA product-card material.
Per-case image-element attribution is not yet captured; it must not be inferred
from the URL title alone. One unassigned incident screenshot reportedly contains
an `OBSERVED_CONTENT_CONTRADICTION` between China-related product context and
EFA artwork stating `Сделано в России`.

## Seller correlation

| seller | seller ID derived from supplied URL | affected offers | suspected cards |
|---|---:|---|---:|
| Генерал Джо&Pg№8 | 3938431 | УФ 004Б | 1 |
| Восточный выбор&Ry№7 | 3548885 | УФ 004Б | 1 |
| верхушка айсберга & KD№7 | 3938303 | УФ 004Б | 1 |
| Хоге & Lb№5 | 3495021 | УФ 005Б | 1 |

No supplied seller ID occurs across multiple EFA offers. This register does not
infer common ownership or coordination between seller accounts.

## Content-comparison matrix

`MATCH_OBSERVED` below is used only for the article code visible in the supplied
card URL. All image/content claims await case-specific capture and side-by-side
review.

| case_id | MAIN_IMAGE | PACKAGING | EFA_LOGO | ARTICLE_CODE | OEM_NUMBERS | PRODUCT_PHOTO | INFOGRAPHIC_TEXT | INFOGRAPHIC_LAYOUT | DESCRIPTION_TEXT | CHARACTERISTICS |
|---|---|---|---|---|---|---|---|---|---|---|
| OCC-2026-08-17-01 | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | MATCH_OBSERVED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED |
| OCC-2026-08-17-02 | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | MATCH_OBSERVED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED |
| OCC-2026-08-17-03 | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | MATCH_OBSERVED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED |
| OCC-2026-08-17-04 | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | MATCH_OBSERVED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED | NOT_CHECKED |

## Priority rationale

- `P1`: cases 01 and 03 have the lowest owner-observed price (391 RUB) in the
  supplied `Есть дешевле` incident and should be captured first.
- `P2`: cases 02 and 04 remain confirmed suspected cards requiring the same
  evidence capture and comparison.
- `P3`: reserved for future partial/uncertain discoveries; none are registered
  yet.
