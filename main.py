"""
NSE & Crypto Breakout Scanner - CLOUD READY
============================================
- Fast parallel scanning with threading
- Continuous loop mode
- Telegram alerts
- Ready for Railway/Render deployment
"""

import os
import csv
import json
import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from dotenv import load_dotenv
import threading

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

# Scanning settings
MAX_WORKERS = 20  # Parallel threads for fast scanning
SCAN_INTERVAL_MINUTES = 5  # How often to rescan (during market hours)
CONTINUOUS_MODE = True  # Keep running in loop

# Technical parameters
RSI_LENGTH = 14
BB_LENGTH = 20
BB_STD = 2.0
VOLUME_SMA_LENGTH = 10
VOLUME_MULTIPLIER = 1.5
RSI_THRESHOLD = 50

# Track already alerted symbols (don't spam)
alerted_symbols = set()
alert_lock = threading.Lock()

# Trade state file for persistence
TRADE_STATE_FILE = "trade_state.json"

# ============================================================================
# TRADE STATE MANAGEMENT (matches Pine Script's var in_long/in_short)
# ============================================================================
def load_trade_state() -> dict:
    """Load trade state from JSON file."""
    try:
        if os.path.exists(TRADE_STATE_FILE):
            with open(TRADE_STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading trade state: {e}")
    return {}  # {symbol: 'LONG' or 'SHORT'}


def save_trade_state(state: dict):
    """Save trade state to JSON file."""
    try:
        with open(TRADE_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"⚠️ Error saving trade state: {e}")


# Global trade state
trade_state = load_trade_state()
trade_state_lock = threading.Lock()


def load_symbols() -> list:
    """Load CRYPTO symbols only from CSV."""
    symbols = []
    try:
        with open('stocks.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = row.get('symbol', '').strip()
                if sym and '-USD' in sym:
                    # Only load crypto symbols
                    symbols.append(sym)
    except Exception as e:
        print(f"❌ Error loading symbols: {e}")
    return symbols


def fetch_and_analyze_stock(symbol: str) -> dict:
    """Fetch data and analyze a single STOCK symbol (Daily timeframe)."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="50d", interval="1d")
        
        if df.empty or len(df) < 25:
            return None
        
        # Calculate indicators
        df['RSI'] = calculate_rsi(df['Close'])
        middle = df['Close'].rolling(20).mean()
        std = df['Close'].rolling(20).std()
        df['BB_Upper'] = middle + (std * 2)
        df['Vol_SMA'] = df['Volume'].rolling(10).mean()
        
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        
        # Check conditions
        cond1 = yesterday['Close'] > yesterday['BB_Upper']
        cond2 = yesterday['Volume'] > (VOLUME_MULTIPLIER * yesterday['Vol_SMA'])
        cond3 = today['Close'] > yesterday['Close']
        cond4 = today['RSI'] > RSI_THRESHOLD
        
        conditions_met = sum([cond1, cond2, cond3, cond4])
        
        return {
            'symbol': symbol,
            'price': round(today['Close'], 2),
            'rsi': round(today['RSI'], 2),
            'volume_ratio': round(yesterday['Volume'] / max(yesterday['Vol_SMA'], 1), 2),
            'conditions_met': conditions_met,
            'is_signal': conditions_met >= 3,
            'signal_type': 'STOCK',
            'cond1': cond1, 'cond2': cond2, 'cond3': cond3, 'cond4': cond4
        }
    except:
        return None


def fetch_and_analyze_crypto(symbol: str) -> dict:
    """
    Fetch data and analyze a CRYPTO symbol using NSE Bollinger Squeeze Pro strategy.
    Uses 15-minute timeframe with:
    - 5-bar squeeze lookback (ta.lowest(bb_width, 5) < 0.10)
    - EMA200 trend filter
    - Volume spike filter (1.5x avg)
    - Exit at opposite band (stop) + 3% trailing profit
    """
    global trade_state
    
    try:
        ticker = yf.Ticker(symbol)
        # Fetch 15m data (max ~60 days available for 15m)
        df = ticker.history(period="1mo", interval="15m")
        
        if df.empty or len(df) < 210:  # Need at least 210 bars for EMA200
            return None
        
        # --- INDICATORS ---
        # Bollinger Bands (length=20, mult=2.0)
        df['BB_Mid'] = df['Close'].rolling(20).mean()
        df['BB_Std'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['BB_Mid'] + (df['BB_Std'] * 2)
        df['BB_Lower'] = df['BB_Mid'] - (df['BB_Std'] * 2)
        
        # BB Width
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Mid']
        
        # Squeeze: ta.lowest(bb_width, 5) < 0.10 (5-bar lookback)
        df['BB_Width_Min'] = df['BB_Width'].rolling(5).min()
        df['Is_Squeezed'] = df['BB_Width_Min'] < 0.10
        
        # EMA 200
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        # Volume SMA (length=20)
        df['Vol_SMA'] = df['Volume'].rolling(20).mean()
        df['Vol_Spike'] = df['Volume'] > (df['Vol_SMA'] * 1.5)
        
        # Trend filters
        df['Trend_Long'] = df['Close'] > df['EMA200']  # Bullish
        df['Trend_Short'] = df['Close'] < df['EMA200']  # Bearish
        
        today = df.iloc[-1]
        
        # Get current position state
        with trade_state_lock:
            position_data = trade_state.get(symbol, None)
        
        # Position data format: {'type': 'LONG'/'SHORT', 'entry_price': X, 'high_since': Y}
        in_long = position_data is not None and position_data.get('type') == 'LONG'
        in_short = position_data is not None and position_data.get('type') == 'SHORT'
        
        # --- ENTRY SIGNALS ---
        is_squeezed = today['Is_Squeezed']
        vol_ok = today['Vol_Spike']
        
        # LONG: is_squeezed AND close > upper AND trend_long AND vol_ok
        long_cond = (not in_long and not in_short and
                     is_squeezed and 
                     today['Close'] > today['BB_Upper'] and 
                     today['Trend_Long'] and 
                     vol_ok)
        
        # SHORT: is_squeezed AND close < lower AND trend_short AND vol_ok
        short_cond = (not in_long and not in_short and
                      is_squeezed and 
                      today['Close'] < today['BB_Lower'] and 
                      today['Trend_Short'] and 
                      vol_ok)
        
        # --- EXIT SIGNALS ---
        # For LONG: Stop at lower band OR 3% trailing profit hit
        # For SHORT: Stop at upper band OR 3% trailing profit hit
        exit_long = False
        exit_short = False
        trail_pct = 3.0  # 3% trailing profit
        
        if in_long:
            entry_price = position_data.get('entry_price', today['Close'])
            high_since = position_data.get('high_since', entry_price)
            
            # Update high since entry
            if today['Close'] > high_since:
                high_since = today['Close']
                with trade_state_lock:
                    trade_state[symbol]['high_since'] = high_since
                    save_trade_state(trade_state)
            
            # Stop loss at lower band
            stop_hit = today['Close'] < today['BB_Lower']
            # Trailing profit: if price drops 3% from high
            trail_stop = high_since * (1 - trail_pct/100)
            trail_hit = today['Close'] < trail_stop
            
            exit_long = stop_hit or trail_hit
        
        if in_short:
            entry_price = position_data.get('entry_price', today['Close'])
            low_since = position_data.get('low_since', entry_price)
            
            # Update low since entry
            if today['Close'] < low_since:
                low_since = today['Close']
                with trade_state_lock:
                    trade_state[symbol]['low_since'] = low_since
                    save_trade_state(trade_state)
            
            # Stop loss at upper band
            stop_hit = today['Close'] > today['BB_Upper']
            # Trailing profit: if price rises 3% from low
            trail_stop = low_since * (1 + trail_pct/100)
            trail_hit = today['Close'] > trail_stop
            
            exit_short = stop_hit or trail_hit
        
        # Determine signal type
        signal_type = None
        is_signal = False
        
        if long_cond:
            signal_type = 'LONG'
            is_signal = True
        elif short_cond:
            signal_type = 'SHORT'
            is_signal = True
        elif exit_long:
            signal_type = 'EXIT_LONG'
            is_signal = True
        elif exit_short:
            signal_type = 'EXIT_SHORT'
            is_signal = True
        
        return {
            'symbol': symbol,
            'price': round(today['Close'], 2),
            'ema200': round(today['EMA200'], 2),
            'bb_upper': round(today['BB_Upper'], 2),
            'bb_lower': round(today['BB_Lower'], 2),
            'bb_mid': round(today['BB_Mid'], 2),
            'volume_ratio': round(today['Volume'] / max(today['Vol_SMA'], 1), 2),
            'is_squeezed': is_squeezed,
            'is_signal': is_signal,
            'signal_type': signal_type if is_signal else 'CRYPTO',
            'current_position': position_data,
            'conditions_met': 4 if is_signal else 0,
            'cond1': is_squeezed,  # Squeeze active (5-bar lookback)
            'cond2': vol_ok,  # Volume spike
            'cond3': today['Trend_Long'] if signal_type == 'LONG' else today['Trend_Short'],  # Trend filter
            'cond4': today['Close'] > today['BB_Upper'] if signal_type == 'LONG' else today['Close'] < today['BB_Lower']  # BB breakout
        }
    except Exception as e:
        return None


def fetch_and_analyze(symbol: str) -> dict:
    """Route to the appropriate analyzer based on symbol type."""
    if '-USD' in symbol:
        return fetch_and_analyze_crypto(symbol)
    else:
        return fetch_and_analyze_stock(symbol)


def calculate_rsi(series, length=14):
    """Fast RSI calculation."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(length, min_periods=1).mean()
    avg_loss = loss.rolling(length, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.inf)
    return 100 - (100 / (1 + rs))


def send_telegram(message: str) -> bool:
    """Send Telegram message."""
    if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        response = requests.post(url, json={
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def scan_all_parallel(symbols: list) -> tuple:
    """Scan all symbols in parallel using thread pool."""
    signals = []
    near_signals = []
    scanned = 0
    
    print(f"\n⚡ Parallel scanning {len(symbols)} symbols with {MAX_WORKERS} threads...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_and_analyze, sym): sym for sym in symbols}
        
        for future in as_completed(futures):
            result = future.result()
            scanned += 1
            
            if scanned % 100 == 0:
                print(f"   Scanned {scanned}/{len(symbols)}...")
            
            if result is None:
                continue
            
            if result['is_signal']:
                signals.append(result)
            elif result['conditions_met'] >= 2:
                near_signals.append(result)
    
    elapsed = time.time() - start_time
    print(f"✅ Scanned {scanned} symbols in {elapsed:.1f}s ({scanned/elapsed:.1f} symbols/sec)")
    
    return signals, near_signals


def process_signals(signals: list, near_signals: list):
    """Process and send alerts for signals. Updates trade state on entries/exits."""
    global alerted_symbols, trade_state
    
    new_signals = []
    
    # For EXIT signals, we don't check alerted_symbols (always alert exits)
    with alert_lock:
        for sig in signals:
            signal_type = sig.get('signal_type')
            symbol = sig['symbol']
            
            # EXIT signals should always be processed (not spam-filtered)
            if signal_type in ['EXIT_LONG', 'EXIT_SHORT']:
                new_signals.append(sig)
            # ENTRY signals check alerted_symbols to prevent spam
            elif symbol not in alerted_symbols:
                new_signals.append(sig)
                alerted_symbols.add(symbol)
    
    if new_signals:
        print(f"\n🚨 {len(new_signals)} NEW SIGNALS!")
        
        for sig in new_signals:
            signal_type = sig.get('signal_type')
            symbol = sig['symbol']
            
            # Update trade state based on signal type
            with trade_state_lock:
                if signal_type == 'LONG':
                    trade_state[symbol] = {
                        'type': 'LONG',
                        'entry_price': sig['price'],
                        'high_since': sig['price']
                    }
                    save_trade_state(trade_state)
                elif signal_type == 'SHORT':
                    trade_state[symbol] = {
                        'type': 'SHORT',
                        'entry_price': sig['price'],
                        'low_since': sig['price']
                    }
                    save_trade_state(trade_state)
                elif signal_type in ['EXIT_LONG', 'EXIT_SHORT']:
                    if symbol in trade_state:
                        del trade_state[symbol]
                        save_trade_state(trade_state)
                    # Remove from alerted_symbols so new entries can be detected
                    if symbol in alerted_symbols:
                        alerted_symbols.discard(symbol)
            
            # Format message based on signal type
            if signal_type == 'LONG':
                stop_price = sig.get('bb_lower', 0)
                trail_exit = round(sig['price'] * 0.97, 2)  # 3% below entry as trailing reference
                msg = f"""🟢 *LONG ENTRY*

📈 *{symbol}*

💰 *Entry Price: ${sig['price']}*
🛑 *Stop Loss: ${stop_price}* (Lower Band)
📈 *Trail Exit: ${trail_exit}* (3% from high)

📊 Volume: {sig['volume_ratio']}x avg
📈 EMA200: ${sig.get('ema200', 'N/A')}

⏰ {datetime.now().strftime('%H:%M:%S')}"""

            elif signal_type == 'SHORT':
                stop_price = sig.get('bb_upper', 0)
                trail_exit = round(sig['price'] * 1.03, 2)  # 3% above entry as trailing reference
                msg = f"""🔴 *SHORT ENTRY*

📉 *{symbol}*

💰 *Entry Price: ${sig['price']}*
🛑 *Stop Loss: ${stop_price}* (Upper Band)
📉 *Trail Exit: ${trail_exit}* (3% from low)

📊 Volume: {sig['volume_ratio']}x avg
📈 EMA200: ${sig.get('ema200', 'N/A')}

⏰ {datetime.now().strftime('%H:%M:%S')}"""

            elif signal_type == 'EXIT_LONG':
                entry_price = sig.get('current_position', {}).get('entry_price', 'N/A') if sig.get('current_position') else 'N/A'
                msg = f"""⚪ *EXIT LONG*

📊 *{symbol}*
💰 *Entry was: ${entry_price}*
💰 *Exit Price: ${sig['price']}*

⏰ {datetime.now().strftime('%H:%M:%S')}"""

            elif signal_type == 'EXIT_SHORT':
                entry_price = sig.get('current_position', {}).get('entry_price', 'N/A') if sig.get('current_position') else 'N/A'
                msg = f"""⚪ *EXIT SHORT*

📊 *{symbol}*
💰 *Entry was: ${entry_price}*
💰 *Exit Price: ${sig['price']}*

⏰ {datetime.now().strftime('%H:%M:%S')}"""
            else:
                continue  # Skip unknown signal types
            
            emoji = "🟢" if signal_type == 'LONG' else ("🔴" if signal_type == 'SHORT' else "⚪")
            print(f"   {emoji} {symbol} - ${sig['price']} ({signal_type})")
            
            if send_telegram(msg):
                print(f"      📤 Telegram sent!")
            else:
                print(f"      ⚠️ Telegram failed")
    else:
        print(f"📊 {len(signals)} signals (already alerted), {len(near_signals)} watchlist")


def is_market_hours() -> bool:
    """Check if Indian market is open (9:15 AM - 3:30 PM IST)."""
    now = datetime.now()
    # Adjust for your timezone - this assumes IST
    market_open = now.replace(hour=9, minute=15, second=0)
    market_close = now.replace(hour=15, minute=30, second=0)
    weekday = now.weekday()
    
    return weekday < 5 and market_open <= now <= market_close


def run_continuous():
    """Run scanner in continuous loop mode."""
    global alerted_symbols
    
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     NSE & Crypto Breakout Scanner - CONTINUOUS MODE      ║
    ║     Running 24/7 with automatic rescanning               ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Test Telegram
    if TELEGRAM_BOT_TOKEN and CHAT_ID:
        if send_telegram("🤖 *Scanner Started*\nMonitoring markets 24/7..."):
            print("✅ Telegram connected!")
        else:
            print("⚠️ Telegram connection failed")
    else:
        print("⚠️ Telegram not configured")
    
    symbols = load_symbols()
    print(f"📊 Loaded {len(symbols)} symbols")
    
    scan_count = 0
    
    while True:
        scan_count += 1
        print(f"\n{'='*60}")
        print(f"🔄 SCAN #{scan_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Reset alerted symbols at market open
        if is_market_hours() and scan_count == 1:
            alerted_symbols.clear()
            print("📈 Market hours - alerts reset")
        
        # Run parallel scan
        signals, near_signals = scan_all_parallel(symbols)
        
        # Process signals
        process_signals(signals, near_signals)
        
        # Summary
        print(f"\n📊 Summary: {len(signals)} signals, {len(near_signals)} watchlist")
        
        # Wait before next scan
        wait_minutes = SCAN_INTERVAL_MINUTES
        if not is_market_hours():
            wait_minutes = 30  # Slower scanning outside market hours
            print(f"🌙 Outside market hours - next scan in {wait_minutes} min")
        else:
            print(f"⏰ Next scan in {wait_minutes} min")
        
        if not CONTINUOUS_MODE:
            break
            
        time.sleep(wait_minutes * 60)


def run_once():
    """Run a single scan."""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     NSE & Crypto Breakout Scanner - SINGLE SCAN          ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    symbols = load_symbols()
    print(f"📊 Loaded {len(symbols)} symbols")
    
    signals, near_signals = scan_all_parallel(symbols)
    process_signals(signals, near_signals)
    
    print(f"\n📊 COMPLETE: {len(signals)} signals, {len(near_signals)} watchlist")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_once()
    else:
        run_continuous()
