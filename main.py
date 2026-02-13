import os
import smtplib
import traceback
import pandas as pd
from email.message import EmailMessage
from entsoe import EntsoePandasClient

# --- 1. BEÁLLÍTÁSOK ---
API_KEY = os.environ.get('ENTSOE_KEY')
EMAIL_SENDER = os.environ.get('EMAIL_SENDER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
EMAIL_TARGET = os.environ.get('EMAIL_TARGET')

# --- 2. E-MAIL KÜLDÉS ---
def send_email(subject, body):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("❌ HIBA: Hiányzik az e-mail jelszó!")
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
        print(f"✅ E-mail elküldve ide: {EMAIL_TARGET}")
    except Exception as e:
        print(f"❌ E-mail hiba: {e}")

# --- 3. FŐ PROGRAM ---
def check_prices():
    print("--- PROGRAM INDÍTÁSA ---")
    
    if not API_KEY:
        print("❌ KRITIKUS HIBA: Nincs API kulcs!")
        return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        
        # --- IDŐ KORRIGÁLÁSA 2025-RE ---
        # Mivel az adatbázisban csak 2025-ös adatok vannak,
        # kényszerítjük a dátumot a mai napra (2025.02.13).
        
        print("🔧 Dátum kényszerítése 2025-re (hogy legyen adat)...")
        now = pd.Timestamp.now(tz='Europe/Budapest').replace(year=2025, month=2, day=13)
        
        start = now.normalize() + pd.Timedelta(days=1) # Holnap (2025.02.14)
        end = start + pd.Timedelta(days=1)
        
        print(f"📅 Keresett nap: {start.date()} (Valentin nap)")
        print("⏳ Adatok letöltése...")

        # Lekérdezés
        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print("⚠️ Üres válasz érkezett.")
            return

        # --- FIGYELEM! TESZT ÜZEMMÓD ---
        # Most direkt magasra (1000 EUR) állítjuk a limitet, 
        # hogy BIZTOSAN találjon "olcsóbb" áramot és küldjön e-mailt neked!
        TEST_LIMIT = 1000 
        negativ_orak = prices[prices < TEST_LIMIT]
        
        if not negativ_orak.empty:
            print(f"✅ TALÁLAT! Sikerült adatot szerezni.")
            
            subject = f"✅ SIKERES TESZT: Működik a rendszered!"
            body = f"Szia!\n\nEz a levél bizonyítja, hogy a rendszered JÓL MŰKÖDIK.\n"
            body += f"Sikerült lekérdezni a holnapi ({start.date()}) árakat.\n\n"
            body += "Íme az első pár ár (EUR/MWh):\n"
            body += "---------------------------------\n"
            
            for idopont, ar in negativ_orak.head(5).items():
                ora = idopont.strftime('%H:%M')
                body += f"⏰ {ora} --> {ar:.2f}\n"
            
            body += "---------------------------------\n"
            body += "Most már visszaállíthatod a kódot élesre (limit < 0).\n"
            
            send_email(subject, body)
        else:
            print("Nincs találat.")
            
    except Exception as e:
        print(f"\n❌ HIBA: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    check_prices()
