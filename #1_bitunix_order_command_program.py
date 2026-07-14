import requests
import time
import uuid
import hashlib
import json
import pandas as pd

API_KEY    = ""
SECRET_KEY = ""
BASE_URL   = "https://fapi.bitunix.com"

# --------------------------------------------------------
# private_api用函數
# --------------------------------------------------------

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

# --------------------------------------------------------
# market
# --------------------------------------------------------

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

# --------------------------------------------------------
# account / position / pending_orders
# --------------------------------------------------------

def get_account():
    return request_private("GET", "/api/v1/futures/account",
                           query_params={"marginCoin": "USDT"})

def get_positions(symbol):
    return request_private("GET", "/api/v1/futures/position/get_pending_positions",
                           query_params={"symbol": symbol})

def get_pending_orders(symbol):
    return request_private("GET", "/api/v1/futures/trade/get_pending_orders",
                           query_params={"symbol": symbol})

# --------------------------------------------------------
# 下單 / 平倉
# --------------------------------------------------------

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
    close_side = "SELL" if side == "BUY" else "BUY"
    return place_order(symbol, close_side, "MARKET", qty, trade_side="CLOSE")

def cancel_all_orders(symbol):
    return request_private("POST", "/api/v1/futures/trade/cancel_all_order",
                           body={"symbol": symbol})