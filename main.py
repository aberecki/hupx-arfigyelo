import os
import smtplib
import traceback
import pandas as pd
from email.message import EmailMessage
from entsoe import EntsoePandasClient

# --- 1. BEÁLLÍTÁSOK ÉS TISZTÍTÁS ---
def clean_secret(value):
    """Eltávolítja a láthatatlan karaktereket és szóközöket."""
    if not value:
        return ""
    # Eltünteti a sima szóközt és a speciális \xa0 (non-breaking space) karaktert is
    return value.strip().replace('\xa0', '')

# Beolvassuk és rögtön meg is tisztítjuk az adatokat
API_KEY = clean_secret(os.environ.get('ENTSOE_KEY'))
EMAIL_SENDER = clean_secret(os.environ.get('EMAIL_SENDER'))
EMAIL_PASSWORD = clean_secret(os.environ.get('EMAIL_PASSWORD'))
EMAIL_TARGET = clean_secret(os.environ.get('EMAIL_TARGET'))

# --- 2. E-MAIL KÜLDÉS ---
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
        # SMTP szerver kapcsolat
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        # Itt történik a bejelentkezés a tisztított adatokkal
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ E-mail sikeresen elküldve ide: {EMAIL_TARGET}")
    except Exception as e:
        print(f"❌ E-mail hiba: {e}")
        # Ha ASCII hiba van, kiírjuk pontosan mi okozza
        import sys
        print(f"Küldő hossza: {len(EMAIL_SENDER)}, Jelszó hossza: {len(EMAIL_PASSWORD)}")

# --- 3. FŐ PROGRAM ---
def check_prices():
    print("--- PROGRAM INDÍTÁSA ---")
    
    if not API_KEY:
        print("❌ KRITIKUS HIBA: Nincs API kulcs!")
        return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        
        # --- DÁTUM FIXÁLÁS 2025-RE (A teszt idejére) ---
        print("🔧 Dátum kényszerítése 2025-re...")
        now = pd.Timestamp.now(tz='Europe/Budapest').replace(year=2025, month=2, day=13)
        
        start = now.normalize() + pd.Timedelta(days=1) # Holnap
        end = start + pd.Timedelta(days=1)
        
        print(f"📅 Keresett nap: {start.date()}")
        print("⏳ Adatok letöltése...")

        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print("⚠️ Üres válasz érkezett.")
            return

        # TESZT LIMIT (hogy biztosan találjon valamit)
        TEST_LIMIT = 1000 
        negativ_orak = prices[prices < TEST_LIMIT]
        
        if not negativ_orak.empty:
            print(f"✅ TALÁLAT! E-mail küldése folyamatban...")
            
            subject = f"✅ MŰKÖDIK: Árfigyelő Teszt {start.date()}"
            body = f"Szia!\n\nSikerült! A rendszer működik.\n"
            body += f"A lekérdezett nap: {start.date()}\n\n"
            body += "Íme az első pár ár:\n"
            
            for idopont, ar in negativ_orak.head(5).items():
                ora = idopont.strftime('%H:%M')
                body += f"⏰ {ora} --> {ar:.2f} EUR\n"
            
            body += "\nÜdv,\nA Robotod"
            
            send_email(subject, body)
        else:
            print("Nincs találat.")
            
    except Exception as e:
        print(f"\n❌ HIBA: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    check_prices()
