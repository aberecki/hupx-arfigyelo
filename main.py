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

# Határérték: 0.1 EUR/kWh (Ez alatt már nem éri meg eladni)
PRICE_LIMIT = 100.0 

def format_intervals(cheap_data):
    if cheap_data.empty: return ""
    intervals = []
    start_time = cheap_data.index[0]
    for i in range(1, len(cheap_data)):
        diff = cheap_data.index[i] - cheap_data.index[i-1]
        if diff > pd.Timedelta(minutes=15):
            end_time = cheap_data.index[i-1] + pd.Timedelta(minutes=15)
            intervals.append(f"• {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
            start_time = cheap_data.index[i]
    end_time = cheap_data.index[-1] + pd.Timedelta(minutes=15)
    intervals.append(f"• {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
    return "\n".join(intervals)

def send_alert(subject, body):
    # Pushover küldés
    if PO_USER and PO_TOKEN:
        try:
            requests.post("https://api.pushover.net/1/messages.json", data={
                "token": PO_TOKEN, "user": PO_USER, "title": subject, "message": body, "priority": 1
            })
        except: print("Pushover hiba")
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

def check_prices():
    print(f"--- INDÍTÁS: PROSUMER OPTIMALIZÁLÁS (Limit: {PRICE_LIMIT/1000} €/kWh) ---")
    if not API_KEY: return
    try:
        client = EntsoePandasClient(api_key=API_KEY)
        now = pd.Timestamp.now(tz='Europe/Budapest')
        target_day = (now + pd.Timedelta(days=1)).normalize()
        
        prices = client.query_day_ahead_prices('HU', start=target_day, end=target_day + pd.Timedelta(days=1))
        if prices.empty: return

        target_prices = prices[prices.index.normalize() == target_day]
        
        # JSON mentés
        data_list = [{"time": t.isoformat(), "price_kwh": round(p/1000, 4)} for t, p in target_prices.items()]
        with open('prices.json', 'w') as f:
            json.dump({"day": str(target_day.date()), "data": data_list}, f)

        # Alacsony ár figyelése (amikor nem éri meg eladni)
        cheap_intervals = target_prices[target_prices < PRICE_LIMIT]
        
        if not cheap_intervals.empty:
            time_list = format_intervals(cheap_intervals)
            min_price = target_prices.min() / 1000
            
            subject = f"⚠️ ALACSONY ÁTVÉTELI ÁR: {target_day.date()}"
            
            body = (
                f"Kedves Termelő!\n\n"
                f"Holnap napközben a piaci átvételi ár nagyon alacsony lesz ({min_price:.4f} €/kWh alá esik). "
                f"Ebben az időszakban nem kifizetődő a hálózatba táplálni!\n\n"
                f"📍 JAVASOLT ÖNFOGYASZTÁSI IDŐSZAKOK:\n{time_list}\n\n"
                f"🛠️ MIT TEGYÉL, HOGY NE VESZÍTS PÉNZT?\n"
                f"🚗 Most töltsd az elektromos autót a saját termelésedből!\n"
                f"🧺 Erre az időre időzítsd a nagyfogyasztókat (mosás, szárítás)!\n"
                f"🌡️ Most hűtsd/fűtsd le a lakást a klímával!\n"
                f"🔋 Ha van akkumulátorod, most töltsd fel, hogy az esti drága órákban legyen mihez nyúlni!\n\n"
                f"Grafikon: https://aberecki.github.io/hupx-arfigyelo/"
            )
            
            send_alert(subject, body)
            print("📧 Prosumer riasztás elküldve.")
            
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    check_prices()
