import os
import smtplib
import requests
import traceback
import pandas as pd
from email.message import EmailMessage
from entsoe import EntsoePandasClient

# --- 1. BEÁLLÍTÁSOK ÉS TISZTÍTÁS ---
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

# --- 2. ÉRTESÍTÉSI FUNKCIÓK ---

def send_pushover(title, message):
    if not PO_USER or not PO_TOKEN: return
    url = "https://api.pushover.net/1/messages.json"
    data = {"token": PO_TOKEN, "user": PO_USER, "title": title, "message": message, "priority": 1}
    try: requests.post(url, data=data)
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
    except: print("E-mail hiba")

# --- 3. FŐ PROGRAM ---
def check_prices():
    print("--- INDÍTÁS (REGGELI AZNAPI ELLENŐRZÉS) ---")
    if not API_KEY: return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        now = pd.Timestamp.now(tz='Europe/Budapest')
        start = now.normalize() 
        end = start + pd.Timedelta(days=1)
        
        print(f"🔎 Vizsgált nap (MA): {start.date()}")

        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print("⚠️ Nincs adat.")
            return

        cheap_hours = prices[prices < PRICE_LIMIT]
        
        if not cheap_hours.empty:
            title = "🟢 MAI OLCSÓ ÁRAM!"
            msg = f"Ma ({start.date()}) {len(cheap_hours)} órán át lesz 0,05€ alatt az ár!"
            body = f"Időpontok:\n" + "\n".join([f"⚡ {t.strftime('%H:%M')} -> {p/1000:.4f} EUR/kWh" for t, p in cheap_hours.items()])
            send_pushover(title, msg)
            send_email(f"{title} {start.date()}", body)
        else:
            min_p = prices.min()
            min_t = prices.idxmin().strftime('%H:%M')
            title = "🔴 DRÁGA NAP (MA)"
            msg = f"Nincs 0,05€ alatti ár. Legolcsóbb: {min_t} ({min_p/1000:.4f} EUR/kWh)"
            send_pushover(title, msg)
            send_email(f"{title} {start.date()}", msg)
            
    except Exception as e:
        # Ha nincs adat a szerveren, ne omlon össze, csak jelezze
        if "NoMatchingDataError" in str(type(e)):
            print("ℹ️ Az ENTSO-E szerverén még nincsenek fent a mai adatok.")
        else:
            traceback.print_exc()

if __name__ == "__main__":
    check_prices()
