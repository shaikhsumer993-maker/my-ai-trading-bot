import json
import pandas as pd
import yfinance as yf
from google import genai
from google.genai import types
import os
import requests
import sys

# 🔐 Environment Variables (GitHub Secrets)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TICKER = "AAPL"

if not GEMINI_API_KEY:
    print("❌ ERROR: GEMINI_API_KEY is missing in GitHub Secrets!")
    sys.exit(0)

try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"❌ ERROR: Failed to initialize Gemini Client: {e}")
    sys.exit(0)

def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: 
        print("⚠️ Telegram configuration missing!")
        return
    
    # 🧼 टोकन को पूरी तरह साफ करना ताकि कोई गलत URL न बने
    clean_token = str(TELEGRAM_TOKEN).strip()
    if "telegram.org" in clean_token:
        # अगर टोकन में गलती से यूआरएल आ गया है, तो उसे केवल मुख्य टोकन भाग में बदलें
        clean_token = clean_token.split('/')[-1]

    url = f"https://telegram.org{clean_token}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    
    try:
        res = requests.post(url, json=payload)
        print(f"📡 Telegram API Status: {res.status_code}")
    except Exception as e:
        # 🛡️ अगर URL में फिर भी एरर हो, तो कोड क्रैश होने के बजाय वॉर्निंग प्रिंट करेगा
        print(f"⚠️ Telegram Send Failed due to invalid configuration: {e}")

def fetch_market_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1mo")
        if df.empty: 
            df = stock.history(period="3mo")
            if df.empty: return None
            
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        latest = df.iloc[-1]
        prev_close = df.iloc[-2]['Close'] if len(df) > 1 else latest['Close']
        
        return {
            "Ticker": ticker,
            "Current_Price": round(latest['Close'], 2),
            "Daily_Change_Percent": round(((latest['Close'] - prev_close) / prev_close) * 100, 2),
            "SMA_20": round(latest['SMA_20'], 2) if not pd.isna(latest['SMA_20']) else round(latest['Close'], 2)
        }
    except Exception as e:
        print(f"⚠️ Market Data Fetch Error: {e}")
        return None

def call_gemini_agent(prompt):
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️ Agent Parsing Error: {e}")
        return {"signal": "HOLD", "analysis_rationale": "AI communication fallback triggered."}

def run_trading_software():
    print("📥 Step 1: Fetching market data...")
    market_info = fetch_market_data(TICKER)
    if not market_info: 
        print("❌ ERROR: Could not fetch data from Yahoo Finance.")
        return
    print(f"📊 Market State: Price ${market_info['Current_Price']} ({market_info['Daily_Change_Percent']}%)")
    
    # Technical Analyst Agent
    print("🧠 Step 2: Consulting Technical Analyst...")
    analyst_prompt = f"You are Technical Analyst. Analyze: {json.dumps(market_info)}. Output JSON with EXACT keys: 'signal' (must be BUY, SELL, or HOLD), 'analysis_rationale'."
    analyst_verdict = call_gemini_agent(analyst_prompt)
    signal = analyst_verdict.get('signal', 'HOLD')
    rationale = analyst_verdict.get('analysis_rationale', 'No rationale provided')
    print(f"🤖 Analyst Verdict: {signal}")
    
    # Risk Manager Agent
    print("🛡️ Step 3: Running Safety Check...")
    risk_prompt = f"You are Risk Manager. Check this proposal: {json.dumps(analyst_verdict)} for {TICKER}. Output JSON with EXACT keys: 'approved' (must be true or false), 'risk_commentary'."
    risk_verdict = call_gemini_agent(risk_prompt)
    approved = risk_verdict.get('approved', False)
    print(f"🛡️ Risk Verdict: Approved -> {approved}")
    
    # Build Telegram Message
    status_msg = f"📊 *AI Trading Bot Report ({TICKER})*\n\n"
    status_msg += f"• Price: ${market_info['Current_Price']} ({market_info['Daily_Change_Percent']}%)\n"
    status_msg += f"• AI Signal: *{signal}*\n"
    status_msg += f"• Reason: {rationale}\n"
    status_msg += f"• Risk Approved: {approved}\n\n"

    if approved and signal in ["BUY", "SELL"]:
        status_msg += f"🚀 *Execution:* Signal generated! Ready for trade."
    else:
        status_msg += "❌ *Execution:* No Trade Action Taken (Hold/Risk Block)."
        
    print("📤 Step 4: Dispatching Telegram Notification...")
    send_telegram_message(status_msg)
    print("🏁 Bot execution finished successfully!")

if __name__ == "__main__":
    run_trading_software()
