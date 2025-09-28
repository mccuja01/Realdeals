# RealDeals Top 10 Engine

## Objective
Deliver exactly ten extraordinary, deeply discounted deals from across the internet every day. Each featured deal must be rare, highly compelling, and objectively the best available offer at that moment.

## Daily Pipeline Overview
1. **Data Ingestion Window (00:00–01:00 UTC)**
   - Pull fresh listings from approved sources (marketplaces, brand outlets, premium aggregators, invite-only communities).
   - Capture metadata: price history, stock levels, seller reputation, exclusivity flags, expiration timestamps, category tags, shipping region.
   - Maintain per-source rate limits and authentication tokens.

2. **Normalization & Enrichment (01:00–02:00 UTC)**
   - Standardize currencies, units, categories, and timestamps.
   - Enrich with third-party signals (historical price trackers, coupon status, social buzz, review sentiment, scarcity indicators).
   - Discard listings missing critical metadata.

3. **Eligibility Filtering (02:00–02:30 UTC)**
   - Ensure minimum discount threshold (e.g., ≥40% off verified MSRP or historical average).
   - Validate seller reliability (e.g., ≥4.5/5 rating or official brand store).
   - Confirm availability (stock > 0, ships within 7 days, no regional blocks for core markets).
   - Remove prohibited items and duplicates (SKU-level dedup + fuzzy matching on titles/descriptions).

4. **Scoring Engine (02:30–03:30 UTC)**
   - Compute composite score `S` for each candidate using weighted factors:
     - `Discount Depth (w=0.50)` – Percent off vs MSRP or recent price floor.
     - `Rarity & Scarcity (w=0.20)` – Limited edition, invite-only, inventory count, time-to-expiry.
     - `Freshness (w=0.15)` – Recency of discovery; penalize stale entries beyond 72 hours.
     - `Trust & Quality (w=0.10)` – Seller score, product reviews, warranty/return policy.
     - `Inventory Signal (w=0.05)` – Reward legitimately scarce stock while deprioritising plentiful supply.
   - Normalize each factor to `[0, 1]` and apply Bayesian smoothing to avoid overfitting sparse signals.
   - Apply category diversity boost: penalize redundant deals within same category unless score gap >10%.

5. **Manual Curation Safeguard (03:30–05:00 UTC)**
   - Present top 25 scored deals to human curator.
   - Curator can veto (with reason codes) or flag for further verification.
   - Curator decisions feed back into machine-learning feedback loop.

6. **Final Selection (05:00 UTC)**
   - Lock in highest scoring 10 deals post-curation.
   - Generate canonical deal objects with static URLs, hero images, copywriting snippets, and countdown timers.
   - Archive snapshots for auditability and future performance tracking.

7. **Distribution & Monitoring (05:00–24:00 UTC)**
   - Publish to app, email digest, push notifications.
   - Monitor inventory and price drift; auto-replace if deal expires early using next-best candidate.
   - Collect click-through, conversion, and revenue share metrics for model training.

## Data Governance & Quality Controls
- Maintain source trust tiers; demote sources with repeated misinformation or stockouts.
- Use anomaly detection to flag suspicious price drops (>80% off) for manual review.
- Enforce privacy and compliance (GDPR, CCPA) for user behavior analytics.
- Retain immutable logs of selection rationale per deal.

## Machine Learning Components
- **Price Normalization Model:** Predict fair value baseline per SKU using historical data + comparable listings.
- **Scarcity Estimator:** Classify listings as "common", "limited", or "exclusive" via inventory signals and text features.
- **Demand Forecasting:** Short-term demand prediction using search/social trends, site click-through, wishlist data.
- **Feedback Loop:** Reinforcement signal from conversions and curator overrides adjusts scoring weights nightly.

## Failure Handling
- If fewer than 10 eligible deals remain after filtering, trigger outreach to premium partners and display transparency notice to users.
- Automatic alerting for API failures, delayed pipelines, or mismatch between advertised and actual prices.
- Maintain fallback cache of vetted evergreen deals to surface only when emergency gap exists (and clearly labeled as such).

## Key Performance Indicators
- Daily gross merchandise value (GMV) attributable to top 10 deals.
- Average discount percentage vs MSRP.
- Deal sell-through rate within 24 hours.
- Curator intervention frequency (aim to decrease over time).
- User satisfaction (NPS) specific to perceived deal quality.

## Security Considerations
- Use signed webhooks for incoming price updates.
- Encrypt credentials for partner APIs (Vault/KMS).
- Monitor for scraping or automated exploitation of exclusive deals.

## Extensibility Hooks
- Plug-in architecture for adding new data sources with minimal effort.
- Support category-specific scoring tweaks (e.g., electronics vs travel vs collectibles).
- Provide API endpoint for partners to propose deals with required metadata schema.

## Reference Implementation Snapshot
The initial production-grade implementation in this repository ships with:

- `realdeals.models.Deal` – Canonical data model enforcing pricing sanity checks and timezone-aware timestamps.
- `realdeals.scoring.DealScorer` – Deterministic feature weighting for discount, rarity, freshness, trust, and inventory signals.
- `realdeals.pipeline.DealPipeline` – Coordinates fetching from pluggable connectors, deduplicates candidates, filters by
  freshness/discount thresholds, scores every eligible listing, and guarantees the final collection contains exactly ten items.
  Connectors receive a `since` timestamp derived from the configured freshness window so they can avoid returning stale
  inventory.
- `realdeals.tests.test_pipeline` – Pytest suite covering deduplication, eligibility filtering, scarcity handling, and the
  "exactly ten" invariant.

Run `pytest` to validate the full selection loop end-to-end.
