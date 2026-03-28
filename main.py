import yfinance as yf
import pandas_ta as ta
import requests
import os
import math
import time
import datetime
import pandas as pd
import mplfinance as mpf

# Mengambil Token & Chat ID dari GitHub Secrets
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_photo(photo_path, caption):
    """Fungsi mengirim gambar grafik beserta teks sinyal ke Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            payload = {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
            files = {"photo": photo}
            requests.post(url, data=payload, files=files)
    except Exception as e:
        print(f"Gagal kirim foto {photo_path}: {e}")

def send_telegram_text(message):
    """Fungsi mengirim pesan teks biasa ke Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def check_ihsg_health():
    """Mengecek apakah IHSG sedang Uptrend atau Downtrend (Filter Risiko)"""
    try:
        ihsg = yf.Ticker("^JKSE").history(period="3mo")
        ihsg.ta.ema(length=20, append=True)
        ihsg.ta.ema(length=50, append=True)
        last = ihsg.iloc[-1]
        # Pasar sehat jika Tren Jangka Pendek (EMA20) di atas Tren Jangka Menengah (EMA50)
        return last['EMA_20'] > last['EMA_50']
    except:
        return True # Jika Yahoo error ambil data IHSG, asumsikan sehat agar bot tetap jalan

def create_chart(df, ticker):
    """Membuat dan menyimpan gambar chart saham candlestick"""
    # Ambil 60 hari terakhir untuk digambar
    df_chart = df.tail(60).copy()
    
    # Tambahkan garis EMA 20 (Biru) dan EMA 50 (Oranye)
    ap = [
        mpf.make_addplot(df_chart['EMA_20'], color='blue', width=1.5),
        mpf.make_addplot(df_chart['EMA_50'], color='orange', width=1.5)
    ]
    
    filename = f"{ticker}_chart.png"
    
    # Render gambar chart
    mpf.plot(
        df_chart, 
        type='candle', 
        addplot=ap, 
        volume=True, 
        style='yahoo', 
        title=f"\n{ticker} - Analisis Teknikal",
        savefig=filename
    )
    return filename

def detect_candlestick_pattern(df):
    """Mendeteksi 4 Pola Candlestick Reversal Akurasi Tinggi pada 2 hari terakhir"""
    # Ambil data 2 hari terakhir
    curr = df.iloc[-1]  # Hari ini
    prev = df.iloc[-2]  # Kemarin

    # Ukuran Candle Hari Ini
    c_O, c_H, c_L, c_C = curr['Open'], curr['High'], curr['Low'], curr['Close']
    c_body = abs(c_C - c_O)
    c_upper_wick = c_H - max(c_O, c_C)
    c_lower_wick = min(c_O, c_C) - c_L
    c_is_green = c_C > c_O
    c_is_red = c_C < c_O

    # Ukuran Candle Kemarin
    p_O, p_H, p_L, p_C = prev['Open'], prev['High'], prev['Low'], prev['Close']
    p_is_red = p_C < p_O
    p_is_green = p_C > p_O

    pola = []

    # 1. Bullish Engulfing (Hijau menelan Merah)
    if p_is_red and c_is_green and c_C > p_O and c_O < p_C:
        pola.append("Bullish Engulfing 🚀")

    # 2. Bearish Engulfing (Merah menelan Hijau)
    if p_is_green and c_is_red and c_C < p_O and c_O > p_C:
        pola.append("Bearish Engulfing 🩸")

    # 3. Hammer / Bullish Pin Bar (Penolakan Harga Bawah)
    # Syarat: Ekor bawah 2x lebih panjang dari body, ekor atas sangat pendek
    if c_lower_wick > (2 * c_body) and c_upper_wick < (0.5 * c_body):
        pola.append("Hammer (Rejeksi Bawah) 🔨")

    # 4. Shooting Star / Bearish Pin Bar (Penolakan Harga Atas)
    # Syarat: Ekor atas 2x lebih panjang dari body, ekor bawah sangat pendek
    if c_upper_wick > (2 * c_body) and c_lower_wick < (0.5 * c_body):
        pola.append("Shooting Star (Rejeksi Atas) 🌠")

    if not pola:
        return "Normal / Netral 🕯️"
    
    return " & ".join(pola)


