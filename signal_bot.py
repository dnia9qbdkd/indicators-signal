import os
from dotenv import load_dotenv
import requests
from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, SuperTrend
from ta.volume import VolumeWeightedAveragePrice
import time
from datetime import datetime, timedelta

load_dotenv()

# Telegram Configuration (add to .env later)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Strategy Parameters
TOP_SYMBOLS = 50
TIMEFRAME = "1h"
VOLUME_LOOKBACK = 24  # 24 hours for volume calculation

# Indicator Parameters
EMA_PERIODS = [7, 25, 99]
RSI_PERIOD = 6
VOLUME_PERIODS = [5, 10]
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 3

# Debug Configuration
DEBUG_FILE = "debug.txt"
SIGNALS_FILE = "signals.txt"


class DebugLogger:
    """Helper class to log debug information to file and console"""
    def __init__(self, filename="debug.txt"):
        self.filename = filename
        self.log(f"\n{'='*80}")
        self.log(f"Debug Session Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"{'='*80}\n")

    def log(self, message):
        """Log message to both file and console"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        with open(self.filename, 'a') as f:
            f.write(log_message + "\n")


class SignalsLogger:
    """Helper class to log trading signals to file"""
    def __init__(self, filename=SIGNALS_FILE):
        self.filename = filename
        self.write_header()

    def write_header(self):
        """Write header to signals file"""
        with open(self.filename, 'a') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Trading Signals - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n")

    def log_signal(self, signal_type, symbol, reason):
        """Log a trading signal"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        signal_emoji = "🟢 BUY" if signal_type == "LONG" else "🔴 SELL"
        log_entry = f"[{timestamp}] {signal_emoji} | {symbol} | {reason}"
        
        with open(self.filename, 'a') as f:
            f.write(log_entry + "\n")

    def log_summary(self, buy_count, sell_count):
        """Log scan summary"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        summary = f"\n[{timestamp}] SUMMARY: {buy_count} BUY signals, {sell_count} SELL signals\n"
        
        with open(self.filename, 'a') as f:
            f.write(summary)


debug = DebugLogger(DEBUG_FILE)
signals_logger = SignalsLogger(SIGNALS_FILE)


class BinanceSignalBot:
    def __init__(self):
        # Use public client (no API key required)
        self.client = Client()
        self.signals = []
        self.telegram_enabled = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
        debug.log("[INIT] BinanceSignalBot initialized")
        if not self.telegram_enabled:
            debug.log("[INIT] ⚠️  Telegram disabled - signals will be logged to signals.txt")
        else:
            debug.log("[INIT] ✓ Telegram enabled - alerts will be sent")

    def send_telegram_alert(self, message):
        """Send alert to Telegram or log to file"""
        debug.log(f"[TELEGRAM] Attempting to send alert: {message[:50]}...")
        
        if not self.telegram_enabled:
            debug.log("[TELEGRAM] No Telegram credentials - alert logged to file only")
            return False

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            response = requests.post(url, data=payload, timeout=10)
            debug.log(f"[TELEGRAM] Alert sent successfully. Status: {response.status_code}")
            return True
        except Exception as e:
            debug.log(f"[TELEGRAM] Error sending alert: {e}")
            return False

    def get_top_symbols(self):
        """Fetch top 50 symbols by 24h volume (public data)"""
        debug.log("[GET_TOP_SYMBOLS] Starting symbol fetch...")
        try:
            tickers = self.client.get_ticker()
            debug.log(f"[GET_TOP_SYMBOLS] Retrieved {len(tickers)} total tickers")
            
            # Filter USDT pairs and sort by 24h volume
            usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
            debug.log(f"[GET_TOP_SYMBOLS] Found {len(usdt_pairs)} USDT pairs")
            
            sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteAssetVolume']), reverse=True)
            symbols = [t['symbol'] for t in sorted_pairs[:TOP_SYMBOLS]]
            debug.log(f"[GET_TOP_SYMBOLS] Selected top {len(symbols)} symbols by volume")
            debug.log(f"[GET_TOP_SYMBOLS] Top 5 symbols: {symbols[:5]}")
            
            print(f"Fetched {len(symbols)} top symbols by 24h volume")
            return symbols
        except BinanceAPIException as e:
            debug.log(f"[GET_TOP_SYMBOLS] BinanceAPIException: {e}")
            print(f"Error fetching symbols: {e}")
            return []
        except Exception as e:
            debug.log(f"[GET_TOP_SYMBOLS] Unexpected error: {e}")
            return []

    def get_klines(self, symbol, interval, limit=200):
        """Fetch candle data from Binance (public data)"""
        debug.log(f"[GET_KLINES] Fetching {limit} candles for {symbol} with interval {interval}")
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            debug.log(f"[GET_KLINES] Retrieved {len(klines)} klines for {symbol}")
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            debug.log(f"[GET_KLINES] {symbol} - First: {df.iloc[0]['timestamp']}, Last: {df.iloc[-1]['timestamp']}")
            debug.log(f"[GET_KLINES] {symbol} - Price range: {df['low'].min():.8f} - {df['high'].max():.8f}")
            debug.log(f"[GET_KLINES] {symbol} - Volume avg: {df['volume'].mean():.2f}")
            
            return df
        except BinanceAPIException as e:
            debug.log(f"[GET_KLINES] BinanceAPIException for {symbol}: {e}")
            print(f"Error fetching klines for {symbol}: {e}")
            return None
        except Exception as e:
            debug.log(f"[GET_KLINES] Unexpected error for {symbol}: {e}")
            return None

    def calculate_indicators(self, df):
        """Calculate all technical indicators"""
        debug.log(f"[CALC_INDICATORS] Starting indicator calculation with {len(df)} rows")
        
        if df is None or len(df) < 100:
            debug.log(f"[CALC_INDICATORS] Insufficient data: {len(df) if df is not None else 0} rows < 100 required")
            return None

        try:
            # EMA Indicators
            for period in EMA_PERIODS:
                df[f'ema_{period}'] = EMAIndicator(close=df['close'], window=period).ema_indicator()
                debug.log(f"[CALC_INDICATORS] EMA({period}) calculated - Latest: {df[f'ema_{period}'].iloc[-1]:.8f}")

            # RSI Indicator
            df['rsi_6'] = RSIIndicator(close=df['close'], window=RSI_PERIOD).rsi()
            debug.log(f"[CALC_INDICATORS] RSI(6) calculated - Latest: {df['rsi_6'].iloc[-1]:.2f}")

            # Volume indicators
            for period in VOLUME_PERIODS:
                df[f'volume_ma_{period}'] = df['volume'].rolling(window=period).mean()
                debug.log(f"[CALC_INDICATORS] Volume MA({period}) calculated - Latest: {df[f'volume_ma_{period}'].iloc[-1]:.2f}")

            # Supertrend
            supertrend = SuperTrend(
                high=df['high'],
                low=df['low'],
                close=df['close'],
                period=SUPERTREND_PERIOD,
                multiplier=SUPERTREND_MULTIPLIER
            )
            df['supertrend'] = supertrend.supertrendl()
            df['supertrend_direction'] = supertrend.supertrendli()
            debug.log(f"[CALC_INDICATORS] SuperTrend calculated - Direction: {df['supertrend_direction'].iloc[-1]:.2f}")

            # VWAP
            df['vwap'] = VolumeWeightedAveragePrice(
                high=df['high'],
                low=df['low'],
                close=df['close'],
                volume=df['volume'],
                window=14
            ).volume_weighted_average_price()
            debug.log(f"[CALC_INDICATORS] VWAP calculated - Latest: {df['vwap'].iloc[-1]:.8f}")
            
            debug.log(f"[CALC_INDICATORS] All indicators calculated successfully")
            return df
        except Exception as e:
            debug.log(f"[CALC_INDICATORS] Error: {e}")
            print(f"Error calculating indicators: {e}")
            return None

    def generate_signals(self, symbol, df):
        """Generate BUY/SELL signals based on trend following strategy"""
        debug.log(f"[GENERATE_SIGNALS] Processing {symbol}")
        
        if df is None or len(df) < 2:
            debug.log(f"[GENERATE_SIGNALS] Invalid data for {symbol}")
            return None

        latest = df.iloc[-1]
        previous = df.iloc[-2]

        # Trend confirmation: EMA alignment
        ema_7 = latest['ema_7']
        ema_25 = latest['ema_25']
        ema_99 = latest['ema_99']
        rsi = latest['rsi_6']
        supertrend_dir = latest['supertrend_direction']
        close = latest['close']
        vwap = latest['vwap']

        # Volume confirmation
        current_volume = latest['volume']
        volume_ma_5 = latest['volume_ma_5']
        volume_ma_10 = latest['volume_ma_10']

        signal = None
        reason = ""

        # Debug: Log all indicator values
        debug.log(f"[GENERATE_SIGNALS] {symbol} - EMA: 7={ema_7:.8f}, 25={ema_25:.8f}, 99={ema_99:.8f}")
        debug.log(f"[GENERATE_SIGNALS] {symbol} - Price: {close:.8f}, VWAP: {vwap:.8f}, Diff: {close - vwap:.8f}")
        debug.log(f"[GENERATE_SIGNALS] {symbol} - RSI: {rsi:.2f}, SuperTrend: {supertrend_dir:.2f}")
        debug.log(f"[GENERATE_SIGNALS] {symbol} - Volume: {current_volume:.2f}, MA5: {volume_ma_5:.2f}, MA10: {volume_ma_10:.2f}")

        # BUY Signal - Trend Following (Long)
        if (ema_7 > ema_25 > ema_99 and  # EMA alignment bullish
            close > vwap and  # Price above VWAP
            supertrend_dir > 0 and  # Supertrend bullish
            rsi > 30 and rsi < 70 and  # RSI in healthy zone
            current_volume > volume_ma_5):  # Volume confirmation
            
            signal = "LONG"
            reason = f"EMA bullish, Close${{{close:.2f}}} > VWAP${{{vwap:.2f}}}, Supertrend↑, RSI:{rsi:.1f}, Vol confirmed"
            debug.log(f"[GENERATE_SIGNALS] ✓ BUY SIGNAL for {symbol}: {reason}")

        # SELL Signal - Trend Following (Short)
        elif (ema_7 < ema_25 < ema_99 and  # EMA alignment bearish
              close < vwap and  # Price below VWAP
              supertrend_dir < 0 and  # Supertrend bearish
              rsi > 30 and rsi < 70 and  # RSI in healthy zone
              current_volume > volume_ma_10):  # Volume confirmation
            
            signal = "SHORT"
            reason = f"EMA bearish, Close${{{close:.2f}}} < VWAP${{{vwap:.2f}}}, Supertrend↓, RSI:{rsi:.1f}, Vol confirmed"
            debug.log(f"[GENERATE_SIGNALS] ✓ SELL SIGNAL for {symbol}: {reason}")
        else:
            debug.log(f"[GENERATE_SIGNALS] ✗ NO SIGNAL for {symbol} - Conditions not met")

        return {"symbol": symbol, "signal": signal, "reason": reason}

    def run_scan(self):
        """Run trading signal scan on all top symbols"""
        debug.log(f"\n[RUN_SCAN] Scan started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n{'='*60}")
        print(f"Scan started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if not self.telegram_enabled:
            print("📝 Signals will be saved to signals.txt")
        else:
            print("📨 Signals will be sent via Telegram")
        print(f"{'='*60}")

        symbols = self.get_top_symbols()
        if not symbols:
            debug.log("[RUN_SCAN] No symbols fetched. Exiting...")
            print("No symbols fetched. Exiting...")
            return

        buy_signals = []
        sell_signals = []

        for i, symbol in enumerate(symbols, 1):
            debug.log(f"[RUN_SCAN] [{i}/{len(symbols)}] Analyzing {symbol}...")
            print(f"[{i}/{len(symbols)}] Analyzing {symbol}...", end=" ")

            # Fetch data
            df = self.get_klines(symbol, Client.KLINE_INTERVAL_1HOUR, limit=200)
            if df is None:
                debug.log(f"[RUN_SCAN] {symbol} - Failed to fetch klines")
                print("SKIP")
                continue

            # Calculate indicators
            df = self.calculate_indicators(df)
            if df is None:
                debug.log(f"[RUN_SCAN] {symbol} - Failed to calculate indicators")
                print("SKIP")
                continue

            # Generate signal
            signal_data = self.generate_signals(symbol, df)
            if signal_data and signal_data["signal"]:
                print(f"→ {signal_data['signal']}")
                if signal_data["signal"] == "LONG":
                    buy_signals.append(signal_data)
                elif signal_data["signal"] == "SHORT":
                    sell_signals.append(signal_data)
            else:
                print("NO SIGNAL")

            time.sleep(0.1)  # Rate limiting

        # Send alerts
        debug.log(f"\n[RUN_SCAN] Scan Results Summary:")
        debug.log(f"[RUN_SCAN] Buy Signals: {len(buy_signals)}, Sell Signals: {len(sell_signals)}")
        
        print(f"\n{'='*60}")
        print(f"SCAN RESULTS")
        print(f"{'='*60}")

        if buy_signals:
            debug.log(f"[RUN_SCAN] Processing {len(buy_signals)} BUY signals")
            print(f"\n🟢 BUY SIGNALS ({len(buy_signals)}):")
            for sig in buy_signals:
                message = f"🟢 <b>BUY SIGNAL</b>\n<b>{sig['symbol']}</b>\n{sig['reason']}"
                print(f"  {sig['symbol']}: {sig['reason']}")
                debug.log(f"[RUN_SCAN] Sending BUY alert for {sig['symbol']}")
                self.send_telegram_alert(message)
                # Always log to file as well
                signals_logger.log_signal("LONG", sig['symbol'], sig['reason'])

        if sell_signals:
            debug.log(f"[RUN_SCAN] Processing {len(sell_signals)} SELL signals")
            print(f"\n🔴 SELL SIGNALS ({len(sell_signals)}):")
            for sig in sell_signals:
                message = f"🔴 <b>SELL SIGNAL</b>\n<b>{sig['symbol']}</b>\n{sig['reason']}"
                print(f"  {sig['symbol']}: {sig['reason']}")
                debug.log(f"[RUN_SCAN] Sending SELL alert for {sig['symbol']}")
                self.send_telegram_alert(message)
                # Always log to file as well
                signals_logger.log_signal("SHORT", sig['symbol'], sig['reason'])

        if not buy_signals and not sell_signals:
            debug.log(f"[RUN_SCAN] No signals detected")
            print("\n⚪ NO SIGNALS - No trading opportunities detected")

        # Log summary to signals file
        signals_logger.log_summary(len(buy_signals), len(sell_signals))

        debug.log(f"[RUN_SCAN] Scan completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nScan completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    """Main entry point"""
    debug.log("[MAIN] Application started")
    bot = BinanceSignalBot()

    # Run once
    bot.run_scan()
    
    debug.log("[MAIN] Application completed")

    # For continuous monitoring, uncomment below:
    # while True:
    #     bot.run_scan()
    #     print(f"\nNext scan in 60 minutes...")
    #     time.sleep(3600)  # Run every hour


if __name__ == "__main__":
    main()
