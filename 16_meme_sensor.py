"""
    失效
"""
import requests
import pandas as pd
import time

BASE_URL = "https://fapi.bitunix.com"

# ----------------------------------------------
# API
# ----------------------------------------------

def get_all_symbols():
    res = requests.get(f"{BASE_URL}/api/v1/futures/market/tickers", timeout=10)
    data = res.json().get("data", [])
    return [s["symbol"] for s in data if s["symbol"].endswith("USDT")]

def get_klines(symbol, interval, limit=150):
    try:
        res = requests.get(
            f"{BASE_URL}/api/v1/futures/market/kline",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=10
        )
        data = res.json().get("data", [])
        if not data or len(data) < 130:
            return None
        df = pd.DataFrame(data)
        df["close"] = df["close"].astype(float)
        return df
    except Exception:
        return None

# ----------------------------------------------
# indicator
# ----------------------------------------------

def calc_indicators(df):
    c = df["close"]

    ema20  = c.ewm(span=20,  adjust=False).mean()
    ema60  = c.ewm(span=60,  adjust=False).mean()
    ema120 = c.ewm(span=120, adjust=False).mean()

    ema12  = c.ewm(span=12, adjust=False).mean()
    ema26  = c.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist   = macd - signal

    return {
        "ema20_now"  : ema20.iloc[-1],
        "ema60_now"  : ema60.iloc[-1],
        "ema120_now" : ema120.iloc[-1],
        "hist_now"   : hist.iloc[-1],
        "hist_prev"  : hist.iloc[-2],
    }

def check_conditions(ind):
    ma_aligned = ind["ema20_now"] > ind["ema60_now"] > ind["ema120_now"]
    macd_cross = ind["hist_prev"] < 0 and ind["hist_now"] > 0
    return ma_aligned and macd_cross

# ----------------------------------------------
# scanner
# ----------------------------------------------

def scan():
    print("取得所有交易對...")
    symbols = get_all_symbols()
    total = len(symbols)
    print(f"共 {total} 個 USDT 交易對，開始掃描...\n")

    results = []

    for i, symbol in enumerate(symbols, 1):
        matched_tf = []

        for tf in ["1h", "4h"]:
            df = get_klines(symbol, tf, limit=150)
            if df is None:
                continue
            ind = calc_indicators(df)
            if check_conditions(ind):
                matched_tf.append(tf)
            time.sleep(0.05)

        if matched_tf:
            results.append({"symbol": symbol, "timeframes": ", ".join(matched_tf)})
            print(f"  符合：{symbol:<15} [{', '.join(matched_tf)}]")
        elif i % 20 == 0:
            print(f"  進度：{i}/{total}")

    print("\n" + "=" * 45)
    print(f"掃描完成，共 {len(results)} 個符合條件")
    print("=" * 45)

    if results:
        print(f"\n{'Symbol':<18} 時間框架")
        print("-" * 35)
        for r in results:
            print(f"{r['symbol']:<18} {r['timeframes']}")

if __name__ == "__main__":
    scan()