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
                "time": timestamp.isoformat(), # Pl: 2026-02-15T11:00:00+01:00
                "price_eur": round(price, 2),  # Ár EUR/MWh
                "price_kwh": round(price / 1000, 4) # Ár EUR/kWh
            })
            
        # JSON fájl írása
        with open('prices.json', 'w', encoding='utf-8') as f:
            json.dump({
                "updated": pd.Timestamp.now().isoformat(),
                "day": str(start_date),
                "data": data_list
            }, f, indent=4)
            
        print("✅ SIKER: prices.json fájl legenerálva!")
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
    print("--- INDÍTÁS (PWA JSON GENERÁTOR + ÉRTESÍTŐ) ---")
    if not API_KEY: return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        now = pd.Timestamp.now(tz='Europe/Budapest')
        start = now.normalize() 
        end = start + pd.Timedelta(days=1)
        
        print(f"🔎 Vizsgált nap: {start.date()}")

        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print("⚠️ Nincs adat.")
            return

        # 1. LÉPÉS: Mentsük el az adatokat a PWA-nak!
        save_to_json(prices, start.date())

        # 2. LÉPÉS: Elemzés és Értesítés (Régi logika)
        cheap_hours = prices[prices < PRICE_LIMIT]
        
        if not cheap_hours.empty:
            title = "🟢 MAI OLCSÓ ÁRAM!"
            msg = f"Ma ({start.date()}) {len(cheap_hours)} órán át lesz 0,05€ alatt!"
            body = f"Részletek:\n" + "\n".join([f"{t.strftime('%H:%M')} -> {p/1000:.4f} €/kWh" for t, p in cheap_hours.items()])
            send_pushover(title, msg)
            send_email(f"{title} {start.date()}", body)
        else:
            print("Nincs olcsó áram, de az adatokat frissítettem.")
            
    except Exception as e:
        if "NoMatchingDataError" in str(type(e)):
            print("ℹ️ Még nincs adat az ENTSO-E-n.")
        else:
            traceback.print_exc()

if __name__ == "__main__":
    check_prices()
