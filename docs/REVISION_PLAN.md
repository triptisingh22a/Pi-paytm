# Standalone merchant decision website — revision plan

The 2026-10-02 instructions supersede the phone-frame requirement. Keep the earlier tested deterministic modules as a legacy demonstration and create a billing-first standalone experience at /demo behind a full-screen landing page.

## Main demonstrations
1. Inventory/revenue overview: day by default, week/month selectors, exact POS revenue and product contribution, popularity/trend/dead-stock nudges, observed repeat-visit and basket profiles. Every statistic is computed in an engine tool, with a receipt and a time window.
2. Assortment twin: canonical SKU mapping → same-type/category peer retrieval → eligibility rerank and normalized weights → exposure-adjusted Gamma-Poisson product-rate transfer → paired assortment scenarios with substitution and outside-option sensitivity. Explicit Y→X and ranked replacement queries both supported. Customers/arrivals remain exogenous and are labeled scenario assumptions rather than identified from POS.

## Synthetic billing data
Hypermarket and restaurant are primary selectable demonstrations; apparel is also selectable. Supporting donor populations include kirana, pharmacy, bakery and electronics. Generate 365 days ending 2026-10-02, bill IDs and product-level timestamps, prices, quantities, optional synthetic pseudonymous loyalty IDs, stock arrivals, inventory exposure and restaurant recipe inputs. Restock data is an explicitly supplied merchant feed, not implicit payment data. All data remains simulated.

## Identity and inference limits
Normalize units and pack sizes, preserve brand/variant/category, exact catalogue aliases/identifiers first; ambiguous matches abstain. Product identity, product family and substitution sets are distinct. Retrieve donors using stable category mixes/ticket/seasonality/scale features, excluding the candidate outcome from similarity features. Transfer means and uncertainty under stated transport assumptions; no peer transfer of costs/demographics/facilities. Aggregate at least ten eligible merchants, report effective sample size and insufficient-support decisions.

## Dashboard and agent
Wide app layout: sidebar, merchant switch, period controls, inventory table, revenue chart, grounded overview, peer panel and twin workspace. Text/voice share one server-side tool executor. Gemini is optional and never performs arithmetic or external actions; local deterministic routing is the working fallback. Sarvam is for STT/TTS only, not default chat generation.

## Verification order
Offline/synthetic tests and frontend production build first. Browser tests cover landing entry, hypermarket/restaurant switch, period aggregates, overview question, replacement question, receipts, peer support, supplier-bill confirmation and a paired seven-day scenario. Regenerate backup recording. Live Sarvam is last: exactly one short TTS request then at most one STT request using its WAV. No automatic retries, no chat requests and no API key in source, archives or logs. Package only after documenting the final result.
