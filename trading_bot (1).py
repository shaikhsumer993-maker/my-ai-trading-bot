import json
import pandas as pd
import yfinance as yf
import google.generativeai as genai
import os
import requests

# 🔐 सुरक्षा गार्डराइल्स - सभी सीक्रेट्स और कीज़ गिटहब से लोड होंगी
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")

# अल्पैका पेपर ट्रेडिंग यूआरएल
ALPACA_BASE_URL = "https://alpaca.markets"

genai.configure(api_key=GEMINI_API_KEY)
TICKER = "AAPL"

# 1. टेलीग्राम अलर्ट टूल
def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram Config Missing!")
        return
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

# 2. अल्पैका ऑर्डर एग्जीक्यूशन टूल
def execute_paper_trade(ticker, action, qty=1):
    if not ALPACA_KEY or not ALPACA_SECRET:
        return "❌ Trade Execution Failed: Alpaca Keys Missing."
        
    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
        "Content-Type": "application/json"
    }
    data = {
        "symbol": ticker,
        "qty": str(qty),
        "side": action.lower(), # buy या sell
        "type": "market",
        "time_in_force": "day"
    }
    response = requests.post(ALPACA_BASE_URL, json=data, headers=headers)
    if response.status_code == 200 or response.status_code == 201:
        return f"✅ Alpaca Paper Order Successfully Placed!"
    else:
        return f"❌ Alpaca Error: {response.text}"

def fetch_market_data(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="1mo")
    if df.empty: return None
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    latest = df.iloc[-1]
    prev_close = df['Close'].iloc[-2]
    daily_change = ((latest['Close'] - prev_close) / prev_close) * 100
    return {
        "Ticker": ticker,
        "Current_Price": round(latest['Close'], 2),
        "Daily_Change_Percent": round(daily_change, 2),
        "SMA_20": round(latest['SMA_20'], 2) if not pd.isna(latest['SMA_20']) else 0
    }

def call_gemini_agent(prompt):
    try:
        model = genai.GenerativeModel(model_name="gemini-1.5-flash", generation_config={"response_mime_type": "application/json"})
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}

def run_trading_software():
    market_info = fetch_market_data(TICKER)
    if not market_info: return
    
    # एआई एजेंट्स लेयर [Paper]
    analyst_prompt = f"You are Technical Analyst. Analyze: {json.dumps(market_info)}. Output JSON with keys: 'signal' (BUY/SELL/HOLD), 'analysis_rationale'."
    analyst_verdict = call_gemini_agent(analyst_prompt)
    
    risk_prompt = f"You are Risk Manager. Check this proposal: {json.dumps(analyst_verdict)} for {TICKER}. Current price: ${market_info['Current_Price']}. Output JSON with keys: 'approved' (true/false), 'risk_commentary'."
    risk_verdict = call_gemini_agent(risk_prompt)
    
    # मेसेज ड्राफ्ट करना
    signal = analyst_verdict.get('signal', 'HOLD')
    approved = risk_verdict.get('approved', False)
    rationale = analyst_verdict.get('analysis_rationale', 'No explanation')
    
    status_msg = f"📊 *AI Trading Bot Report ({TICKER})*\n\n"
    status_msg += f"• Price: ${market_info['Current_Price']} ({market_info['Daily_Change_Percent']}%)\n"
    status_msg += f"• AI Signal: *{signal}*\n"
    status_msg += f"• Reason: {rationale}\n"
    status_msg += f"• Risk Assessment: Approved = {approved}\n\n"

    # आर्डर एग्जीक्यूशन और नोटिफिकेशन लॉजिक
    if approved and signal != "HOLD":
        trade_result = execute_paper_trade(TICKER, signal, qty=1)
        status_msg += f"🚀 *Execution:* {trade_result}"
    else:
        status_msg += "❌ *Execution:* No Trade Action Taken."
        
    # टेलीग्राम पर अलर्ट भेजना
    send_telegram_message(status_msg)

if __name__ == "__main__":
    run_trading_software()
