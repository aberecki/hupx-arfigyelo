import os
import smtplib
import traceback
import pandas as pd
from email.message import EmailMessage
from entsoe import EntsoePandasClient

# --- 1. BEÁLLÍTÁSOK ---
def clean_secret(value):
    """Eltávolítja a láthatatlan karaktereket a másolt jelszavakból."""
    if not value: return ""
    return value.strip().replace('\xa0', '')

API_KEY = clean_secret(os.environ.get('ENTSOE_KEY'))
EMAIL_SENDER = clean_secret(os.environ.get('EMAIL_SENDER'))
EMAIL_PASSWORD = clean_secret(os.environ.get('EMAIL_PASSWORD'))
EMAIL_TARGET = clean_secret(os.environ.get('EMAIL_TARGET'))

# ÁR LIMIT (EUR/MWh) - 0.05 EUR/kWh = 50 EUR/MWh
PRICE_LIMIT = 50.0 

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
        # Élesben a mostani időt használjuk
        now = pd.Timestamp.now(tz='Europe/Budapest')
        
        start = now.normalize() + pd.Timedelta(days=1) # Holnap 00:00
        end = start + pd.Timedelta(days=1)             # Holnapután 00:00
        
        print(f"🔎 Vizsgált nap: {start.date()}")

        # Lekérdezés
        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print("⚠️ A szerver válaszolt, de üres adatot küldött.")
            return

        # --- ELEMZÉS ---
        cheap_hours = prices[prices < PRICE_LIMIT]
        
        # "A" ESET: VAN JÓ ÁR
        if not cheap_hours.empty:
            print(f"✅ TALÁLAT! {len(cheap_hours)} óra van {PRICE_LIMIT} EUR alatt.")
            
            subject = f"🟢 OLCSÓ ÁRAM: {start.date()} (0,05€ alatt!)"
            body = f"Szia!\n\nHolnap ({start.date()}) lesznek időszakok, amikor az ár 0,05 EUR/kWh (50 EUR/MWh) alá esik.\n\n"
            body += "IDŐPONTOK:\n-------------------\n"
            
            for timestamp, price in cheap_hours.items():
                time_str = timestamp.strftime('%H:%M')
                kwh_price = price / 1000 
                body += f"⚡ {time_str} --> {kwh_price:.4f} EUR/kWh ({price:.1f} €/MWh)\n"
            
            body += "-------------------\nÉrdemes tölteni!"
            send_email(subject, body)

        # "B" ESET: MINDEN DRÁGA
        else:
            print(f"info: Nincs ár a limit ({PRICE_LIMIT} EUR) alatt.")
            
            subject = f"🔴 DRÁGA NAP: {start.date()} (Nincs 0,05€ alatt)"
            body = f"Szia!\n\nA holnapi napon ({start.date()}) sajnos nem lesz 0,05 EUR/kWh alatti áram.\n\n"
            
            min_price = prices.min()
            min_price_kwh = min_price / 1000
            min_time = prices.idxmin().strftime('%H:%M')
            
            body += f"A legolcsóbb időszak ez lesz:\n"
            body += f"🕒 {min_time} --> {min_price_kwh:.4f} EUR/kWh ({min_price:.1f} €/MWh)\n"
            
            send_email(subject, body)
            
    except Exception as e:
        print(f"\n❌ HIBA TÖRTÉNT: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    check_prices()
