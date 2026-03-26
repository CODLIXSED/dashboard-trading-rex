import yfinance as yf
import pandas_ta as ta
import requests
import os
import math
import time

# Mengambil Token & Chat ID dari GitHub Secrets
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def analyze_stock_genius(ticker):
    # Ambil data 6 bulan terakhir untuk akurasi Moving Average
    df = yf.download(ticker, period="6mo", interval="1d", progress=False)
    if df.empty or len(df) < 50: return None

    # Kalkulasi Indikator Technical Analysis (TA)
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.ema(length=20, append=True) # Tren Jangka Pendek
    df.ta.ema(length=50, append=True) # Tren Jangka Menengah
    df.ta.atr(length=14, append=True) # Volatilitas Harian
    
    last = df.iloc[-1]
    
    price = last['Close']
    rsi = last['RSI_14']
    macd = last['MACD_12_26_9']
    macd_signal = last['MACDs_12_26_9']
    ema20 = last['EMA_20']
    ema50 = last['EMA_50']
    atr = last['ATRr_14']

    # Logika Cerdas untuk BUY
    is_uptrend = ema20 > ema50
    is_momentum_up = macd > macd_signal
    
    if is_uptrend and is_momentum_up and rsi < 65:
        # Risk:Reward = 1:2 berdasarkan volatilitas (ATR)
        stop_loss = price - (1.5 * atr)
        take_profit = price + (3.0 * atr)
        days_to_target = math.ceil((take_profit - price) / atr)
        
        return (f"🟢 *STRONG BUY* : {ticker}\n"
                f"🏷 Harga: `{price:.2f}`\n"
                f"🎯 Target Profit (TP): `{take_profit:.2f}`\n"
                f"🛑 Stop Loss (SL): `{stop_loss:.2f}`\n"
                f"⏳ Estimasi: `~{days_to_target} Hari Kerja`\n"
                f"📊 *Alasan:* Tren naik & Momentum Positif.")

    # Logika Cerdas untuk SELL / Amankan Profit
    elif (ema20 < ema50) or rsi > 75:
        alasan = "Overbought (RSI > 75)" if rsi > 75 else "Patah Tren (EMA20 < EMA50)"
        return (f"🔴 *SELL WARNING* : {ticker}\n"
                f"🏷 Harga: `{price:.2f}`\n"
                f"⚠️ *Alasan:* {alasan}.\n"
                f"💡 *Aksi:* Segera amankan profit/cut loss.")
    
    return None

if __name__ == "__main__":
    # Daftar 45 Saham Paling Aktif di Indonesia (LQ45)
    stocks = [
        "ACES.JK", "ADRO.JK", "AKRA.JK", "AMMN.JK", "AMRT.JK", "ANTM.JK", 
        "ARTO.JK", "ASII.JK", "BBCA.JK", "BBNI.JK", "BBRI.JK", "BBTN.JK", 
        "BMRI.JK", "BRIS.JK", "BRPT.JK", "BUKA.JK", "CPIN.JK", "ESSA.JK", 
        "EXCL.JK", "GGRM.JK", "GOTO.JK", "HRUM.JK", "ICBP.JK", "INCO.JK", 
        "INDF.JK", "INKP.JK", "INTP.JK", "ITMG.JK", "KLBF.JK", "MDKA.JK", 
        "MEDC.JK", "MTEL.JK", "PGAS.JK", "PGEO.JK", "PTBA.JK", "PTMP.JK", 
        "SIDO.JK", "SMGR.JK", "SRTG.JK", "TLKM.JK", "TOWR.JK", "TPIA.JK", 
        "UNTR.JK", "UNVR.JK", "WIFI.JK"
    ]
    
    results = []
    
    for s in stocks:
        try:
            signal = analyze_stock_genius(s)
            if signal:
                results.append(signal)
            time.sleep(1) # JEDA 1 DETIK agar tidak diblokir Yahoo Finance!
        except Exception as e:
            print(f"Error pada {s}: {e}")
            continue
    
    # Pengiriman Pesan ke Telegram
    if results:
        chunk_size = 5 # Kirim max 5 sinyal per pesan agar Telegram tidak menolak
        for i in range(0, len(results), chunk_size):
            chunk = results[i:i + chunk_size]
            message = "🧠 *DASHBOARD SAHAM GENIUS*\n\n" + "\n\n".join(chunk)
            send_telegram(message)
    else:
        send_telegram("💤 *DASHBOARD SAHAM GENIUS*\n\nHari ini tidak ada sinyal. Pasar sedang sideways/konsolidasi.")
