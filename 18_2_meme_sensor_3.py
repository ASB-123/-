"""
bitunix_ma_macd_scanner_v2.py
====================
[工具] 多幣種均線排列 + MACD金叉 掃描器 —— v2 優化版

策略邏輯不變：EMA20 > EMA60 > EMA120（多頭排列）且 MACD柱狀圖(hist)由負轉正
（金叉發生在上一根到這一根之間），在1h/4h兩個時間框架分別檢查。

跟原版的差異（這次討論出的三個修正）：
─────────────────────────────────────────────────────────
  [修正1] K線陣列排序方向，不再依賴API回傳順序的假設
      原版：直接對API回傳的list建DataFrame，用.iloc[-1]/.iloc[-2]當作
      「最新/次新」K棒，但官方文件完全沒寫明回傳陣列是正序還是倒序。
      如果實際是倒序（新的在前面），所有指標會系統性算反，且不會報錯。
      v2：明確用回傳資料裡的 time 欄位排序（升序）後再取用，不管API
      實際回傳順序為何，結果都正確。

  [修正2] EMA120在只有150根K棒時還沒真正收斂
      原版：limit=150，但EMA(span=120)經驗法則上需要3-5倍span（360-600根）
      才會收斂到接近真正的120期指數移動平均，150根的EMA120還帶著初始值
      的偏差，尤其是資料起點剛好是劇烈趨勢時偏差更明顯。
      v2：limit拉高到API上限200（官方文件寫明maximum: 200），雖然仍不到
      理論收斂所需的360-600根，但這已經是單次API呼叫能拿到的上限，如果
      要更精確收斂，需要用startTime/endTime分頁多次抓取更長歷史（v2先
      不做這個，先把「能在單次呼叫內做到最好」的部分修好，並在註解裡
      誠實標注這個限制還在）。

  [修正3] 排除還沒收盤的「進行中K棒」，避免重繪(repainting)
      原版：可能把最後一根還在形成中的K棒當成「已收盤」納入指標計算，
      過幾分鐘同一根K棒的收盤價變了，訊號會消失或反轉。
      v2：用 time 欄位 + 該時間框架的K棒週期長度，判斷最後一根是否已經
      收盤，未收盤的話直接捨棄，只用已收盤的K棒算指標。

[優化4] 幣種清單改用 trading_pairs（帶symbolStatus過濾），跟你另一支
      資金費結算週期掃描工具用同一套邏輯，只抓OPEN狀態的幣，避免抓到
      已下架/停牌但tickers端點可能還留著的幣，浪費API額度。

[⚠ 這次沒動、繼續誠實揭露的限制]
  1. 這是即時掃描工具，不是回測——沒有歷史勝率、Sharpe等統計驗證，
     純粹是「現在這個時間點，哪些幣符合技術面條件」的篩選器。
  2. EMA120收斂限制（見上方修正2說明）只緩解沒有根除，如果要嚴謹驗證
     這組訊號的歷史有效性，還是需要另外寫回測（用更長的K線歷史，逐根
     滾動計算指標，而不是像這樣只看單一個時間點的快照）。
  3. Rate limit 官方寫 10 req/sec/ip，這裡用保守間隔，不要調快。
─────────────────────────────────────────────────────────
"""

import requests
import pandas as pd
import time
from datetime import datetime, timezone

BASE_URL = "https://fapi.bitunix.com"
REQ_INTERVAL_SEC = 0.12   # 10 req/sec上限，保守節流

TIMEFRAMES = ["1h", "4h"]
KLINE_LIMIT = 200          # API上限就是200，見官方文件 Get Kline

# 各interval對應的毫秒數，用來判斷「最後一根K棒是否已收盤」
INTERVAL_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000,
    "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000,
    "3d": 259_200_000, "1w": 604_800_000,
}

MIN_BARS_REQUIRED = 130   # 至少要有130根收盘K棒才計算指標（ema120至少要有資料）


# ----------------------------------------------
# API
# ----------------------------------------------

def get_open_symbols():
    """[優化4] 用 trading_pairs 抓OPEN狀態的幣，跟資金費結算週期掃描工具邏輯一致"""
    res = requests.get(f"{BASE_URL}/api/v1/futures/market/trading_pairs", timeout=15)
    data = res.json()
    if data.get("code") not in (0, "0"):
        raise RuntimeError(f"trading_pairs 查詢失敗：{data}")
    pairs = data.get("data", [])
    open_symbols = [p["symbol"] for p in pairs
                    if p.get("symbolStatus") == "OPEN" and p["symbol"].endswith("USDT")]
    print(f"  [trading_pairs] 共 {len(pairs)} 個交易對，OPEN且為USDT對的有 {len(open_symbols)} 個")
    return open_symbols


