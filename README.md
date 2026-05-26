# Deriv Over 3 Trading Bot

This project contains two useful versions of the bot:

- A Python Deriv API bot with market scanning, risk controls, SQLite trade logs, and a live terminal dashboard.
- A Deriv Bot Builder XML export that can be imported into Deriv's visual Bot Builder.

No bot can guarantee profit. Test on a demo account first and trade only money you can afford to lose.

## What Is Included

| Area | Included |
| --- | --- |
| Strategy | DIGIT OVER 3, barrier 3, 1 tick duration |
| Markets | Scans R_10, R_25, R_50, R_75, and R_100 in the Python bot |
| Risk | Stop-loss, take-profit, max daily trades, cooldown, loss guard |
| Staking | Safer martingale sequence instead of pure doubling |
| Records | SQLite trade history, latency, execution speed, market stats, and log file |
| Dashboard | Rich terminal dashboard plus a Deriv-style local web preview |
| Export | `exports/deriv-over3-bot.xml` for Deriv Bot Builder |
| Download | `dist/deriv-over3-package.zip` package for moving to another device |

## Project Structure

```text
deriv_bot/
  api/                 Deriv WebSocket client
  analytics/           Digit tracking and SQLite logging
  analytics/performance.py  In-memory performance metrics
  api/auth.py          Token validation helpers
  dashboard/           Terminal dashboard
  exports/             Deriv Bot Builder XML export
  risk/                Bankroll and martingale logic
  risk/stoploss.py     Stop-loss, take-profit, and max-trade rules
  strategies/          Trading strategy, filters, and market selector
  web/                 Deriv-style local dashboard preview
  tools/               Packaging script
  main.py              Python bot entry point
  config.py            Environment-driven settings
  ARCHITECTURE_AUDIT.md  Blueprint compliance notes
```

## Import Into Deriv Bot Builder

1. Open `https://app.deriv.com/bot`.
2. Go to **Bot Builder**.
3. Click **Import**, choose **Local**, and select:

```text
exports/deriv-over3-bot.xml
```

You can also drag the XML file onto the Deriv Bot Builder workspace.

The XML export contains the base Deriv Bot Builder version. The Python bot has the additional features: market scanning, filters, SQLite logs, terminal dashboard, and richer risk controls.

## Run the Python Bot

1. Install Python 3.12 or newer.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set your Deriv API token:

```text
DERIV_API_TOKEN=your_api_token_here
```

4. Start the bot:

```bash
python main.py
```

Press `Ctrl+C` for a clean stop.

## Open the Deriv-Style Dashboard

Open this file in a browser:

```text
web/index.html
```

It is a local visual dashboard shaped like Deriv Bot Builder and includes download links for the XML and packaged ZIP.

## Build the Download Package

From PowerShell:

```powershell
.\tools\build_package.ps1
```

The package is created here:

```text
dist/deriv-over3-package.zip
```

Move that ZIP to another desktop or phone. On phones, use the XML import in Deriv Bot. The full Python bot needs a Python-capable environment.

## Important Risk Notes

- Martingale increases exposure after losses.
- Keep `MAX_MARTINGALE_STEPS` low.
- Keep `STOP_LOSS` enabled.
- Demo test before using a real account.
- Digit markets are still random enough that losses can happen quickly.

## Architecture Checklist

- Connects to Deriv WebSocket API with authorization and reconnect backoff.
- Scans R_10, R_25, R_50, R_75, and R_100.
- Trades only DIGITOVER barrier 3.
- Tracks digit distribution, Over 3 rate, spike ratio, stability, momentum, tick speed, and market score.
- Filters low-score, unstable, high-latency, high-spike, and loss-streak conditions.
- Supports adjustable stake, martingale, stop loss, take profit, cooldown, and max daily trades.
- Logs symbol, stake, digit, result, PnL, balance, market score, latency, execution time, and analysis metrics to SQLite.
- Shows win rate, average profit/loss, best/worst market, latency, execution speed, market ranking, and risk state in the Rich dashboard.

See `ARCHITECTURE_AUDIT.md` for the focused blueprint scan notes.
