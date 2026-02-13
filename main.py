import os
import smtplib
import traceback
import pandas as pd
from email.message import EmailMessage
from entsoe import EntsoePandasClient

# --- 1. BEÁLLÍTÁSOK ÉS TITKOS KULCSOK ---
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
    
    if not API_KEY:
        print("❌ KRITIKUS HIBA: Nincs beállítva az ENTSOE_KEY a Secrets-ben!")
        return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        
        # Időzóna beállítása (Budapest)
        now = pd.Timestamp.now(tz='Europe/Budapest')
        start = now.normalize() + pd.Timedelta(days=1)  # Holnap 00:00
        end = start + pd.Timedelta(days=1)              # Holnapután 00:00
        
        print(f"📅 Mai dátum (szerver szerint): {now}")
        print(f"🔎 Lekérdezés erre a napra (holnap): {start.date()}")
        print("⏳ Adatok lekérése az ENTSO-E szerverről...")

        # --- ITT TÖRTÉNIK A LEKÉRDEZÉS ---
        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print("⚠️ FIGYELEM: A szerver válaszolt, de üres adatot küldött.")
            print("Ok lehet: Még nincsenek feltöltve a holnapi árak.")
            return

        # --- ADATOK ELEMZÉSE ---
        negativ_orak = prices[prices <= 0]
        
        if not negativ_orak.empty:
            print(f"📉 TALÁLAT! {len(negativ_orak)} órában lesz negatív/ingyen áram.")
            
            subject = f"⚠️ INGYEN ÁRAM: {start.date()} (Holnap!)"
            body = f"Szia!\n\nA tőzsdei adatok alapján holnap ({start.date()}) negatív vagy 0 eurós áramár várható!\n\n"
            body += "🕒 ÉRINTETT IDŐSZAKOK:\n"
            body += "---------------------------------\n"
            
            for idopont, ar in negativ_orak.items():
                ora = idopont.strftime('%H:%M')
                body += f"⚡ {ora} --> {ar:.2f} EUR/MWh\n"
            
            body += "---------------------------------\n"
            body += "Javaslat: Töltsd az autót vagy indítsd a nagy fogyasztókat!\n\n"
            body += "Üdv,\nA Te Árfigyelő Robotod 🤖"
            
            send_email(subject, body)
        else:
            print(f"👍 Siker! Lekértem az adatokat {start.date()}-ra.")
            print(f"Minimális ár: {prices.min():.2f} EUR/MWh")
            print("Nincs negatív ár holnapra, így nem küldök e-mailt.")
            
    except Exception as e:
        print("\n❌ ------------------------------------------------")
        print("HIBA TÖRTÉNT A PROGRAM FUTÁSA KÖZBEN!")
        print(f"Hiba típusa: {type(e).__name__}")
        print(f"Hiba üzenet: {str(e)}")
        print("\nRészletes Traceback:")
        traceback.print_exc()
        print("--------------------------------------------------")

if __name__ == "__main__":
    check_prices()
