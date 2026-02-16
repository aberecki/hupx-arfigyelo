import os
import json
import smtplib
import requests
import traceback
import pandas as pd
from email.message import EmailMessage
from entsoe import EntsoePandasClient

# --- 1. BEÁLLÍTÁSOK ---
def clean_secret(value):
    if not value: return ""
    return value.strip().replace('\xa0', '')

API_KEY = clean_secret(os.environ.get('ENTSOE_KEY'))
EMAIL_SENDER = clean_secret(os.environ.get('EMAIL_SENDER'))
EMAIL_PASSWORD = clean_secret(os.environ.get('EMAIL_PASSWORD'))
EMAIL_TARGET = clean_secret(os.environ.get('EMAIL_TARGET'))
PO_USER = clean_secret(os.environ.get('PUSHOVER_USER_KEY'))
PO_TOKEN = clean_secret(os.environ.get('PUSHOVER_API_TOKEN'))

# ÚJ ÁRLIMIT: 100 EUR/MWh = 0.1 EUR/kWh
# Ha az ár ez alatt van, küldünk értesítést.
PRICE_LIMIT = 100.0 

# --- 2. JSON MENTÉS ---
def save_to_json(prices, start_date):
    try:
        data_list = []
        for timestamp, price in prices.items():
            data_list.append({
                "time": timestamp.isoformat(), 
                "price_eur": round(price, 2),  
                "price_kwh": round(price / 1000, 4) 
            })
            
        with open('prices.json', 'w', encoding='utf-8') as f:
            json.dump({
                "updated": pd.Timestamp.now().isoformat(),
                "day": str(start_date),
                "data": data_list
            }, f, indent=4)
        print(f"✅ Adatok mentve: {start_date}")
    except Exception as e:
        print(f"❌ JSON hiba: {e}")

# --- 3. ÉRTESÍTÉSI FUNKCIÓK ---
def send_pushover(title, message):
    if not PO_USER or not PO_TOKEN: return
    try:
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": PO_TOKEN, "user": PO_USER, "title": title, "message": message, "priority": 1
        })
    except: pass

def send_email(subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD: return
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_TARGET
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
    except: pass

# --- 4. FŐ PROGRAM ---
def check_prices():
    print(f"--- INDÍTÁS: ADATLEKÉRDEZÉS (Limit: {PRICE_LIMIT/1000} EUR/kWh) ---")
    if not API_KEY: return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        now = pd.Timestamp.now(tz='Europe/Budapest')
        target_day = (now + pd.Timedelta(days=1)).normalize()
        start = target_day
        end = start + pd.Timedelta(days=1)
        
        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print("⚠️ Nincs adat holnapra.")
            return

        target_prices =
