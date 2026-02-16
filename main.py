import os
import json
import smtplib
import requests
import traceback
import pandas as pd
from email.message import EmailMessage
from entsoe import EntsoePandasClient

# VERZIÓ: 3.0 - MÁSNAPI ÉLES ÜZEMMÓD (2026)
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
        print(f"✅ SIKER: prices.json frissítve ({start_date})")
    except Exception as e:
        print(f"❌ JSON hiba: {e}")

# --- 3. FŐ PROGRAM ---
def check_prices():
    # EBBŐL A FELIRATBÓL FOGOD LÁTNI, HOGY EZ MÁR AZ ÚJ KÓD:
    print("--- !!!INDÍTÁS: MÁSNAPI ÁRAK ÉLES LEKÉRDEZÉSE (VERZIÓ 3.0)!!! ---")
    
    if not API_KEY: 
        print("Hiba: Nincs API kulcs!")
        return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        
        # DÁTUM: Célzottan a HOLNAPI nap
        now = pd.Timestamp.now(tz='Europe/Budapest')
        target_day = (now + pd.Timedelta(days=1)).normalize()
        
        start = target_day
        end = start + pd.Timedelta(days=1)
        
        print(f"🔎 Lekérdezés a holnapi napra: {start.date()}")

        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print(f"⚠️ Nincs adat holnapra ({start.date()}).")
            return

        target_prices = prices[prices.index.normalize() == target_day]
        save_to_json(target_prices, target_day.date())
            
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    check_prices()
