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

# ÚJ LIMIT: 100 EUR/MWh = 0.1 EUR/kWh
PRICE_LIMIT = 100.0 

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
            json.dump({"updated": pd.Timestamp.now().isoformat(), "day": str(start_date), "data": data_list}, f, indent=4)
        print(f"✅ Mentve: {start_date}")
    except Exception as e:
        print(f"❌ JSON hiba: {e}")

def send_alert(subject, body):
    # E-mail küldés
    if EMAIL_SENDER and EMAIL_PASSWORD:
        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg['Subject'] = subject
            msg['From'] = EMAIL_SENDER
            msg['To'] = EMAIL_TARGET
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)
                server.send_message(msg)
        except: print("E-mail hiba")
    # Pushover küldés
    if PO_USER and PO_TOKEN:
        try: requests.post("https://api.pushover.net/1/messages.json", data={"token": PO_TOKEN, "user": PO_USER, "title": subject, "message": body})
        except: print("Pushover hiba")

def check_prices():
    print(f"--- INDÍTÁS: NEGYEDÓRÁS MONITORING (Limit: {PRICE_LIMIT/1000} EUR/kWh) ---")
    if not API_KEY: return
    try:
        client = EntsoePandasClient(api_key=API_KEY)
        now = pd.Timestamp.now(tz='Europe/Budapest')
        target_day = (now + pd.Timedelta(days=1)).normalize()
        
        # Lekérdezés (ENTSO-E automatikusan adja a negyedórásat, ha elérhető)
        prices = client.query_day_ahead_prices('HU', start=target_day, end=target_day + pd.Timedelta(days=1))
        
        if prices.empty: return

        # SZINTAKTIKAI JAVÍTÁS ITT:
        target_prices = prices[prices.index.normalize() == target_day]
        
        save_to_json(target_prices, target_day.date())

        # Értesítő, ha 0.1 EUR/kWh alá megy
        cheap_intervals = target_prices[target_prices < PRICE_LIMIT]
        if not cheap_intervals.empty:
            count = len(cheap_intervals)
            msg = f"Holnap {count} időszakban 0.1 €/kWh alatt lesz az ár!"
            send_alert(f"⚡ Áram Ár Riasztás: {target_day.date()}", msg)
            
    except Exception as e: traceback.print_exc()

if __name__ == "__main__":
    check_prices()
