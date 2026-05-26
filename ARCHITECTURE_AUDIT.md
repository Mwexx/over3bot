# Architecture Audit

This project was scanned against the Deriv Over 3 blueprint.

## Implemented

- Python 3.12+ async architecture using WebSockets.
- Deriv authorization through API token and `.env`.
- Dynamic scan of `R_10`, `R_25`, `R_50`, `R_75`, and `R_100`.
- DIGITOVER barrier 3 contract payload.
- Last-200-tick analysis with digit frequency, Over 3 rate, stability, spike ratio, momentum, tick speed, and market score.
- Trade filters for minimum data, score, stability, spike ratio, empirical Over 3 rate, API latency, and consecutive losses.
- Adjustable base stake, martingale multiplier or safe martingale sequence, max martingale steps, stop loss, take profit, max daily trades, and cooldown.
- Automatic stop on stop-loss, take-profit, and max-trade limits.
- Duplicate contract guard and contract-id verification.
- Balance refresh after settled contracts.
- Reconnect with exponential backoff.
- SQLite trade logs with PnL, digit, market score, latency, execution speed, and analysis metrics.
- Rich terminal dashboard with market ranking, latency, execution speed, win rate, average profit/loss, and best/worst market.
- Importable Deriv Bot Builder XML in `exports/deriv-over3-bot.xml`.

## Important Limits

- The bot does not and cannot guarantee profit.
- Digit behavior is still mostly random; analysis is used only as a filter.
- Martingale can increase losses quickly; use the safe sequence and demo-test first.

## Recommended Operating Defaults

- `USE_SAFE_MARTINGALE_SEQUENCE=true`
- `MAX_MARTINGALE_STEPS=4`
- `STOP_LOSS=-20`
- `TAKE_PROFIT=30`
- `MAX_CONSECUTIVE_LOSSES=5`
- Demo account testing before real-money use.
