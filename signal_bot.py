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


class BinanceSignalBot:
    def __init__(self):
        # Use public client (no API key required)
        self.client = Client()
        self.signals = []

    def send_telegram_alert(self, message):
        """Send alert to Telegram"""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print(f"[ALERT] {message}")
            return

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, data=payload, timeout=10)
        except Exception as e:
            print(f"Error sending Telegram alert: {e}")

    def get_top_symbols(self):
        """Fetch top 50 symbols by 24h volume (public data)"""
        try:
            tickers = self.client.get_ticker()
            # Filter USDT pairs and sort by 24h volume
            usdt_pairs = [t for t in tickers if t['symbol'].endswith('USDT')]
            sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteAssetVolume']), reverse=True)
            symbols = [t['symbol'] for t in sorted_pairs[:TOP_SYMBOLS]]
            print(f"Fetched {len(symbols)} top symbols by 24h volume")
            return symbols
        except BinanceAPIException as e:
            print(f"Error fetching symbols: {e}")
            return []

    def get_klines(self, symbol, interval, limit=200):
        """Fetch candle data from Binance (public data)"""
        try:
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
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
            
            return df
        except BinanceAPIException as e:
            print(f"Error fetching klines for {symbol}: {e}")
            return None

    def calculate_indicators(self, df):
        """Calculate all technical indicators"""
        if df is None or len(df) < 100:
            return None

        try:
            # EMA Indicators
            for period in EMA_PERIODS:
                df[f'ema_{period}'] = EMAIndicator(close=df['close'], window=period).ema_indicator()

            # RSI Indicator
            df['rsi_6'] = RSIIndicator(close=df['close'], window=RSI_PERIOD).rsi()

            # Volume indicators
            for period in VOLUME_PERIODS:
                df[f'volume_ma_{period}'] = df['volume'].rolling(window=period).mean()

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

            # VWAP
            df['vwap'] = VolumeWeightedAveragePrice(
                high=df['high'],
                low=df['low'],
                close=df['close'],
                volume=df['volume'],
                window=14
            ).volume_weighted_average_price()

            return df
        except Exception as e:
            print(f"Error calculating indicators: {e}")
            return None

    def generate_signals(self, symbol, df):
        """Generate BUY/SELL signals based on trend following strategy"""
        if df is None or len(df) < 2:
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

        # BUY Signal - Trend Following (Long)
        if (ema_7 > ema_25 > ema_99 and  # EMA alignment bullish
            close > vwap and  # Price above VWAP
            supertrend_dir > 0 and  # Supertrend bullish
            rsi > 30 and rsi < 70 and  # RSI in healthy zone
            current_volume > volume_ma_5):  # Volume confirmation
            
            signal = "LONG"
            reason = f"EMA bullish, Close${{{close:.2f}}} > VWAP${{{vwap:.2f}}}, Supertrend↑, RSI:{rsi:.1f}, Vol confirmed"

        # SELL Signal - Trend Following (Short)
        elif (ema_7 < ema_25 < ema_99 and  # EMA alignment bearish
              close < vwap and  # Price below VWAP
              supertrend_dir < 0 and  # Supertrend bearish
              rsi > 30 and rsi < 70 and  # RSI in healthy zone
              current_volume > volume_ma_10):  # Volume confirmation
            
            signal = "SHORT"
            reason = f"EMA bearish, Close${{{close:.2f}}} < VWAP${{{vwap:.2f}}}, Supertrend↓, RSI:{rsi:.1f}, Vol confirmed"

        return {"symbol": symbol, "signal": signal, "reason": reason}

    def run_scan(self):
        """Run trading signal scan on all top symbols"""
        print(f"\n{'='*60}")
        print(f"Scan started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

        symbols = self.get_top_symbols()
        if not symbols:
            print("No symbols fetched. Exiting...")
            return

        buy_signals = []
        sell_signals = []

        for i, symbol in enumerate(symbols, 1):
            print(f"[{i}/{len(symbols)}] Analyzing {symbol}...", end=" ")

            # Fetch data
            df = self.get_klines(symbol, Client.KLINE_INTERVAL_1HOUR, limit=200)
            if df is None:
                print("SKIP")
                continue

            # Calculate indicators
            df = self.calculate_indicators(df)
            if df is None:
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
        print(f"\n{'='*60}")
        print(f"SCAN RESULTS")
        print(f"{'='*60}")

        if buy_signals:
            print(f"\n🟢 BUY SIGNALS ({len(buy_signals)}):")
            for sig in buy_signals:
                message = f"🟢 <b>BUY SIGNAL</b>\n<b>{sig['symbol']}</b>\n{sig['reason']}"
                print(f"  {sig['symbol']}: {sig['reason']}")
                self.send_telegram_alert(message)

        if sell_signals:
            print(f"\n🔴 SELL SIGNALS ({len(sell_signals)}):")
            for sig in sell_signals:
                message = f"🔴 <b>SELL SIGNAL</b>\n<b>{sig['symbol']}</b>\n{sig['reason']}"
                print(f"  {sig['symbol']}: {sig['reason']}")
                self.send_telegram_alert(message)

        if not buy_signals and not sell_signals:
            print("\n⚪ NO SIGNALS - No trading opportunities detected")

        print(f"\nScan completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    """Main entry point"""
    bot = BinanceSignalBot()

    # Run once
    bot.run_scan()

    # For continuous monitoring, uncomment below:
    # while True:
    #     bot.run_scan()
    #     print(f"\nNext scan in 60 minutes...")
    #     time.sleep(3600)  # Run every hour


if __name__ == "__main__":
    main()