def analyze_stock_pro(ticker, is_market_healthy):
    """Otak algoritma pencari sinyal Buy/Sell + Candlestick"""
    df = yf.Ticker(ticker).history(period="6mo")
    if df.empty or len(df) < 50: return None

    # Kalkulasi Indikator Technical Analysis
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.ema(length=20, append=True)
    df.ta.ema(length=50, append=True)
    df.ta.atr(length=14, append=True)
    
    # --- DETEKSI POLA CANDLESTICK ---
    candlestick_pattern = detect_candlestick_pattern(df)
    
    last = df.iloc[-1]
    
    price = last['Close']
    rsi = last['RSI_14']
    macd = last['MACD_12_26_9']
    macd_signal = last['MACDs_12_26_9']
    ema20 = last['EMA_20']
    ema50 = last['EMA_50']
    atr = last['ATRr_14']

    is_uptrend = ema20 > ema50
    is_momentum_up = macd > macd_signal
    
    signal_msg = None
    
    # --- LOGIKA BUY ---
    if is_uptrend and is_momentum_up and rsi < 65:
        if not is_market_healthy:
            return None 
            
        stop_loss = price - (1.5 * atr)
        take_profit = price + (3.0 * atr)
        days = math.ceil((take_profit - price) / atr)
        
        # Tambahkan teks Pola Candlestick ke pesan Telegram
        signal_msg = (f"🟢 *STRONG BUY* : {ticker}\n\n"
                      f"🏷 Harga: `{price:.2f}`\n"
                      f"🎯 TP: `{take_profit:.2f}`\n"
                      f"🛑 SL: `{stop_loss:.2f}`\n"
                      f"⏳ Waktu: `~{days} Hari Kerja`\n"
                      f"🕯️ *Pola Candle:* {candlestick_pattern}\n"
                      f"📈 *(Garis Biru EMA20 > Oranye EMA50)*")

    # --- LOGIKA SELL ---
    elif (ema20 < ema50) or rsi > 75:
        alasan = "Overbought (RSI > 75)" if rsi > 75 else "Patah Tren (EMA 20 < EMA 50)"
        signal_msg = (f"🔴 *SELL WARNING* : {ticker}\n\n"
                      f"🏷 Harga: `{price:.2f}`\n"
                      f"⚠️ Alasan: {alasan}\n"
                      f"🕯️ *Pola Candle:* {candlestick_pattern}\n"
                      f"💡 Segera amankan profit / cut loss.")
                      
    if signal_msg:
        try:
            chart_file = create_chart(df, ticker)
            return {"message": signal_msg, "chart": chart_file}
        except Exception as e:
            print(f"Gagal membuat chart untuk {ticker}: {e}")
            return None
        
    return None

    
    # --- LOGIKA BUY ---
    if is_uptrend and is_momentum_up and rsi < 65:
        if not is_market_healthy:
            return None # Batalkan BUY jika IHSG sedang Downtrend (Bahaya)
            
        stop_loss = price - (1.5 * atr)
        take_profit = price + (3.0 * atr)
        days = math.ceil((take_profit - price) / atr)
        
        signal_msg = (f"🟢 *STRONG BUY* : {ticker}\n\n"
                      f"🏷 Harga: `{price:.2f}`\n"
                      f"🎯 TP: `{take_profit:.2f}`\n"
                      f"🛑 SL: `{stop_loss:.2f}`\n"
                      f"⏳ Waktu: `~{days} Hari Kerja`\n"
                      f"📈 *(Garis Biru EMA20 > Oranye EMA50)*")

    # --- LOGIKA SELL ---
    elif (ema20 < ema50) or rsi > 75:
        alasan = "Overbought (RSI > 75)" if rsi > 75 else "Patah Tren (EMA 20 < EMA 50)"
        signal_msg = (f"🔴 *SELL WARNING* : {ticker}\n\n"
                      f"🏷 Harga: `{price:.2f}`\n"
                      f"⚠️ Alasan: {alasan}\n"
                      f"💡 Segera amankan profit / cut loss.")
                      
    # Jika sinyal terbentuk, buatkan chart-nya
    if signal_msg:
        try:
            chart_file = create_chart(df, ticker)
            return {"message": signal_msg, "chart": chart_file}
        except Exception as e:
            print(f"Gagal membuat chart untuk {ticker}: {e}")
            return None
        
    return None

if __name__ == "__main__":
    # 1. Deteksi Sesi (Pagi/Sore) berdasarkan Jam Server UTC
    now_utc = datetime.datetime.utcnow()
    hour_utc = now_utc.hour
    
    # Jika di bawah jam 05:00 UTC (12:00 WIB), berarti sesi pagi
    if hour_utc < 5:
        sesi_teks = "🌅 *SESI PEMBUKAAN (09:15 WIB)*"
    else:
        sesi_teks = "🌇 *SESI PENUTUPAN (16:30 WIB)*"

    # 2. Cek Kesehatan Pasar (IHSG)
    is_market_healthy = check_ihsg_health()
    status_pasar = "✅ *IHSG UPTREND (Aman untuk Buy)*" if is_market_healthy else "🚨 *IHSG DOWNTREND (Risiko Tinggi - Buy Dibatalkan)*"
    
    send_telegram_text(f"🤖 *Memulai Pemindaian Saham...*\n{sesi_teks}\nStatus Pasar: {status_pasar}")
    
    # 3. Daftar 45 Saham Paling Aktif (LQ45)
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
    
    signals_found = 0
    
    # 4. Mulai Scanning
    for s in stocks:
        try:
            result = analyze_stock_pro(s, is_market_healthy)
            if result:
                # Kirim foto grafik dan caption ke Telegram
                send_telegram_photo(result["chart"], result["message"])
                
                # Hapus file gambar setelah dikirim (Bersih-bersih server)
                if os.path.exists(result["chart"]):
                    os.remove(result["chart"])
                    
                signals_found += 1
                time.sleep(3) # Jeda 3 detik agar Telegram & Yahoo tidak nge-block IP
            else:
                time.sleep(1) # Jeda ringan jika tidak ada sinyal
        except Exception as e:
            print(f"Error pada saham {s}: {e}")
            continue
            
    # 5. Laporan Penutup
    if signals_found == 0:
        pesan_tutup = ("💤 *SCAN SELESAI*\n\nTidak ada saham yang memenuhi kriteria *Genius* di sesi ini.")
        send_telegram_text(pesan_tutup)
    else:
        send_telegram_text(f"✅ *SCAN SELESAI*\nBerhasil mengirim {signals_found} sinyal saham potensial.")
