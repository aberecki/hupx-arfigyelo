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

# Környezeti változók beolvasása (GitHub Secrets)
API_KEY = clean_secret(os.environ.get('ENTSOE_KEY'))
EMAIL_SENDER = clean_secret(os.environ.get('EMAIL_SENDER'))
EMAIL_PASSWORD = clean_secret(os.environ.get('EMAIL_PASSWORD'))
EMAIL_TARGET = clean_secret(os.environ.get('EMAIL_TARGET'))
PO_USER = clean_secret(os.environ.get('PUSHOVER_USER_KEY'))
PO_TOKEN = clean_secret(os.environ.get('PUSHOVER_API_TOKEN'))

# Árlimit: Csak akkor küld értesítést, ha ez alatt van az ár (EUR/MWh)
# 50 EUR = kb. 20 Ft/kWh (rendszerhasználati díj nélkül)
PRICE_LIMIT = 50.0 

# --- 2. JSON MENTÉS (WEBOLDALHOZ) ---
def save_to_json(prices, start_date):
    """Lementi az adatokat a prices.json fájlba, amit a PWA olvas fel."""
    try:
        data_list = []
        for timestamp, price in prices.items():
            data_list.append({
                "time": timestamp.isoformat(), 
                "price_eur": round(price, 2),  
                "price_kwh": round(price / 1000, 4) 
            })
            
        with open('prices.json', 'w', encoding='utf-8') as f:
            json.dump({
                "updated": pd.Timestamp.now().isoformat(),
                "day": str(start_date),
                "data": data_list
            }, f, indent=4)
        print(f"✅ prices.json sikeresen frissítve ({start_date}) adatokkal.")
    except Exception as e:
        print(f"❌ JSON mentési hiba: {e}")

# --- 3. ÉRTESÍTÉSEK ---
def send_pushover(title, message):
    if not PO_USER or not PO_TOKEN: return
    try:
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": PO_TOKEN, "user": PO_USER, "title": title, "message": message, "priority": 1
        })
        print("📱 Pushover elküldve.")
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
        print("📧 E-mail elküldve.")
    except: print("E-mail hiba")

# --- 4. FŐ PROGRAM ---
def check_prices():
    print("--- INDÍTÁS (ÉLES ÜZEMMÓD - REAL TIME) ---")
    if not API_KEY: 
        print("Hiba: Nincs API kulcs beállítva.")
        return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        
        # --- IDŐZÍTÉS: MAI NAP + HOLNAP ---
        # Lekérjük a "most"-tól kezdődő 48 órát, hogy biztosan benne legyen a holnap is
        now = pd.Timestamp.now(tz='Europe/Budapest')
        start = now.normalize()
        end = start + pd.Timedelta(days=2) # Biztonsági ráhagyás a holnapra
        
        print(f"🔎 Lekérdezés indítása: {start.date()} -> {end.date()}")
        
        # Adatok lekérése az ENTSO-E-ről
        prices = client.query_day_ahead_prices('HU', start=start, end=end)
        
        if prices.empty:
            print("⚠️ Nincs adat az ENTSO-E rendszerében (lehet, hogy még nem töltötték fel).")
            return

        # --- A LEGFRISSEBB NAP KIVÁLASZTÁSA ---
        # Megnézzük, mi a legutolsó elérhető dátum az adatokban (ma vagy holnap)
        last_available_time = prices.index[-1]
        target_day = last_available_time.normalize()
        
        print(f"📅 Legfrissebb elérhető adat erre a napra: {target_day.date()}")
        
        # Leszűrjük csak erre az EGY napra (hogy a grafikon szép legyen, 00:00-23:00)
        day_prices = prices[prices.index.normalize() == target_day]

        # 1. Mentés a weboldalnak
        save_to_json(day_prices, target_day.date())

        # 2. Elemzés és Értesítés
        cheap_hours = day_prices[day_prices < PRICE_LIMIT]
        
        if not cheap_hours.empty:
            min_price = day_prices.min() / 1000 
            title = f"⚡ Olcsó áram: {target_day.date()}"
            msg = f"{len(cheap_hours)} órán át olcsó!\nMinimum: {min_price:.4f} €/kWh"
            
            body = f"Időpontok ({target_day.date()}):\n\n"
            for t, p in cheap_hours.items():
                body += f"{t.strftime('%H:%M')} -> {p/1000:.4f} €/kWh\n"
            
            # Csak akkor küldünk értesítést, ha ez a nap "friss" (ma vagy jövőbeli)
            # Ne küldjön, ha valamiért régi adatot talált
            if target_day.date() >= now.date():
                send_pushover(title, msg)
                send_email(f"Áram Árak: {target_day.date()}", body)
        else:
            print("Nincs kiugróan olcsó áram (< 50 EUR/MWh), de az adatokat frissítettem.")
            
    except Exception as e:
        if "NoMatchingDataError" in str(type(e)):
            print("ℹ️ Még nincs feltöltve a friss adat az ENTSO-E-re (próbáld később, kb. 14:00 után).")
        else:
            traceback.print_exc()

if __name__ == "__main__":
    check_prices()
