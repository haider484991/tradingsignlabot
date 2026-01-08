"""
Get Telegram Chat ID
"""
import requests

TOKEN = "7924969775:AAEd6tX0RMFrDwrlxrS-j3Q3yMqpOhEPc3k"
URL = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

print("🔍 Looking for your Chat ID...")

try:
    response = requests.get(URL, timeout=30).json()
    
    if "result" in response and len(response["result"]) > 0:
        chat_id = response["result"][-1]["message"]["chat"]["id"]
        first_name = response["result"][-1]["message"]["from"]["first_name"]
        
        print("\n" + "="*40)
        print(f"✅ SUCCESS! Found ID for {first_name}")
        print(f"🆔 YOUR CHAT ID IS: {chat_id}")
        print("="*40)
    else:
        print("\n❌ No messages found yet.")
        print("Please open Telegram, search for @stockscanner48_bot, and click START.")
        print("Then run this script again.")
        print(f"\nDebug: {response}")

except Exception as e:
    print(f"Error: {e}")
