import requests
import time
import uuid
import hashlib
import json

API_KEY    = ""
SECRET_KEY = ""
BASE_URL   = "https://fapi.bitunix.com"

# -------------------------------------------------------
# basic_tools
# -------------------------------------------------------

def sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()

def request_private(method, path, query_params=None, body=None):
    nonce     = uuid.uuid4().hex
    timestamp = str(int(time.time() * 1000))
    query    = "".join(f"{k}{query_params[k]}" for k in sorted(query_params)) if query_params else ""
    body_str = json.dumps(body, separators=(",", ":"), sort_keys=True) if body else ""
    sign     = sha256(sha256(nonce + timestamp + API_KEY + query + body_str) + SECRET_KEY)
    headers  = {
        "api-key"     : API_KEY,
        "nonce"       : nonce,
        "timestamp"   : timestamp,
        "sign"        : sign,
        "Content-Type": "application/json"
    }
    url = BASE_URL + path
    if method == "GET":
        res = requests.get(url, headers=headers, params=query_params)
    else:
        res = requests.post(url, headers=headers, data=body_str)
    return res.json()

def request_public(path, params=None):
    res = requests.get(BASE_URL + path, params=params)
    return res.json()

# ----------------------------------------------
# statistics
# ----------------------------------------------

def get_klines(symbol, interval="1m", limit=100):
    """
    取得K線資料
    interval: 1m 5m 15m 30m 1h 2h 4h 1d
    """
    res = request_public("/api/v1/futures/market/kline", params={
        "symbol"  : symbol,
        "interval": interval,
        "limit"   : limit
    })
    return res.get("data", [])

# -------------------------------------------------------
# account/position
# -------------------------------------------------------

def get_account():
    return request_private("GET", "/api/v1/futures/account",
                           query_params={"marginCoin": "USDT"})

def get_positions(symbol):
    return request_private("GET", "/api/v1/futures/position/get_pending_positions",
                           query_params={"symbol": symbol})

def get_pending_orders(symbol):
    return request_private("GET", "/api/v1/futures/trade/get_pending_orders",
                           query_params={"symbol": symbol})

# -------------------------------------------------------
# order
# -------------------------------------------------------

def place_order(symbol, side, order_type, qty, price=None,
                trade_side="OPEN", effect="GTC",
                tp_price=None, sl_price=None, stop_type="MARK"):
    body = {
        "symbol"    : symbol,
        "side"      : side,
        "orderType" : order_type,
        "qty"       : str(qty),
        "tradeSide" : trade_side,
        "reduceOnly": False,
        "effect"    : effect,
    }
    if price:
        body["price"] = str(price)
    if tp_price:
        body["tpPrice"]     = str(tp_price)
        body["tpStopType"]  = stop_type
        body["tpOrderType"] = "MARKET"
    if sl_price:
        body["slPrice"]     = str(sl_price)
        body["slStopType"]  = stop_type
        body["slOrderType"] = "MARKET"
    return request_private("POST", "/api/v1/futures/trade/place_order", body=body)

def close_position(symbol, side, qty):
    """平倉：持多就賣，持空就買"""
    close_side = "SELL" if side == "BUY" else "BUY"
    return place_order(symbol, close_side, "MARKET", qty, trade_side="CLOSE")

def cancel_all_orders(symbol):
    return request_private("POST", "/api/v1/futures/trade/cancel_all_order",
                           body={"symbol": symbol})

# -------------------------------------------------------
# strategy_caculation
# -------------------------------------------------------

def calc_ma(closes, period):
    """簡單移動平均"""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period

def calc_ema(closes, period):
    """指數移動平均"""
    if len(closes) < period:
        return None
    k   = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return ema

def calc_macd(closes, fast=12, slow=26, signal=9):
    """
    MACD
    回傳 (macd_line, signal_line, histogram) 或 None
    """
    if len(closes) < slow + signal:
        return None, None, None
    ema_fast   = calc_ema(closes, fast)
    ema_slow   = calc_ema(closes, slow)
    macd_line  = ema_fast - ema_slow

    # 計算 signal line（MACD 的 EMA）
    macd_history = []
    for i in range(slow - 1, len(closes)):
        ef = calc_ema(closes[:i+1], fast)
        es = calc_ema(closes[:i+1], slow)
        if ef and es:
            macd_history.append(ef - es)
    if len(macd_history) < signal:
        return None, None, None
    signal_line = calc_ema(macd_history, signal)
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_volume_spike(volumes, period=20, multiplier=1.5):
    """
    成交量異常放大
    回傳 True 表示當前成交量 > 過去N根均量 * 倍數
    """
    if len(volumes) < period + 1:
        return False
    avg_vol     = sum(volumes[-period-1:-1]) / period
    current_vol = volumes[-1]
    return current_vol > avg_vol * multiplier

