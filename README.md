# NSE & Crypto Breakout Scanner

Real-time market scanner with Telegram alerts. Runs continuously in the cloud.

## Features
- ⚡ **Parallel scanning** - 20 threads for fast analysis
- 🔄 **Continuous mode** - Rescans every 5 minutes during market hours
- 📱 **Telegram alerts** - Instant notifications on breakouts
- ☁️ **Cloud ready** - Deploy to Railway/Render for free

## Quick Deploy to Railway (FREE)

1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/trading-scanner.git
   git push -u origin main
   ```

2. **Deploy to Railway:**
   - Go to [railway.app](https://railway.app)
   - Click "New Project" → "Deploy from GitHub"
   - Select your repository
   - Add environment variables:
     - `TELEGRAM_BOT_TOKEN` = your bot token
     - `CHAT_ID` = your chat id
   - Click Deploy!

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "TELEGRAM_BOT_TOKEN=your_token" > .env
echo "CHAT_ID=your_chat_id" >> .env

# Run single scan
python main.py --once

# Run continuous mode
python main.py
```

## Strategy

Signals when 3/4 conditions met:
1. ✅ BB Breakout - Close > Upper Bollinger Band
2. ✅ Volume Spike - Volume > 1.5x average
3. ✅ Continuation - Price up from yesterday
4. ✅ Momentum - RSI > 50

## Files

- `main.py` - Main scanner script
- `stocks.csv` - 1865 symbols (NSE + Crypto)
- `fetch_symbols.py` - Update symbol list
- `Procfile` - Cloud deployment config
- `railway.json` - Railway.app config
