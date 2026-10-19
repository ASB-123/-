import requests
import time
import uuid
#產生隨機碼
import hashlib
#哈希算法(加密用的)
import json
#字典 ↔ JSON字串互轉

API_KEY = "0546d75bbf46fa213acecc9a056e8e0c"
API_SECRET = "3569601ebdbaca053f1e70679e97fe44"

BASE_URL = "https://fapi.bitunix.com"

def sha256(s):
    """
        加密成 64 碼的雜湊值，用來產生簽名. s為任意字串, encode()是把字串轉成bytes(2進制), hexdigest()再轉成16進制
        加密好的return輸出. 不然拿不到結果
    """
    return hashlib.sha256(s.encode()).hexdigest()

def request_private(method, path, query_params= None, body= None):
    """
        method      : "GET"（查詢）或 "POST"（下單/操作）
        path        : API 路徑，例如 "/api/v1/futures/account"
        query_params: GET 參數，放在網址後面，預設 None(有需要, 在呼叫)
        body        : POST 參數，放在請求內容裡，預設 None(有需要, 在呼叫)
    """

    nonce     = uuid.uuid4().hex
    #uuid4() 產生隨機 UUID(16進制)，.hex為以16進制存取附帶能去掉破折號變成純字串
    #每次請求都不一樣，防止有人截取請求重複發送（重放攻擊）
    timestamp = str(int(time.time() * 1000))
    #time.time(): 當前時間（秒+浮點數）. int(): 去掉小數點. str(): 轉字串，因為之後要做字串拼接

    if query_params:
        query = "".join(f"{k}{query_params[k]}" for k in sorted(query_params))
        #.join(...)為把所有結果拼在一起，""為中間不加任何字元
        #for k in 就是把清單裡每個元素依序拿出來，每次放進k裡處理
        #f"{k}{query_params[k]}"用f string拼接
    else:
        query = ""
        #沒有 GET 參數就給空字串

    # ---- body ----
    if body:
        body_str = json.dumps(body, separators=(",", ":"), sort_keys=True)
        #json.dumps(): python → JSON 字串
        #separators=(",",":"): 去掉空格，{"a": 1} → {"a":1}（空格會讓簽名不一樣）
        #sort_keys=True: key(字母)排序，確保每次順序一致
    else:
        body_str = ""
        #沒有 post 參數就給空字串

    # ---- sign ----
    digest = sha256(nonce + timestamp + API_KEY + query + body_str)
    #第一次加密：把所有請求資訊拼在一起壓縮成雜湊值
    sign   = sha256(digest + API_SECRET)
    #第二次加密：加入SECRET再加密一次

    headers = {
        "api-key"      : API_KEY,
        "nonce"        : nonce,
        "timestamp"    : timestamp,
        "sign"         : sign,
        "Content-Type" : "application/json"
    }

    url = BASE_URL + path

    if method == "GET":
        res = requests.get(url, headers=headers, params=query_params)
        #params=query_params : requests 自動把字典轉成 ?marginCoin=USDT 加在網址後面
    else:
        res = requests.post(url, headers=headers, data=body_str)
        #data=body_str : 把 JSON 字串放在請求內容裡送出
    return res.json()
    #回傳json給使用者

# 查帳戶餘額（要加 marginCoin 參數）
result = request_private(
    method="GET",
    path="/api/v1/futures/account",
    query_params={"marginCoin": "USDT"}
)
print(result)

# 測試查訂單
result = request_private(
    method="GET",
    path="/api/v1/futures/trade/get_pending_orders",
    query_params={"symbol": "BTCUSDT"}
)
print(result)