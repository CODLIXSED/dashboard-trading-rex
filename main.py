import yfinance as yf
import pandas_ta as ta
import requests
import os
import math

# Konfigurasi dari Secrets GitHub
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def analyze_stock_genius(ticker):
    # Ambil data lebih panjang untuk MA50
    df = yf.download(ticker, period="6mo", interval="1d", progress=False)
    if df.empty or len(df) < 50: return None

    # Kalkulasi Indikator Genius dengan Pandas TA
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.ema(length=20, append=True) # Tren Jangka Pendek
    df.ta.ema(length=50, append=True) # Tren Jangka Menengah
    df.ta.atr(length=14, append=True) # Volatilitas untuk TP/SL
    
    # Ambil data hari terakhir
    last = df.iloc[-1]
    
    price = last['Close']
    rsi = last['RSI_14']
    macd = last['MACD_12_26_9']
    macd_signal = last['MACDs_12_26_9']
    ema20 = last['EMA_20']
    ema50 = last['EMA_50']
    atr = last['ATRr_14']

    # --- LOGIKA BUY GENIUS ---
    # Syarat: Sedang Uptrend (EMA20 > EMA50) + Momentum naik (MACD > Signal) + Belum Overbought (RSI < 65)
    is_uptrend = ema20 > ema50
    is_momentum_up = macd > macd_signal
    
    if is_uptrend and is_momentum_up and rsi < 65:
        # Kalkulasi Risk/Reward Ratio 1:2
        stop_loss = price - (1.5 * atr)
        take_profit = price + (3.0 * atr)
        
        # Estimasi waktu profit (Asumsi harga bergerak sebesar 1 ATR per hari)
        days_to_target = math.ceil((take_profit - price) / atr)
        
        return (f"🟢 *STRONG BUY* : {ticker}\n"
                f"🏷 Harga: `{price:.2f}`\n"
                f"🎯 Target Profit (TP): `{take_profit:.2f}`\n"
                f"🛑 Stop Loss (SL): `{stop_loss:.2f}`\n"
                f"⏳ Estimasi Waktu: `~{days_to_target} Hari Kerja`\n"
                f"📊 *Alasan:* Tren naik (Golden Cross) & Momentum MACD Positif.")

    # --- LOGIKA SELL GENIUS ---
    # Syarat: Patah Tren (EMA20 < EMA50) atau Harga overbought parah (RSI > 75)
    elif (ema20 < ema50) or rsi > 75:
        return (f"🔴 *SELL WARNING* : {ticker}\n"
                f"🏷 Harga: `{price:.2f}`\n"
                f"⚠️ *Alasan:* " + ("Overbought (RSI Tinggi)" if rsi > 75 else "Patah Tren (Death Cross)") + ".\n"
                f"💡 *Aksi:* Segera amankan profit Anda.")
    
    return None

if __name__ == "__main__":
    # Daftar saham, disarankan gunakan saham bluechip bervolatilitas baik
    stocks = ["BBCA.JK", "BMRI.JK", "AMMN.JK", "AAPL", "NVDA"] 
    results = []
    
    for s in stocks:
        try:
            signal = analyze_stock_genius(s)
            if signal:
                results.append(signal)
        except Exception as e:
            continue # Abaikan error jika data saham gagal diunduh
    
    if results:
        message = "🧠 *DASHBOARD SAHAM GENIUS*\n\n" + "\n\n".join(results)
        send_telegram(message)
    else:
        # Opsional: Kirim pesan jika tidak ada sinyal hari ini
        send_telegram("💤 *DASHBOARD SAHAM GENIUS*\n\nHari ini tidak ada sinyal Buy/Sell yang memenuhi standar algoritma. Pasar sedang konsolidasi/sideways.")
