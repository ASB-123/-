import websocket
#WebSocket套件，讓Python能建立WebSocket連線
import json
import time
#等待和取當前時間
import threading
#能執行多個執行緒，讓ping和接收資料同時跑

def send_ping(ws):
# 定義ping函數，ws是WebSocket連線物件，傳進來才能用它發送訊息
    while True:
        time.sleep(20)
        # 等20秒
        try:
            ws.send(json.dumps({"op": "ping", "ping": int(time.time())}))
            #發送ping給伺服器，int(time.time()) 是當前時間（秒）
            #json.dumps()把python語言轉成JSON字串才能發送
            #"op": 告訴伺服器這是什麼操作 → "ping"
            #"ping": 帶上當前時間戳，伺服器會原封不動回傳讓你確認延遲
            #ping pong為bitunix規定
        except:
            break
            #發送失敗代表連線已斷，跳出迴圈結束這個執行緒

def on_open(ws):
    sub = {
        "op"  : "subscribe",
        "args": [{"symbol": "BTCUSDT", "ch": "market_kline_1min"}]
    }
    #訂閱請求，告訴伺服器我要BTC1分K線
    ws.send(json.dumps(sub))
    #發送訂閱請求
    print("已連線")
    threading.Thread(target=send_ping, args=(ws,), daemon=True).start()
    #開新執行緒跑 send_ping
    #target=send_ping : 要跑的函數
    #args=(ws,)       : 把 ws 傳給 send_ping 用
    #daemon=True      : 主程式結束時這個執行緒也自動結束
    #.start()         : 啟動執行緒

def on_message(ws, message):
#每次收到伺服器推送的資料時自動觸發
#message是伺服器傳來的JSON字串
    data = json.loads(message)
    #JSON → Python
    print(data)
    #印出來

def on_error(ws, error):
#發生錯誤時自動觸發
    print("錯誤:", error)

def on_close(ws, close_status_code, close_msg):
# 連線關閉時自動觸發
    print("reconnecting")
    time.sleep(3)
    #等3秒再重連，避免馬上重連失敗
    connect()
    #重新呼叫connect()建立新連線

def connect():
#建立WebSocket連線的函數
    ws = websocket.WebSocketApp(
        "wss://fapi.bitunix.com/public/",
        #WebSocket伺服器網址，wss= 加密版的WebSocket(像https之於http）
        on_open    = on_open,
        #連線成功時呼叫on_open
        on_message = on_message,
        #收到資料時呼叫on_message
        on_error   = on_error,
        #發生錯誤時呼叫on_error
        on_close   = on_close
        #連線關閉時呼叫on_close
        #左邊是固定的，右邊自己取
    )
    ws.run_forever()
    #啟動連線並持續運作，不會自動結束

connect()
#啟動整個程式
