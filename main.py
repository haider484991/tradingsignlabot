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


def load_symbols() -> list:
    """Load symbols from CSV."""
    symbols = []
    try:
        with open('stocks.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sym = row.get('symbol', '').strip()
                if sym:
                    if '-USD' in sym:
                        symbols.append(sym)
                    else:
                        symbols.append(f"{sym}.NS")
    except Exception as e:
        print(f"❌ Error loading symbols: {e}")
    return symbols


def fetch_and_analyze(symbol: str) -> dict:
    """Fetch data and analyze a single symbol."""
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
            'cond1': cond1, 'cond2': cond2, 'cond3': cond3, 'cond4': cond4
        }
    except:
        return None


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
    """Process and send alerts for signals."""
    global alerted_symbols
    
    new_signals = []
    
    with alert_lock:
        for sig in signals:
            if sig['symbol'] not in alerted_symbols:
                new_signals.append(sig)
                alerted_symbols.add(sig['symbol'])
    
    if new_signals:
        print(f"\n🚨 {len(new_signals)} NEW SIGNALS!")
        
        for sig in new_signals:
            msg = f"""🚨 *BREAKOUT ALERT*

📊 *{sig['symbol']}*
💰 Price: ₹{sig['price']}
📈 RSI: {sig['rsi']}
📊 Volume: {sig['volume_ratio']}x avg
✅ Conditions: {sig['conditions_met']}/4

{'✅' if sig['cond1'] else '❌'} BB Breakout
{'✅' if sig['cond2'] else '❌'} Volume Spike
{'✅' if sig['cond3'] else '❌'} Price Up
{'✅' if sig['cond4'] else '❌'} RSI Momentum

⏰ {datetime.now().strftime('%H:%M:%S')}"""
            
            print(f"   🚨 {sig['symbol']} - ₹{sig['price']}")
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
