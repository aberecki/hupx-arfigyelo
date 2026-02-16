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

# Értesítési limit: 0.1 EUR/kWh (100 EUR/MWh)
PRICE_LIMIT = 100.0 

def format_intervals(cheap_data):
    """Összefüggő idősávok generálása a negyedórás adatokból"""
    if cheap_data.empty:
        return ""
    
    intervals = []
    start_time = cheap_data.index[0]
    
    for i in range(1, len(cheap_data)):
        # Megnézzük a különbséget az aktuális és az előző időpont között
        diff = cheap_data.index[i] - cheap_data.index[i-1]
        
        # Ha több mint 15 perc telt el, lezárjuk az előző sávot
        if diff > pd.Timedelta(minutes=15):
            end_time = cheap_data.index[i-1] + pd.Timedelta(minutes=15)
            intervals.append(f"• {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
            start_time = cheap_data.index[i]
            
    # Az utolsó sáv lezárása
    end_time = cheap_data.index[-1] + pd.Timedelta(minutes=15)
    intervals.append(f"• {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
    
    return "\n".join(intervals)

def send_alert(subject, body):
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
            print("📧 E-mail elküldve.")
        except: print("E-mail hiba")

    if PO_USER and PO_TOKEN:
        try:
            requests.post("https://api.pushover.net/1/messages.json", data={
                "token": PO_TOKEN, "user": PO_USER, "title": subject, "message": body, "priority": 1
            })
            print("📱 Pushover elküldve.")
        except: print("Pushover hiba")

def check_prices():
    print(f"--- INDÍTÁS: OKOS ÉRTESÍTÉSEK (Limit: {PRICE_LIMIT/1000} €/kWh) ---")
    if not API_KEY: return

    try:
        client = EntsoePandasClient(api_key=API_KEY)
        now = pd.Timestamp.now(tz='Europe/Budapest')
        target_day = (now + pd.Timedelta(days=1)).normalize()
        
        prices = client.query_day_ahead_prices('HU', start=target_day, end=target_day + pd.Timedelta(days=1))
        
        if prices.empty:
            print("Nincs adat holnapra.")
            return

        target_prices = prices[prices.index.normalize() == target_day]
        
        # JSON mentés a weboldalnak
        data_list = [{"time": t.isoformat(), "price_kwh": round(p/1000, 4)} for t, p in target_prices.items()]
        with open('prices.json', 'w') as f:
            json.dump({"day": str(target_day.date()), "data": data_list}, f)

        # Riasztási logika
        cheap_intervals = target_prices[target_prices < PRICE_LIMIT]
        
        if not cheap_intervals.empty:
            time_list = format_intervals(cheap_intervals)
            min_price = target_prices.min() / 1000
            
            subject = f"⚡ KEDVEZŐ ENERGIAÁRAK: {target_day.date()}"
            
            body = (
                f"Szia!\n\n"
                f"Holnap kedvező áron lesz elérhető az áram a tőzsdén. "
                f"A legalacsonyabb ár: {min_price:.4f} €/kWh.\n\n"
                f"📍 Alacsony tarifás időszakok:\n{time_list}\n\n"
                f"💡 OKOS TIPPEK ERRE AZ IDŐSZAKRA:\n"
                f"🚗 Töltsd fel az elektromos autódat!\n"
                f"🧺 Indítsd el a mosó- vagy mosogatógépet!\n"
                f"❄️ Időzítsd a klímát az előhűtésre/fűtésre!\n"
                f"🔋 Ha van otthoni akkumulátorod, most érdemes tölteni!\n\n"
                f"Részletes grafikon: https://aberecki.github.io/hupx-arfigyelo/"
            )
            
            send_alert(subject, body)
        else:
            print("Holnap nincs a limit alatti ár.")
            
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    check_prices()
