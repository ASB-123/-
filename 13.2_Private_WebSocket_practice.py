import websocket
import requests
import time
import uuid
import hashlib
import json
import threading

API_KEY    = "3c676ce499a61174f6dd03f0c9487f9e"
SECRET_KEY = "6d52ad24dfb94cd6e59267ce5165e5c3"
BASE_URL   = "https://fapi.bitunix.com"

def sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()

def request_private(method, path, query_params=None, body=None):
    nonce     = uuid.uuid4().hex
    timestamp = str(int(time.time() * 1000))

    if query_params:
        query = "".join(f"{k}{query_params[k]}" for k in sorted(query_params))
    else:
        query = ""

    if body:
        body_str = json.dumps(body, separators=(",", ":"), sort_keys=True)
    else:
        body_str = ""

    squeeze = sha256(nonce + timestamp + API_KEY + query + body_str)
    sign    = sha256(squeeze + SECRET_KEY)

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

def send_ping(ws):
    while True:
        time.sleep(60)
        try:
            ws.send(json.dumps({"op": "ping", "ping": int(time.time())}))
        except:
            break

def on_open(ws):
    sub = {
        "op"  : "subscribe",
        "args": [{"symbol": "ETHUSDT", "ch": "market_kline_1min"}]
    }
    ws.send(json.dumps(sub))
    print("已連線")
    threading.Thread(target=send_ping, args=(ws,), daemon=True).start()

def on_message(ws, message):
    data = json.loads(message)
    print(data)

def on_error(ws, error):
    print("錯誤:", error)

def on_close(ws, close_status_code, close_msg):
    print("reconnecting")
    time.sleep(3)
    connect()

def connect():
    ws = websocket.WebSocketApp(
        "wss://fapi.bitunix.com/public/",
        on_open   =on_open,
        on_message=on_message,
        on_error  =on_error,
        on_close  =on_close
    )
    ws.run_forever()

connect()