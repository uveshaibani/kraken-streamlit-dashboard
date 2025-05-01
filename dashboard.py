import streamlit as st
import pandas as pd
import requests
import ta
from datetime import datetime

# ========== CONFIG ==========
SYMBOLS = ['XXBTZUSD', 'XETHZUSD', 'SOLUSD', 'XRPUSD']
INTERVAL = 1
STOP_LOSS_PCT = 0.01
TAKE_PROFIT_PCT = 0.015
CANDLE_LIMIT = 200

# ========== DATA FUNCTIONS ==========
def fetch_ohlcv(symbol, interval=1):
    url = f'https://api.kraken.com/0/public/OHLC?pair={symbol}&interval={interval}'
    r = requests.get(url).json()
    result = list(r['result'].values())[0]
    df = pd.DataFrame(result, columns=['timestamp', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'])
    df['close'] = df['close'].astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
    return df.tail(CANDLE_LIMIT).reset_index(drop=True)

def get_signals(df):
    df['ema5'] = ta.trend.ema_indicator(df['close'], window=5)
    df['ema9'] = ta.trend.ema_indicator(df['close'], window=9)
    df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
    df['macd'] = ta.trend.macd_diff(df['close'])
    bb = ta.volatility.BollingerBands(df['close'])
    df['bb_high'] = bb.bollinger_hband()
    df['bb_low'] = bb.bollinger_lband()
    return df

def evaluate_signal(row):
    signals = []
    if row['ema5'] > row['ema9']:
        signals.append('EMA_UP')
    if row['ema5'] < row['ema9']:
        signals.append('EMA_DOWN')
    if row['rsi'] < 30:
        signals.append('RSI_OVERSOLD')
    if row['rsi'] > 70:
        signals.append('RSI_OVERBOUGHT')
    if row['macd'] > 0:
        signals.append('MACD_BULLISH')
    if row['macd'] < 0:
        signals.append('MACD_BEARISH')
    if row['close'] < row['bb_low']:
        signals.append('BB_BREAKDOWN')
    if row['close'] > row['bb_high']:
        signals.append('BB_BREAKOUT')

    action = 'HOLD'
    if 'EMA_UP' in signals and 'RSI_OVERSOLD' in signals and 'MACD_BULLISH' in signals:
        action = 'BUY'
    elif 'EMA_DOWN' in signals and 'RSI_OVERBOUGHT' in signals and 'MACD_BEARISH' in signals:
        action = 'SELL'

    return action, signals

# ========== STREAMLIT DASHBOARD ==========
st.set_page_config(page_title="Kraken Crypto Bot Dashboard", layout="wide")
st.title("📊 Kraken Crypto Paper Bot Dashboard")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("🔍 Current Signals")
    status_table = []
    for symbol in SYMBOLS:
        df = fetch_ohlcv(symbol, INTERVAL)
        df = get_signals(df)
        signal, signals_used = evaluate_signal(df.iloc[-1])
        price = df['close'].iloc[-1]
        status_table.append({
            'Symbol': symbol,
            'Price': f"${price:.2f}",
            'Signal': signal,
            'Indicators': ', '.join(signals_used)
        })
    st.dataframe(pd.DataFrame(status_table))

with col2:
    st.subheader("📈 Live Charts")
    selected_symbol = st.selectbox("Choose a symbol to display:", SYMBOLS)
    df = fetch_ohlcv(selected_symbol, INTERVAL)
    df = get_signals(df)
    st.line_chart(df[['close', 'ema5', 'ema9']].set_index(df['timestamp']))

    st.markdown("---")
    st.write("**Last updated:**", datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'))