# -------------------------------------------------------
# strategy_setting
# -------------------------------------------------------

SYMBOL      = "ETHUSDT"
INTERVAL    = "1m"
QTY         = "0.01"       # 每次下單數量
TP_PCT      = 0.015        # 止盈 1.5%
SL_PCT      = 0.008        # 止損 0.8%
MA_FAST     = 9            # 快線週期
MA_SLOW     = 21           # 慢線週期
VOL_PERIOD  = 20           # 成交量均量週期
VOL_MULT    = 1.5          # 成交量倍數門檻
LOOP_SEC    = 30           # 每次檢查間隔（秒）

# -------------------------------------------------------
# strategy_core
# -------------------------------------------------------

def check_signal(klines):
    """
    進場條件：
    做多 → 均線金叉 + MACD histogram 由負轉正 + 成交量放大
    做空 → 均線死叉 + MACD histogram 由正轉負 + 成交量放大
    回傳 "BUY" / "SELL" / None
    """
    if len(klines) < 40:
        return None

    closes  = [float(k["close"])   for k in klines]
    volumes = [float(k["baseVol"]) for k in klines]

    # 均線
    ma_fast_now  = calc_ma(closes, MA_FAST)
    ma_slow_now  = calc_ma(closes, MA_SLOW)
    ma_fast_prev = calc_ma(closes[:-1], MA_FAST)
    ma_slow_prev = calc_ma(closes[:-1], MA_SLOW)

    if None in [ma_fast_now, ma_slow_now, ma_fast_prev, ma_slow_prev]:
        return None

    golden_cross = ma_fast_prev <= ma_slow_prev and ma_fast_now > ma_slow_now
    death_cross  = ma_fast_prev >= ma_slow_prev and ma_fast_now < ma_slow_now

    # MACD
    _, _, hist_now  = calc_macd(closes)
    _, _, hist_prev = calc_macd(closes[:-1])

    if hist_now is None or hist_prev is None:
        return None

    macd_bullish = hist_prev < 0 and hist_now > 0   # 由負轉正
    macd_bearish = hist_prev > 0 and hist_now < 0   # 由正轉負

    # 成交量放大
    vol_spike = calc_volume_spike(volumes, VOL_PERIOD, VOL_MULT)

    # 合併訊號
    if golden_cross and macd_bullish and vol_spike:
        return "BUY"
    if death_cross and macd_bearish and vol_spike:
        return "SELL"
    return None

def get_current_position(symbol):
    """取得當前持倉（只取第一筆）"""
    res = get_positions(symbol)
    positions = res.get("data", [])
    if positions:
        return positions[0]
    return None

def run_strategy():
    print(f"strategy_on：{SYMBOL} {INTERVAL}")
    print(f"MA {MA_FAST}/{MA_SLOW}  MACD(12,26,9)  Vol×{VOL_MULT}")
    print(f"position_size：{QTY}  tp：{TP_PCT*100}%  sl：{SL_PCT*100}%")
    print("=" * 50)

    while True:
        try:
            klines   = get_klines(SYMBOL, INTERVAL, limit=100)
            position = get_current_position(SYMBOL)
            signal   = check_signal(klines)

            current_price = float(klines[-1]["close"]) if klines else None
            print(f"[{time.strftime('%H:%M:%S')}] price:{current_price}  position:{'Yes' if position else 'No'}  Signal:{signal or '—'}")

            # 有倉位 → 不開新倉
            if position:
                time.sleep(LOOP_SEC)
                continue

            # 無倉位 + 有訊號 → 開倉
            if signal and current_price:
                if signal == "BUY":
                    tp = round(current_price * (1 + TP_PCT), 2)
                    sl = round(current_price * (1 - SL_PCT), 2)
                else:
                    tp = round(current_price * (1 - TP_PCT), 2)
                    sl = round(current_price * (1 + SL_PCT), 2)

                print(f"  → 開倉 {signal}  tp:{tp}  sl:{sl}")
                result = place_order(
                    symbol     = SYMBOL,
                    side       = signal,
                    order_type = "MARKET",
                    qty        = QTY,
                    trade_side = "OPEN",
                    tp_price   = tp,
                    sl_price   = sl,
                )
                print(f"  → result: {result}")

        except Exception as e:
            print(f"error: {e}")

        time.sleep(LOOP_SEC)

# -------------------------------------------------------
# start
# -------------------------------------------------------

if __name__ == "__main__":
    run_strategy()
