Here is a complete, professional Project Blueprint (.md) file. You can save this text as project_requirements.md and drop it directly into Cursor, Windsurf, or any AI coding assistant. It contains every instruction needed to build the bot exactly as your client requested.

File Content: project_requirements.md
Markdown

# Project: NSE & Crypto Daily Breakout Scanner with Telegram Alerts

## 1. Project Overview
**Goal:** Build a Python-based market scanner that analyzes 2,600+ NSE stocks and Cryptocurrency pairs on a "Daily" timeframe.
**Output:** If a stock meets specific technical criteria (High Volume Bollinger Breakout + Continuation), the bot must send a real-time alert to a Telegram channel/chat.
**Constraints:** - Must use free data sources (Yahoo Finance API).
- Must handle a large list of tickers (read from a CSV file).
- Must be robust (error handling for API limits).

---

## 2. Tech Stack & Libraries
* **Language:** Python 3.9+
* **Data Source:** `yfinance` (Yahoo Finance)
* **Technical Analysis:** `pandas_ta` (Pandas Technical Analysis)
* **Data Manipulation:** `pandas`
* **Alerting:** `requests` (for Telegram API)
* **Input:** `csv` module

### `requirements.txt`
```text
yfinance
pandas
pandas_ta
requests
3. Directory Structure
Plaintext

/stock-scanner
│
├── main.py            # The primary script that runs the scan
├── requirements.txt   # Dependencies
├── stocks.csv         # Input file containing the list of symbols
└── .env               # (Optional) For storing Telegram Token securely
4. Functional Logic
A. Input Handling (stocks.csv)
The program should read a CSV file containing a list of symbols.

NSE Stocks: If the symbol is an Indian stock (e.g., RELIANCE), the code must append .NS to it (e.g., RELIANCE.NS) for yfinance compatibility.

Crypto: If the symbol is crypto (e.g., BTC-USD), leave it as is.

B. Data Fetching
Loop: Iterate through each symbol in the CSV.

API Call: Fetch 100 days of history on the 1d (Daily) interval using yfinance.

Rate Limiting: Add a small time.sleep(0.5) between requests to avoid IP bans.

Error Handling: Wrap the fetch in a try/except block. If a symbol fails, log it and continue to the next one; do NOT crash the script.

C. Technical Indicators (Calculated via pandas_ta)
For every stock, calculate:

RSI (Relative Strength Index): Length = 14.

Bollinger Bands: Length = 20, Std Dev = 2.0.

Volume SMA: Simple Moving Average of Volume, Length = 10.

D. The Strategy (The Core Logic)
We are looking for a "High Volume Breakout with Continuation." Access the dataframe by index: -1 is Today (Live/Current), -2 is Yesterday (Confirmed).

The 4 Conditions:

Yesterday's Setup: The stock's Close Price (Yesterday) was GREATER than the Upper Bollinger Band (Yesterday).

Volume Spike: The Volume (Yesterday) was GREATER than 3x the Volume SMA (Yesterday).

Logic: Vol[-2] > (3 * VolSMA[-2])

Continuation (Today): The Current Price (Today) is GREATER than Yesterday's High.

Momentum (Today): The Current RSI (Today) is GREATER than 60.

Trigger: IF (Cond1 AND Cond2 AND Cond3 AND Cond4) are all TRUE -> Send Alert.

5. Alerting System (Telegram)
Use a simple HTTP POST request to the Telegram Bot API.

Function Signature: send_telegram_message(symbol, price, rsi, volume_info)

Message Format:

Plaintext

🚨 BREAKOUT ALERT 🚨

Symbol: RELIANCE.NS
Price: 2450.00
RSI: 65.4

Reason:
✅ BB Breakout (Yesterday)
✅ Vol > 3x Avg (Yesterday)
✅ Breaking High (Today)
6. Implementation Guidelines for AI
Create a dummy stocks.csv file in the code with 5-10 examples (mix of NSE and Crypto) for testing.

Configuration: Use variables at the top of the file for TELEGRAM_BOT_TOKEN and CHAT_ID.

Console Logging: Print "Scanning [Symbol]..." to the console so the user knows it's working.

Validation: Ensure that pandas_ta calculates the Bollinger Bands correctly (it usually outputs columns like BBU_20_2.0). Dynamically find the column names if needed.

7. Example Data for Testing
If the AI needs to generate a test CSV, use these:

Code snippet

RELIANCE
TCS
INFY
BTC-USD
ETH-USD
TATAMOTORS
SBIN

***

### How to use this:
1.  **Copy** the code block above.
2.  **Create a file** on your computer named `prompt.md` or `project.md`.
3.  **Paste** the content in.
4.  **Open Cursor** (or your AI builder).
5.  **Drag and drop** this file into the chat or attach it.
6.  **Type this command:**
    > "Read this project file. Build the complete Python project structure, including the `ma