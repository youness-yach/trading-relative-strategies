# Trading & relative-value experiments

Curated notebooks and small Python projects around macro, equities, mean reversion, and related quant work.

## Layout

- `notebooks/` — exploratory and strategy notebooks (FRED, GARCH, portfolio/PCA-style work, etc.).
- `codes-from-ilia/` — supporting codebases (e.g. correlation tooling, DeFi TWAP utilities). Runtime logs and `trade_logs/` are not versioned by default.
- `mean-reversion-strategy/` — mean-reversion style execution/helpers.

## Notes

- This is a **portfolio snapshot**, not production trading infrastructure.
- Do not commit secrets; use environment variables for API keys where applicable.
