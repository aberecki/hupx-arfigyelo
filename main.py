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

PRICE_LIMIT = 50.0 

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
        print(f"✅ Mentve a másnapi ({start_date}) adat.")
    except Exception as e:
        print(f"❌ JSON hiba: {e}")

# --- 3. ÉRTESÍTÉSEK ---
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
    print("--- INDÍTÁS: MÁSNAPI ÁRAK FIGYELÉSE (15:00-as futás) ---")
    if not API_KEY: return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        
        # DÁTUM: Célzottan a HOLNAPI nap (00:00-tól 24:00-ig)
        now = pd.Timestamp.now(tz='Europe/Budapest')
        target_day = (now + pd.Timedelta(days=1)).normalize()
        
        start = target_day
        end = start + pd.Timedelta(days=1)
        
        print(f"🔎 Lekérdezés a holnapi napra: {start.date()}")

        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print(f"⚠️ Nincs adat holnapra ({start.date()}).")
            return

        # Csak a holnapi napot mentjük
        target_prices = prices[prices.index.normalize() == target_day]
        save_to_json(target_prices, target_day.date())

        # Értesítés küldése
        cheap_hours = target_prices[target_prices < PRICE_LIMIT]
        if not cheap_hours.empty:
            min_p = target_prices.min() / 1000
            subject = f"⚡ MÁSNAPI RIASZTÁS: {target_day.date()}"
            body = f"Holnap {len(cheap_hours)} órán át lesz olcsó az áram!\nMinimum: {min_p:.4f} €/kWh"
            
            send_pushover(subject, body)
            send_email(subject, body)
            print("📧 Értesítés elküldve.")
            
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    check_prices()
