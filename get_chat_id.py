"""
Get Private Channel ID
======================
Run this AFTER:
1. Adding @stockscanner48_bot as admin to your private channel
2. Sending a "test" message in the channel
"""

import requests

TOKEN = "7924969775:AAEd6tX0RMFrDwrlxrS-j3Q3yMqpOhEPc3k"
URL = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

print("🔍 Looking for Channel ID...")

try:
    response = requests.get(URL, timeout=30).json()
    
    if "result" in response and len(response["result"]) > 0:
        found = False
        
        for update in response["result"]:
            # Look for channel_post updates
            if "channel_post" in update:
                chat = update["channel_post"]["chat"]
                print(f"\n✅ FOUND IT!")
                print(f"📢 Channel: {chat.get('title', 'Unknown')}")
                print(f"🆔 CHANNEL ID: {chat['id']}")
                print(f"\nUpdate your .env file with:")
                print(f"CHAT_ID={chat['id']}")
                found = True
                break
            
            # Also check my_chat_member (when bot is added)
            if "my_chat_member" in update:
                chat = update["my_chat_member"]["chat"]
                if chat.get("type") == "channel":
                    print(f"\n✅ FOUND IT!")
                    print(f"📢 Channel: {chat.get('title', 'Unknown')}")
                    print(f"🆔 CHANNEL ID: {chat['id']}")
                    print(f"\nUpdate your .env file with:")
                    print(f"CHAT_ID={chat['id']}")
                    found = True
                    break
        
        if not found:
            print("\n❌ No channel messages found.")
            print("\nMake sure you:")
            print("1. Added @stockscanner48_bot as ADMIN to your channel")
            print("2. Gave it 'Post Messages' permission")
            print("3. Sent a 'test' message in the channel")
            print("\nThen run this script again!")
            print(f"\nDebug - Raw response: {response}")
    else:
        print("\n❌ No updates found.")
        print("Add the bot to your channel and send 'test' message first.")
        print(f"\nDebug: {response}")

except Exception as e:
    print(f"Error: {e}")
    print("\nNote: If you're getting a timeout, Telegram may be blocked on your network.")
    print("This script will work on Railway after deployment.")
