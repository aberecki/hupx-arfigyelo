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

# GitHub Secrets beolvasása
API_KEY = clean_secret(os.environ.get('ENTSOE_KEY'))
EMAIL_SENDER = clean_secret(os.environ.get('EMAIL_SENDER'))
EMAIL_PASSWORD = clean_secret(os.environ.get('EMAIL_PASSWORD'))
EMAIL_TARGET = clean_secret(os.environ.get('EMAIL_TARGET'))
PO_USER = clean_secret(os.environ.get('PUSHOVER_USER_KEY'))
PO_TOKEN = clean_secret(os.environ.get('PUSHOVER_API_TOKEN'))

# Riasztási limit (EUR/MWh)
PRICE_LIMIT = 50.0 

# --- 2. JSON MENTÉS A WEBOLDALNAK ---
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
        print(f"✅ SIKER: prices.json frissítve a másnapi dátummal: {start_date}")
    except Exception as e:
        print(f"❌ JSON hiba: {e}")

# --- 3. ÉRTESÍTÉSI FUNKCIÓK ---
def send_pushover(title, message):
    if not PO_USER or not PO_TOKEN: return
    try:
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": PO_TOKEN, "user": PO_USER, "title": title, "message": message, "priority": 1
        })
        print("📱 Pushover értesítés elküldve.")
    except: print("❌ Pushover hiba")

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
    except: print("❌ E-mail hiba")

# --- 4. FŐ LOGIKA ---
def check_prices():
    # Ez a felirat jelzi a logban, hogy már az ÚJ kód fut:
    print("--- INDÍTÁS: MÁSNAPI ÁRAK ÉLES LEKÉRDEZÉSE (2026) ---")
    
    if not API_KEY: 
        print("Hiba: Hiányzik az ENTSOE_KEY!")
        return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        
        # Mai időpont meghatározása
        now = pd.Timestamp.now(tz='Europe/Budapest')
        # Célzottan a HOLNAPI nap (00:00:00-tól)
        target_day = (now + pd.Timedelta(days=1)).normalize()
        
        start = target_day
        end = start + pd.Timedelta(days=1)
        
        print(f"🔎 Lekérdezés a holnapi napra: {start.date()}")

        # Adatok lekérése
        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print(f"⚠️ Nincs elérhető adat holnapra ({start.date()}).")
            return

        # Csak a holnapi nap adatait tartjuk meg
        target_prices = prices[prices.index.normalize() == target_day]

        # 1. Mentés a weboldalnak
        save_to_json(target_prices, target_day.date())

        # 2. Értesítési logika
        cheap_hours = target_prices[target_prices < PRICE_LIMIT]
        
        if not cheap_hours.empty:
            min_price = target_prices.min() / 1000
            subject = f"⚡ OLCSÓ ÁRAM HOLNAP: {target_day.date()}"
            msg = f"Holnap {len(cheap_hours)} órán át lesz 50 EUR/MWh alatt az ár!\nMinimum: {min_price:.4f} €/kWh"
            
            body = f"Időpontok ({target_day.date()}):\n\n"
            for t, p in cheap_hours.items():
                body += f"{t.strftime('%H:%M')} -> {p/1000:.4f} €/kWh\n"
            
            send_pushover(subject, msg)
            send_email(subject, body)
        else:
            print("Holnap nincs az értesítési limit alatti ár.")
            
    except Exception as e:
        if "NoMatchingDataError" in str(type(e)):
            print(f"ℹ️ Az ENTSO-E-n még nem elérhetőek a holnapi ({target_day.date()}) árak.")
        else:
            traceback.print_exc()

if __name__ == "__main__":
    check_prices()
