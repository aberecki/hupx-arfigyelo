import os
import smtplib
import requests
import traceback
import pandas as pd
from email.message import EmailMessage
from entsoe import EntsoePandasClient

# --- 1. BEÁLLÍTÁSOK ÉS TISZTÍTÁS ---
def clean_secret(value):
    """Eltávolítja a láthatatlan karaktereket a másolt jelszavakból."""
    if not value: return ""
    return value.strip().replace('\xa0', '')

# Kulcsok beolvasása
API_KEY = clean_secret(os.environ.get('ENTSOE_KEY'))
EMAIL_SENDER = clean_secret(os.environ.get('EMAIL_SENDER'))
EMAIL_PASSWORD = clean_secret(os.environ.get('EMAIL_PASSWORD'))
EMAIL_TARGET = clean_secret(os.environ.get('EMAIL_TARGET'))
PO_USER = clean_secret(os.environ.get('PUSHOVER_USER_KEY'))
PO_TOKEN = clean_secret(os.environ.get('PUSHOVER_API_TOKEN'))

# ÁR LIMIT (EUR/MWh) - 0.05 EUR/kWh = 50 EUR/MWh
PRICE_LIMIT = 50.0 

# --- 2. ÉRTESÍTÉSI FUNKCIÓK ---

def send_pushover(title, message):
    """Azonnali push értesítés küldése a telefonra."""
    if not PO_USER or not PO_TOKEN:
        print("⚠️ Pushover kulcsok hiányoznak.")
        return
    
    url = "https://api.pushover.net/1/messages.json"
    data = {
        "token": PO_TOKEN,
        "user": PO_USER,
        "title": title,
        "message": message,
        "priority": 1
    }
    try:
        requests.post(url, data=data)
        print("📱 Pushover értesítés elküldve!")
    except Exception as e:
        print(f"❌ Pushover hiba: {e}")

def send_email(subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        return
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
        print(f"📧 E-mail elküldve: {subject}")
    except Exception as e:
        print(f"❌ E-mail hiba: {e}")

# --- 3. FŐ PROGRAM ---
def check_prices():
    print("--- INDÍTÁS (REGGELI AZNAPI ELLENŐRZÉS) ---")
    
    if not API_KEY:
        print("❌ KRITIKUS HIBA: Nincs API kulcs!")
        return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        
        # --- DÁTUM BEÁLLÍTÁSA ---
        # A reggel 6-os futtatáskor a MAI napot nézzük
        now = pd.Timestamp.now(tz='Europe/Budapest')
        start = now.normalize() 
        end = start + pd.Timedelta(days=1)
        
        print(f"🔎 Vizsgált nap (MA): {start.date()}")

        # Lekérdezés
        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print("⚠️ Nincs elérhető adat a mai napra.")
            return

        # --- ELEMZÉS ---
        cheap_hours = prices[prices < PRICE_LIMIT]
        
        # "A" ESET: VAN JÓ ÁR MA
        if not cheap_hours.empty:
            print(f"✅ TALÁLAT! {len(cheap_hours)} olcsó óra van ma.")
            
            title = "🟢 MAI OLCSÓ ÁRAM!"
            msg_brief = f"Ma ({start.date()}) {len(cheap_hours)} órán át lesz 0,05€ alatt az ár!"
            
            email_body = f"Szia!\n\nA mai napon ({start.date()}) az alábbi időpontokban érdemes fogyasztani:\n\n"
            email_body += "IDŐPONTOK:\n-------------------\n"
            for timestamp, price in cheap_hours.items():
                time_str = timestamp.strftime('%H:%M')
                email_body += f"⚡ {time_str} --> {price/1000:.4f} EUR/kWh ({price:.1f} €/MWh)\n"
            email_body += "-------------------\nÜdv, a Robotod"
            
            send_pushover(title, msg_brief)
            send_email(f"{title} {start.date()}", email_body)

        # "B" ESET: MA MINDEN DRÁGA
        else:
            print(f"info: Nincs ár a limit alatt ma.")
            
            title = "🔴 DRÁGA NAP (MA)"
            min_price = prices.min()
            min_time = prices.idxmin().strftime('%H:%M')
            
            msg_text = f"Ma ({start.date()}) nincs 0,05€ alatti ár.\n"
            msg_text += f"Legolcsóbb időszak: {min_time} ({min_price/1000:.4f} EUR/kWh)"
            
            send_pushover(title, msg_text)
            send_email(f"{title} {start.date()}", msg_text)
            
    except Exception as e:
        print(f"\n❌ HIBA TÖRTÉNT: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    check_prices()
