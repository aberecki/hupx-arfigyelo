import os
import smtplib
import traceback
import pandas as pd
from email.message import EmailMessage
from entsoe import EntsoePandasClient

# --- 1. BEÁLLÍTÁSOK ÉS ADATVÉDELEM ---
def clean_secret(value):
    """Eltávolítja a láthatatlan karaktereket a másolt jelszavakból."""
    if not value: return ""
    return value.strip().replace('\xa0', '')

# Titkos kulcsok beolvasása a GitHub Secrets-ből
API_KEY = clean_secret(os.environ.get('ENTSOE_KEY'))
EMAIL_SENDER = clean_secret(os.environ.get('EMAIL_SENDER'))
EMAIL_PASSWORD = clean_secret(os.environ.get('EMAIL_PASSWORD'))
EMAIL_TARGET = clean_secret(os.environ.get('EMAIL_TARGET'))

# ÁR LIMIT BEÁLLÍTÁSA
# 0.05 EUR/kWh = 50 EUR/MWh
# Ha ez alá megy az ár, "Jó áras" levelet kapsz.
PRICE_LIMIT = 50.0 

# --- 2. E-MAIL KÜLDŐ ROBOT ---
def send_email(subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("❌ HIBA: Hiányzik az e-mail jelszó vagy cím!")
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
        print(f"✅ E-mail sikeresen elküldve: {subject}")
    except Exception as e:
        print(f"❌ E-mail hiba: {e}")

# --- 3. FŐ PROGRAM ---
def check_prices():
    print("--- INDÍTÁS (ÉLES ÜZEMMÓD) ---")
    
    if not API_KEY:
        print("❌ KRITIKUS HIBA: Nincs API kulcs!")
        return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        
        # --- DÁTUM BEÁLLÍTÁSA ---
        # A rendszer a valós idejű "holnapi" napot nézi.
        now = pd.Timestamp.now(tz='Europe/Budapest')
        
        # Ha tesztelni akarod a múltat/jövőt, csak akkor vedd ki a kommentet az alábbi sor elől:
        # now = now.replace(year=2025, month=2, day=14) 
        
        start = now.normalize() + pd.Timedelta(days=1) # Holnap 00:00
        end = start + pd.Timedelta(days=1)             # Holnapután 00:00
        
        print(f"🔎 Vizsgált nap: {start.date()}")

        # Lekérdezés a HUPX szerverről
        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print("⚠️