def get_klines(symbol, interval, limit=KLINE_LIMIT):
    """
    [修正1][修正3] 抓K線後明確用time排序、並剔除尚未收盤的最後一根。
    回傳 None 代表資料不足或抓取失敗，呼叫端要能處理。
    """
    try:
        res = requests.get(
            f"{BASE_URL}/api/v1/futures/market/kline",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=10
        )
        data = res.json().get("data", [])
        if not data:
            return None

        df = pd.DataFrame(data)
        if "time" not in df.columns:
            # 保底：萬一回傳格式跟文件不一致，沒有time欄位就無法安全排序，直接放棄這筆
            return None

        df["time"] = df["time"].astype(int)
        df["close"] = df["close"].astype(float)

        # [修正1] 明確用時間戳排序，不依賴API回傳順序的假設
        df = df.sort_values("time").reset_index(drop=True)

        # [修正3] 剔除還沒收盤的最後一根K棒
        interval_ms = INTERVAL_MS.get(interval)
        if interval_ms:
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            last_bar_close_time = df["time"].iloc[-1] + interval_ms
            if last_bar_close_time > now_ms:
                df = df.iloc[:-1]  # 最後一根還沒收盤，丟掉

        if len(df) < MIN_BARS_REQUIRED:
            return None

        return df
    except Exception as e:
        print(f"\n  [{symbol} {interval}] 抓取失敗：{e}")
        return None


# ----------------------------------------------
# indicator
# ----------------------------------------------

def calc_indicators(df):
    ema20 = df['close'].ewm(span=20, adjust=False).mean()
    ema60 = df['close'].ewm(span=60, adjust=False).mean()
    ema120 = df['close'].ewm(span=120, adjust=False).mean()

    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    hist = dif - dea

    return {
        "ema20_now": ema20.iloc[-1],
        "ema60_now": ema60.iloc[-1],
        "ema120_now": ema120.iloc[-1],
        "hist_now": hist.iloc[-1],
        "hist_prev": hist.iloc[-2],
        "last_bar_time": df["time"].iloc[-1],
    }


def check_conditions(ind):
    ma_aligned = ind["ema20_now"] > ind["ema60_now"] > ind["ema120_now"]
    macd_cross = ind["hist_prev"] < 0 and ind["hist_now"] > 0
    return ma_aligned and macd_cross


# ----------------------------------------------
# scanner
# ----------------------------------------------

def scan():
    print("=== 均線排列 + MACD金叉 多幣種掃描器 v2 ===\n")
    print("取得所有OPEN狀態的USDT交易對...")
    symbols = get_open_symbols()
    total = len(symbols)
    print(f"開始掃描 {total} 個幣種...\n")

    results = []
    skipped_insufficient_data = []

    for i, symbol in enumerate(symbols, 1):
        matched_tf = []

        for tf in TIMEFRAMES:
            df = get_klines(symbol, tf)
            time.sleep(REQ_INTERVAL_SEC)

            if df is None:
                skipped_insufficient_data.append(f"{symbol}({tf})")
                continue

            ind = calc_indicators(df)
            if check_conditions(ind):
                matched_tf.append(tf)

        if matched_tf:
            results.append({"symbol": symbol, "timeframes": ", ".join(matched_tf)})
            print(f"  符合：{symbol:<15} [{', '.join(matched_tf)}]")

        if i % 20 == 0:
            print(f"  進度：{i}/{total}")

    print("\n" + "=" * 45)
    print(f"掃描完成，共 {len(results)} 個符合條件")
    print("=" * 45)

    if results:
        print(f"\n{'Symbol':<18} 時間框架")
        print("-" * 35)
        for r in results:
            print(f"{r['symbol']:<18} {r['timeframes']}")
    else:
        print("  這次掃描沒有符合條件的幣種")

    if skipped_insufficient_data:
        print(f"\n[!] 有 {len(skipped_insufficient_data)} 筆(symbol,timeframe)因資料不足或抓取失敗被跳過")
        print(f"    （K棒數 < {MIN_BARS_REQUIRED} 根，或該幣該時間框架上市不夠久／API暫時失敗）")
        if len(skipped_insufficient_data) <= 20:
            print(f"    清單：{', '.join(skipped_insufficient_data)}")

    if results:
        pd.DataFrame(results).to_csv("scan_result_ma_macd.csv", index=False, encoding="utf-8-sig")
        print(f"\n結果已存至 scan_result_ma_macd.csv")

    print(f"\n[提醒] 這是即時快照，不是回測——上面的訊號只代表「這次掃描當下」符合條件，")
    print(f"       沒有歷史勝率/統計驗證。若要驗證這組邏輯的歷史有效性，需要另外寫逐根")
    print(f"       滾動回測，而不是靠這種單點掃描結果來判斷策略好壞。")


if __name__ == "__main__":
    scan()