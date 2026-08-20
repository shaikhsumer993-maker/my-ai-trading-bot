import json
import pandas as pd
import yfinance as yf
import google.generativeai as genai
import os

# API Key को सुरक्षित रखने के लिए हम Environment Variable का इस्तेमाल करेंगे
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
genai.configure(api_key=GEMINI_API_KEY)

TICKER = "AAPL"

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
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"response_mime_type": "application/json"}
        )
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}

def run_trading_software():
    market_info = fetch_market_data(TICKER)
    if not market_info:
        print("Error: No data")
        return
        
    print(f"📊 Market State: Price ${market_info['Current_Price']} ({market_info['Daily_Change_Percent']}%)")
    
    # Technical Analyst Agent [Paper]
    analyst_prompt = f"You are Technical Analyst. Analyze: {json.dumps(market_info)}. Output JSON with keys: 'signal' (BUY/SELL/HOLD), 'analysis_rationale'."
    analyst_verdict = call_gemini_agent(analyst_prompt)
    print(f"🤖 Analyst Verdict: {analyst_verdict.get('signal')}")
    
    # Risk Manager Agent [Paper]
    risk_prompt = f"You are Risk Manager. Check this proposal: {json.dumps(analyst_verdict)} for {TICKER}. Current price: ${market_info['Current_Price']}. Output JSON with keys: 'approved' (true/false), 'risk_commentary'."
    risk_verdict = call_gemini_agent(risk_prompt)
    print(f"🛡️ Risk Verdict: Approved -> {risk_verdict.get('approved')}")
    
    if risk_verdict.get('approved') and analyst_verdict.get('signal') != "HOLD":
        print(f"🚨 EXECUTION ALERT: {analyst_verdict.get('signal')} order triggered for {TICKER}!")
    else:
        print("❌ EXECUTION ALERT: No Trade Action Taken.")

if __name__ == "__main__":
    run_trading_software()
