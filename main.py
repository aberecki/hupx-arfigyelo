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

# --- 2. ÚJ FUNKCIÓ: ADATMENTÉS JSON-BE (PWA-HOZ) ---
def save_to_json(prices, start_date):
    """Elmenti az árakat egy prices.json fájlba a GitHub repó gyökerébe."""
    try:
        data_list = []
        for timestamp, price in prices.items():
            data_list.append({
                "time": timestamp.isoformat(), 
                "price_eur": round(price, 2),  
                "price_kwh": round(price / 1000, 4) 
            })
            
        # JSON fájl írása
        with open('prices.json', 'w', encoding='utf-8') as f:
            json.dump({
                "updated": pd.Timestamp.now().isoformat(),
                "day": str(start_date),
                "data": data_list
            }, f, indent=4)
            
        print("✅ SIKER: prices.json fájl legenerálva (Teszt adat)!")
    except Exception as e:
        print(f"❌ Hiba a JSON mentésekor: {e}")

# --- 3. ÉRTESÍTÉSEK ---
def send_pushover(title, message):
    if not PO_USER or not PO_TOKEN: return
    try:
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": PO_TOKEN, "user": PO_USER, "title": title, "message": message, "priority": 1
        })
        print("📱 Pushover elküldve.")
    except: print("Pushover hiba")

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
        print("📧 E-mail elküldve.")
    except: print("E-mail hiba")

# --- 4. FŐ PROGRAM ---
def check_prices():
    print("--- INDÍTÁS (FIX DÁTUMOS TESZT MÓD) ---")
    if not API_KEY: return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        
        # --- ITT A VÁLTOZÁS: FIX DÁTUM ---
        # Eredeti (Real-time): now = pd.Timestamp.now(tz='Europe/Budapest')
        
        # Teszt (Fix 2025-ös dátum):
        fixed_date = pd.Timestamp("2025-02-15", tz='Europe/Budapest')
        
        start = fixed_date.normalize()
        end = start + pd.Timedelta(days=1)
        
        print(f"🔎 Vizsgált nap (TESZT): {start.date()}")

        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print("⚠️ Nincs adat.")
            return

        # 1. LÉPÉS: Mentsük el az adatokat a PWA-nak!
        save_to_json(prices, start.date())

        # 2. LÉPÉS: Elemzés (Csak a logba írjuk ki, ne küldjön e-mailt a múltból)
        cheap_hours = prices[prices < PRICE_LIMIT]
        print(f"Elemzés: {len(cheap_hours)} olcsó óra található ezen a napon.")
            
    except Exception as e:
        if "NoMatchingDataError" in str(type(e)):
            print("ℹ️ Nincs adat erre a napra az ENTSO-E-n.")
        else:
            traceback.print_exc()

if __name__ == "__main__":
    check_prices()
