import requests
import pandas as pd
import ta
import time
import os
from datetime import datetime

# ========== CONFIG ==========
TELEGRAM_TOKEN = '7826236909:AAENixPCxu4atFDB9ICYSdo_kRR8KA3HnQ8'
TELEGRAM_CHAT_ID = '5614752129'
SYMBOLS = ['XXBTZUSD', 'XETHZUSD', 'SOLUSD', 'XRPUSD']
INTERVAL = 1  # 1 minute candles
TRADE_QTY = 0.01
STOP_LOSS_PCT = 0.01  # 1%
TAKE_PROFIT_PCT = 0.015  # 1.5%
LOG_FILE = 'trade_log.csv'
open_positions = {}

# ========== FUNCTIONS ==========
def fetch_ohlcv(symbol, interval=1):
    url = f'https://api.kraken.com/0/public/OHLC?pair={symbol}&interval={interval}'
    r = requests.get(url).json()
    result = list(r['result'].values())[0]
    df = pd.DataFrame(result, columns=['timestamp', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'])
    df['close'] = df['close'].astype(float)
    return df

def get_signals(df):
    df['ema5'] = ta.trend.ema_indicator(df['close'], window=5)
    df['ema9'] = ta.trend.ema_indicator(df['close'], window=9)
    df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
    df['macd'] = ta.trend.macd_diff(df['close'])
    bb = ta.volatility.BollingerBands(df['close'])
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()

    latest = df.iloc[-1]
    signals = []

    if latest['ema5'] > latest['ema9']:
        signals.append('EMA_UP')
    if latest['ema5'] < latest['ema9']:
        signals.append('EMA_DOWN')
    if latest['rsi'] < 30:
        signals.append('RSI_OVERSOLD')
    if latest['rsi'] > 70:
        signals.append('RSI_OVERBOUGHT')
    if latest['macd'] > 0:
        signals.append('MACD_BULLISH')
    if latest['macd'] < 0:
        signals.append('MACD_BEARISH')
    if latest['close'] < latest['bb_low']:
        signals.append('BB_BREAKDOWN')
    if latest['close'] > latest['bb_high']:
        signals.append('BB_BREAKOUT')

    # Decision
    if 'EMA_UP' in signals and 'RSI_OVERSOLD' in signals and 'MACD_BULLISH' in signals:
        return 'BUY', signals
    elif 'EMA_DOWN' in signals and 'RSI_OVERBOUGHT' in signals and 'MACD_BEARISH' in signals:
        return 'SELL', signals
    return 'HOLD', signals

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    try:
        requests.post(url, data=payload)
    except:
        print("Failed to send Telegram message.")

def log_trade(action, symbol, price, signals):
    row = {
        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        'symbol': symbol,
        'action': action,
        'price': price,
        'signals': ', '.join(signals),
        'qty': TRADE_QTY
    }
    df = pd.DataFrame([row])
    df.to_csv(LOG_FILE, mode='a', index=False, header=not os.path.exists(LOG_FILE))
    print(f"📊 Logged {action} for {symbol} at ${price:.2f}")

# ========== MAIN LOOP ==========
print("🚀 Kraken Paper Bot Running...")

while True:
    for symbol in SYMBOLS:
        try:
            df = fetch_ohlcv(symbol, INTERVAL)
            signal, indicators = get_signals(df)
            current_price = df['close'].iloc[-1]

            # Check for SL/TP on open trades
            if symbol in open_positions:
                trade = open_positions[symbol]
                if trade['side'] == 'BUY':
                    if current_price <= trade['sl']:
                        msg = f"🛑 STOP-LOSS HIT for {symbol} at ${current_price:.2f}"
                        send_telegram(msg)
                        del open_positions[symbol]
                    elif current_price >= trade['tp']:
                        msg = f"🎯 TAKE-PROFIT HIT for {symbol} at ${current_price:.2f}"
                        send_telegram(msg)
                        del open_positions[symbol]
                elif trade['side'] == 'SELL':
                    if current_price >= trade['sl']:
                        msg = f"🛑 STOP-LOSS HIT for {symbol} at ${current_price:.2f}"
                        send_telegram(msg)
                        del open_positions[symbol]
                    elif current_price <= trade['tp']:
                        msg = f"🎯 TAKE-PROFIT HIT for {symbol} at ${current_price:.2f}"
                        send_telegram(msg)
                        del open_positions[symbol]

            # Entry Logic
            if signal in ['BUY', 'SELL'] and symbol not in open_positions:
                sl = current_price * (1 - STOP_LOSS_PCT) if signal == 'BUY' else current_price * (1 + STOP_LOSS_PCT)
                tp = current_price * (1 + TAKE_PROFIT_PCT) if signal == 'BUY' else current_price * (1 - TAKE_PROFIT_PCT)
                open_positions[symbol] = {
                    'side': signal,
                    'entry': current_price,
                    'sl': sl,
                    'tp': tp
                }
                msg = f"📈 NEW {signal} SIGNAL for {symbol}\nEntry: ${current_price:.2f}\nSL: ${sl:.2f} | TP: ${tp:.2f}\nSignals: {', '.join(indicators)}"
                send_telegram(msg)
                log_trade(signal, symbol, current_price, indicators)
            else:
                print(f"⏳ {symbol} | Signal: {signal} | Price: ${current_price:.2f}")

        except Exception as e:
            print(f"❌ Error for {symbol}: {e}")
    time.sleep(60)
