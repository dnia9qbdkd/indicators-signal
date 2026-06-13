# indicators-signal

A **Binance trading signal bot** that analyzes the top 50 cryptocurrencies hourly using technical indicators and sends alerts via Telegram (or logs to file).

## 🎯 Features

- 📊 **Real-time analysis** - Scans top 50 USDT trading pairs by volume
- 🔔 **Smart alerts** - BUY/SELL signals based on multi-indicator confirmation
- 📨 **Flexible delivery** - Sends to Telegram OR logs to file if credentials missing
- 🔍 **Comprehensive logging** - Detailed debug logs for troubleshooting
- ⏰ **Automated** - Runs hourly via GitHub Actions (or manually)
- 📝 **No dependencies** - Works with public Binance API (no auth needed)

## 📈 Technical Indicators

- **EMA (7, 25, 99)** - Trend confirmation
- **RSI (6)** - Momentum
- **SuperTrend** - Trend direction
- **VWAP** - Volume-weighted price
- **Volume MA (5, 10)** - Volume confirmation

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/dnia9qbdkd/indicators-signal.git
cd indicators-signal
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -U -r requirements.txt
```

### 2. Configure (Optional - Telegram)

Create a `.env` file:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

**Without these**, signals are automatically logged to `signals.txt` ✅

### 3. Run

```bash
python3 signal_bot.py
```

Or use the shell script:

```bash
bash run_bot.sh
```

## 📁 Project Structure

```
indicators-signal/
├── signal_bot.py              # Main trading bot
├── monitor_workflow.py        # GitHub Actions monitor
├── trigger_workflow.py        # Manual workflow trigger
├── run_bot.sh                 # Execution script
├── requirements.txt           # Dependencies
├── .github/workflows/         # GitHub Actions
│   └── trading-signals.yml    # Hourly scheduler
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

## 📊 Output Files

- **signals.txt** - All trading signals (always created)
- **debug.txt** - Detailed debug logs
- **signal_bot_output.txt** - Console output (from GitHub Actions)

## 🔄 Workflow

```
Fetch top 50 symbols
    ↓
For each symbol:
    ├── Get price data (200 1-hour candles)
    ├── Calculate indicators
    ├── Check signal conditions
    └── If signal → Telegram + signals.txt
    ↓
Log summary
```

## 🎛️ Signal Conditions

### 🟢 BUY Signal (LONG)
- EMA(7) > EMA(25) > EMA(99) ✓
- Price > VWAP ✓
- SuperTrend bullish ✓
- RSI between 30-70 ✓
- Current volume > Volume MA(5) ✓

### 🔴 SELL Signal (SHORT)
- EMA(7) < EMA(25) < EMA(99) ✓
- Price < VWAP ✓
- SuperTrend bearish ✓
- RSI between 30-70 ✓
- Current volume > Volume MA(10) ✓

## 🛠️ Utilities

### Trigger Workflow Manually

```bash
export GITHUB_TOKEN=your_github_token
python trigger_workflow.py
```

### Monitor Workflow Runs

```bash
python monitor_workflow.py
```

## 📦 Dependencies

- `python-binance` - Binance API client
- `pandas` - Data manipulation
- `ta` - Technical analysis indicators
- `requests` - HTTP requests
- `python-dotenv` - Environment configuration

## ⚙️ Configuration

Edit constants in `signal_bot.py`:

```python
TOP_SYMBOLS = 50                # Number of pairs to analyze
EMA_PERIODS = [7, 25, 99]      # EMA periods
RSI_PERIOD = 6                  # RSI period
SUPERTREND_PERIOD = 10         # SuperTrend period
```

## 🔐 Best Practices

- ✅ Keep `.env` in `.gitignore` (already done)
- ✅ Don't commit sensitive tokens
- ✅ Review `debug.txt` for troubleshooting
- ✅ Check `signals.txt` for signal history
- ✅ Monitor GitHub Actions for failures

## 📝 Logging Levels

| Mode | Output |
|------|--------|
| **With Telegram** | Alerts sent + signals.txt logged |
| **Without Telegram** | signals.txt logged only |
| **Debug** | All debug.txt logs printed |

## 🤝 Contributing

Found a bug? Want to improve signals? Open an issue or PR!

## 📄 License

Unlicensed - Free to use and modify.

---

**Happy trading! 🚀**
