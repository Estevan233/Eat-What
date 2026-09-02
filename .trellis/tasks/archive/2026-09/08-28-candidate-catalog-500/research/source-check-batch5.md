# Batch 5 source check — Meishichina public recipe pages

## Scope

Batch 5 adds 52 mainstream, reachable recipe candidates to
`backend/data/external_dining_seed.json`. The list is intentionally biased
toward ordinary rice/noodle/dumpling/soup/home-style dishes rather than
festival or intangible-heritage names that users may not be able to order.

## Parallel browser verification

On 2026-08-31, the 52 direct pages under `home.meishichina.com/recipe-*.html`
were opened in bounded parallel batches through the user-authorized Chrome
CDP session. All 52 returned HTTP 200 and a recipe title containing the target
dish name (for example `recipe-667343` 烤猪排 and `recipe-667338` 香菇酱拌面).

This proves that the public page exists and exposes a recipe/ingredient lead.
It does **not** prove that a nearby merchant sells the dish, that the dish is
available for delivery, or that the page's nutrition/health language is
reliable. Therefore every batch-5 row remains `review_status=draft`, uses
`delivery_fit=unknown`, `price_band=unknown`, `nature=unknown`, and carries an
explicit review note.

## Why this source replaces a blocked path

The direct Xiachufang pages used by batch 4 began returning rate-limit and
intermittent gateway responses during repeated checks. We stopped retrying the
same path and switched to Meishichina's public recipe index and direct pages.
The source is still treated as a discovery source (not a menu authority), so
production approval still requires a merchant/menu existence check and a
human content review.

## Review hand-off

The batch manifest records the direct URL and timestamp for each row. Before
approval, fill in merchant/menu evidence, serving size, delivery fit,
allergens, and reviewer identity; do not copy the page's unverified efficacy
claims into user-facing tags.
