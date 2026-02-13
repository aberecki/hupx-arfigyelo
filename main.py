import os
import smtplib
import traceback
import pandas as pd
from email.message import EmailMessage
from entsoe import EntsoePandasClient

# --- 1. BEÁLLÍTÁSOK ÉS TITKOS KULCSOK ---
# Ezeket a GitHub Secrets-ből olvassa ki
API_KEY = os.environ.get('ENTSOE_KEY')
EMAIL_SENDER = os.environ.get('EMAIL_SENDER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
EMAIL_TARGET = os.environ.get('EMAIL_TARGET')

# --- 2. E-MAIL KÜLDŐ FÜGGVÉNY ---
def send_email(subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("❌ HIBA: Hiányzik az e-mail küldő címe vagy jelszava a Secrets-ből!")
        return

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_TARGET

    try:
        # Csatlakozás a Gmail szerverhez (SSL biztonságos kapcsolaton)
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ E-mail sikeresen elküldve ide: {EMAIL_TARGET}")
    except Exception as e:
        print(f"❌ Hiba az e-mail küldéskor: {e}")

# --- 3. FŐ PROGRAM (ÁRAK LEKÉRÉSE) ---
def check_prices():
    print("--- PROGRAM INDÍTÁSA ---")
    
    # Ellenőrizzük, hogy megvan-e az API kulcs
    if not API_KEY:
        print("❌ KRITIKUS HIBA: Nincs beállítva az ENTSOE_KEY a Secrets-ben!")
        return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        
        # Időzóna beállítása (Budapest)
        # A 'normalize' éjfélre állítja az órát
        now = pd.Timestamp.now(tz='Europe/Budapest')
        start = now.normalize() + pd.Timedelta(days=1)  # Holnap 00:00
        end = start + pd.Timedelta(days=1)              # Holnapután 00:00
        
        print(f"📅 Mai dátum (szerver szerint): {now}")
        print(f"🔎 Lekérdezés erre a napra (holnap): {start.date()}")
        print("⏳ Adatok lekérése az ENTSO-E szerverről...")

        # --- ITT TÖRTÉNIK A LEKÉRDEZÉS ---
        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        # Ha üres választ kapunk (de nem hibaüzenetet)
        if prices.empty:
            print("⚠️ FIGYELEM: A szerver válaszolt, de üres adatot küldött.")
            print("Ok lehet: Még nincsenek feltöltve a holnapi árak (próbáld később, pl. 13:00 után).")
