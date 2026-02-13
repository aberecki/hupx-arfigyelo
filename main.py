import os
import smtplib
import pandas as pd
from email.message import EmailMessage
from entsoe import EntsoePandasClient

# --- 1. TITKOS ADATOK BEOLVASÁSA ---
API_KEY = os.environ['ENTSOE_KEY']
EMAIL_SENDER = os.environ['EMAIL_SENDER']
EMAIL_PASSWORD = os.environ['EMAIL_PASSWORD']
EMAIL_TARGET = os.environ['EMAIL_TARGET']

def send_email(subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_TARGET

    try:
        # Csatlakozás a Gmail szerverhez
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ E-mail sikeresen elküldve!")
    except Exception as e:
        print(f"❌ Hiba az e-mail küldéskor: {e}")

def check_prices():
    # Csatlakozás az ENTSO-E adatbázishoz
    client = EntsoePandasClient(api_key=API_KEY)

    # Időzóna beállítása (Budapest)
    start = pd.Timestamp.now(tz='Europe/Budapest').normalize() + pd.Timedelta(days=1)
    end = start + pd.Timedelta(days=1)

    print(f"🔎 Árak lekérdezése erre a napra: {start.date()}")

    try:
        # Magyar (HU) árak lekérése holnapra
        prices = client.query_day_ahead_prices('HU', start=start, end=end)

        # Keressük a 0 vagy negatív árakat
        negativ_orak = prices[prices <= 0]

        if not negativ_orak.empty:
            print("📉 Negatív árakat találtam! E-mail küldése...")

            # E-mail összeállítása
            subject = f"⚠️ INGYEN ÁRAM: {start.date()} (Holnap!)"

            body = f"Szia!\n\nA tőzsdei adatok alapján holnap ({start.date()}) 0 vagy negatív áramár várható!\n\n"
            body += "🕒 IDŐSZAKOK ÉS ÁRAK:\n"
            body += "---------------------------------\n"

            for idopont, ar in negativ_orak.items():
                ora = idopont.strftime('%H:%M')
                body += f"⚡ {ora} --> {ar:.2f} EUR/MWh\n"

            body += "---------------------------------\n"
            body += "TIPP: Töltsd az autót vagy indítsd a mosógépet ezekben az órákban!\n\n"
            body += "Üdv,\nA Te Árfigyelő Robotod 🤖"

            send_email(subject, body)
        else:
            print("👍 Nincs negatív ár holnapra. Nem küldök levelet.")

    except Exception as e:
        print(f"❌ Hiba történt a lekérdezésben: {e}")

if __name__ == "__main__":
    check_prices()
