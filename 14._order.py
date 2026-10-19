import requests
import time
import uuid
import hashlib
import json

API_KEY    = "3c676ce499a61174f6dd03f0c9487f9e"
SECRET_KEY = "6d52ad24dfb94cd6e59267ce5165e5c3"
BASE_URL   = "https://fapi.bitunix.com"

# ── 基礎工具 ──────────────────────────────────────────

def sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()

def request_private(method, path, query_params=None, body=None):
    nonce     = uuid.uuid4().hex
    timestamp = str(int(time.time() * 1000))

    query    = "".join(f"{k}{query_params[k]}" for k in sorted(query_params)) if query_params else ""
    body_str = json.dumps(body, separators=(",", ":"), sort_keys=True) if body else ""

    sign = sha256(sha256(nonce + timestamp + API_KEY + query + body_str) + SECRET_KEY)

    headers = {
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

# ── 查詢類 ────────────────────────────────────────────

def get_account():
    """查帳戶餘額"""
    return request_private("GET", "/api/v1/futures/account",
                           query_params={"marginCoin": "USDT"})

def get_pending_orders(symbol):
    """查掛單"""
    return request_private("GET", "/api/v1/futures/trade/get_pending_orders",
                           query_params={"symbol": symbol})

def get_order_detail(order_id):
    """查單一訂單詳情"""
    return request_private("GET", "/api/v1/futures/trade/get_order_detail",
                           query_params={"orderId": order_id})

def get_positions(symbol):
    """查倉位"""
    return request_private("GET", "/api/v1/futures/position/get_pending_positions",
                           query_params={"symbol": symbol})

# ── 下單類 ────────────────────────────────────────────

def place_order(symbol, side, order_type, qty, price=None,
                trade_side="OPEN",
                reduce_only=False, effect="GTC", client_id=None,
                tp_price=None, tp_stop_type="MARK",
                sl_price=None, sl_stop_type="MARK"):
    """
    下單
    ─────────────────────────────────────────
    symbol      : 交易對，例如 "BTCUSDT"
    side        : "BUY" 或 "SELL"
    order_type  : "LIMIT"（限價）或 "MARKET"（市價）
    qty         : 數量，字串，例如 "0.001"
    price       : 限價單必填，市價單不填
    trade_side  : "OPEN"（開倉）或 "CLOSE"（平倉）← HEDGE模式必填
    reduce_only : True = 只減倉，不開新倉
    effect      : "GTC" / "IOC" / "FOK"
    client_id   : 自訂訂單ID，可不填
    tp_price    : 止盈觸發價
    tp_stop_type: "MARK"（標記價）或 "LAST"（最新價）
    sl_price    : 止損觸發價
    sl_stop_type: "MARK" 或 "LAST"
    """
    body = {
        "symbol"    : symbol,
        "side"      : side,
        "orderType" : order_type,
        "qty"       : str(qty),
        "tradeSide" : trade_side,   # HEDGE 模式必填
        "reduceOnly": reduce_only,
        "effect"    : effect,
    }
    if price:
        body["price"] = str(price)
    if client_id:
        body["clientId"] = client_id
    if tp_price:
        body["tpPrice"]     = str(tp_price)
        body["tpStopType"]  = tp_stop_type
        body["tpOrderType"] = "MARKET"
    if sl_price:
        body["slPrice"]     = str(sl_price)
        body["slStopType"]  = sl_stop_type
        body["slOrderType"] = "MARKET"

    return request_private("POST", "/api/v1/futures/trade/place_order", body=body)

def cancel_order(symbol, order_id):
    """取消單一訂單"""
    return request_private("POST", "/api/v1/futures/trade/cancel_order",
                           body={"symbol": symbol, "orderId": order_id})

def cancel_all_orders(symbol):
    """取消所有掛單"""
    return request_private("POST", "/api/v1/futures/trade/cancel_all_order",
                           body={"symbol": symbol})

def modify_order(symbol, order_id, price=None, qty=None):
    """改單（價格或數量）"""
    body = {"symbol": symbol, "orderId": order_id}
    if price:
        body["price"] = str(price)
    if qty:
        body["qty"] = str(qty)
    return request_private("POST", "/api/v1/futures/trade/modify_order", body=body)

def close_position(symbol, side, qty, order_type="MARKET"):
    """
    平倉
    ─────────────────────────────────────────
    side : 持倉方向（BUY倉就用SELL平，SELL倉就用BUY平）
    qty  : 平倉數量
    """
    close_side = "SELL" if side == "BUY" else "BUY"
    return place_order(
        symbol     = symbol,
        side       = close_side,
        order_type = order_type,
        qty        = qty,
        trade_side = "CLOSE"
    )

# ── 測試 ──────────────────────────────────────────────

if __name__ == "__main__":

    print("=== 帳戶餘額 ===")
    print(get_account())

    print("\n=== BTC 掛單 ===")
    print(get_pending_orders("BTCUSDT"))

    print("\n=== BTC 倉位 ===")
    print(get_positions("BTCUSDT"))

    # ── 開倉範例（解開註解才會執行）──

    # 市價做多，帶止盈止損
    """
    result = place_order(
        symbol     = "BTCUSDT",
        side       = "BUY",
        order_type = "MARKET",
        qty        = "0.001",
        trade_side = "OPEN",
        tp_price   = "115000",
        sl_price   = "100000",
    )
    print(result)
    """

    # 市價做空，帶止盈止損
    
    result = place_order(
        symbol     = "ETHUSDT",
        side       = "SELL",
        order_type = "MARKET",
        qty        = "0.003",
        trade_side = "OPEN",
        tp_price   = "1600",
        sl_price   = "1760",
    )
    print(result)
    

    # 平倉範例
    #result = close_position(
    #    symbol = "BTCUSDT",
    #    side   = "BUY",
    #    qty    = "0.001",
    #)
    #print(result)