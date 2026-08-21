import json
import pandas as pd
import yfinance as yf
from google import genai
from google.genai import types
import os
import requests

# 🔐 Environment Variables (GitHub Secrets)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")

ALPACA_BASE_URL = "https://alpaca.markets"

# 🚀 Initialize New Google GenAI SDK Client
client = genai.Client(api_key=GEMINI_API_KEY)
TICKER = "AAPL"

def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def execute_paper_trade(ticker, action, qty=1):
    if not ALPACA_KEY or not ALPACA_SECRET: return "❌ Alpaca Keys Missing"
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
        "Content-Type": "application/json"
    }
    data = {"symbol": ticker, "qty": str(qty), "side": action.lower(), "type": "market", "time_in_force": "day"}
    res = requests.post(ALPACA_BASE_URL, json=data, headers=headers)
    
    # FIXED: Explicitly checking for successful response codes 200 or 201
    return "✅ Alpaca Order Placed!" if res.status_code in [200, 201] else f"❌ Alpaca Error: {res.text}"

def fetch_market_data(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="1mo")
    if df.empty: return None
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    latest = df.iloc[-1]
    prev_close = df['Close'].iloc[-2]
    return {
        "Ticker": ticker,
        "Current_Price": round(latest['Close'], 2),
        "Daily_Change_Percent": round(((latest['Close'] - prev_close) / prev_close) * 100, 2),
        "SMA_20": round(latest['SMA_20'], 2) if not pd.isna(latest['SMA_20']) else 0
    }

# 🧠 Gemini 2.0 Agent Function
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
        print(f"Agent Parsing Error: {e}")
        return {}

def run_trading_software():
    market_info = fetch_market_data(TICKER)
    if not market_info: return
    print(f"📊 Market State: Price ${market_info['Current_Price']} ({market_info['Daily_Change_Percent']}%)")
    
    # Technical Analyst [Paper]
    analyst_prompt = f"You are Technical Analyst. Analyze: {json.dumps(market_info)}. Output JSON with EXACT keys: 'signal' (must be BUY, SELL, or HOLD), 'analysis_rationale'."
    analyst_verdict = call_gemini_agent(analyst_prompt)
    signal = analyst_verdict.get('signal', 'HOLD')
    rationale = analyst_verdict.get('analysis_rationale', 'No rationale provided')
    print(f"🤖 Analyst Verdict: {signal}")
    
    # Risk Manager [Paper]
    risk_prompt = f"You are Risk Manager. Check this proposal: {json.dumps(analyst_verdict)} for {TICKER}. Output JSON with EXACT keys: 'approved' (must be true or false), 'risk_commentary'."
    risk_verdict = call_gemini_agent(risk_prompt)
    approved = risk_verdict.get('approved', False)
    print(f"🛡️ Risk Verdict: Approved -> {approved}")
    
    status_msg = f"📊 *AI Trading Bot Report ({TICKER})*\n\n"
    status_msg += f"• Price: ${market_info['Current_Price']} ({market_info['Daily_Change_Percent']}%)\n"
    status_msg += f"• AI Signal: *{signal}*\n"
    status_msg += f"• Reason: {rationale}\n"
    status_msg += f"• Risk Approved: {approved}\n\n"

    if approved and signal in ["BUY", "SELL"]:
        trade_result = execute_paper_trade(TICKER, signal)
        status_msg += f"🚀 *Execution:* {trade_result}"
    else:
        status_msg += "❌ *Execution:* No Trade Action Taken (Hold/Risk Block)."
        
    send_telegram_message(status_msg)

if __name__ == "__main__":
    run_trading_software()
    
