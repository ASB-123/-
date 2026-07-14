"""
bitunix_backtest_smc_v1.py
====================
ICT/SMC 版回測（取代 v21 的 POC 突破邏輯）

進場邏輯：
  1. 依時段自動切換結構判斷時框：紐約盤用5m結構，其餘（亞盤/倫敦盤/盤外）用15m結構
     （時段判斷含冬夏令自動切換，見 liquidity_zones.py）
  2. 該時框上最近一次 BOS/CHoCH 事件形成後，價格回測到綁定的 OB 區間（ob_low ~ ob_high）
     → 以OB回測方向進場（多方結構→找多單，空方結構→找空單）
  3. 同一個結構事件（用 timeframe+ob_time 當唯一鍵）只進場一次，避免重複觸發
  4. OB 訊號有效期：超過 OB_MAX_AGE_BARS 根對應時框K棒未被回測到，視為過期不用

SL：OB 區間邊緣 × 2% 緩衝（多單: ob_low×0.98／空單: ob_high×1.02）

TP：優先抓「進場方向前方最近的關鍵流動性位」
    （1h/4h/8h/日/週/月開盤 + 前日高低），依距離排序取前三個當 TP1/TP2/TP3；
    不足三個則用固定風報比 1.5R/2.5R/4R 補滿。
    分批比例、套保機制（TP1後SL→entry, TP2後SL→TP1）與資金費率計算，
    完全沿用 v21 已驗證過的邏輯，未變更。

本檔案依賴：liquidity_zones.py, smc_structure.py（需放在同一目錄）
"""

import requests
import pandas as pd
import numpy as np
import time
import os
import bisect
from datetime import datetime, timezone

from liquidity_zones import (
    compute_key_opens, compute_prev_day_high_low, get_entry_timeframe, sl_from_ob,
)
from smc_structure import compute_structure_events

BASE_URL  = "https://fapi.bitunix.com"

SYMBOLS   = ["ETHUSDT", "BTCUSDT", "SOLUSDT"]
NOTIONAL  = 25.0
PAGES_5M  = 1060
PAGES_15M = 360
FEE_RATE  = 0.0006
FUND_RATE = 0.000574

SL_BUFFER_PCT     = 0.02
STRUCT_LENGTH_5M  = 50
STRUCT_LENGTH_15M = 50
OB_MAX_AGE_BARS   = 96   # OB 超過這麼多根「對應時框」K棒沒被回測到，視為過期

TP1_RATIO = 0.60
TP2_RATIO = 0.25
TP3_RATIO = 0.15

FUNDING_HOURS_UTC = [0, 8, 16]

# ----------------------------------------------
# 數據抓取（與 v21 相同，未變更）
# ----------------------------------------------

def fetch_klines(symbol, interval, limit=200, end_time=None):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if end_time:
        params["endTime"] = end_time
    for attempt in range(5):
        try:
            res  = requests.get(f"{BASE_URL}/api/v1/futures/market/kline",
                                params=params, timeout=30)
            data = res.json().get("data", [])
            return data
        except Exception as e:
            wait = (attempt + 1) * 5
            print(f"\n  重試 {attempt+1}，等待 {wait}s：{e}")
            time.sleep(wait)
    return []

def fetch_all_klines(symbol, interval, pages):
    cache = f"cache_{symbol}_{interval}.csv"
    if os.path.exists(cache):
        df_c = pd.read_csv(cache)
        df_c["time"] = df_c["time"].astype(int)
        all_data   = df_c.to_dict("records")
        end_time   = df_c["time"].min()
        start_page = len(all_data) // 200
        print(f"  [{symbol} {interval}] 快取 {len(all_data)} 根，從第 {start_page} 頁繼續")
    else:
        all_data, end_time, start_page = [], None, 0

    for p in range(start_page, pages):
        batch = fetch_klines(symbol, interval, limit=200, end_time=end_time)
        if not batch:
            break
        all_data.extend(batch)
        end_time = batch[-1]["time"]
        if (p + 1) % 50 == 0:
            pd.DataFrame(all_data).drop_duplicates("time").to_csv(cache, index=False)
        print(f"  [{symbol} {interval}] {p+1}/{pages}", end="\r")
        time.sleep(0.15)

    df = pd.DataFrame(all_data).drop_duplicates("time")
    for col in ["time", "close", "high", "low", "open"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["baseVol"] = pd.to_numeric(df.get("baseVol", 0), errors="coerce").fillna(0)
    df = df.sort_values("time").reset_index(drop=True)
    df.to_csv(cache, index=False)
    print(f"\n  [{symbol} {interval}] 完成，共 {len(df)} 根")
    return df

# ----------------------------------------------
# 資金費率（與 v21 相同，未變更）
# ----------------------------------------------

def calc_funding_fee_v2(entry_ms, exit_ms, notional):
    if exit_ms <= entry_ms:
        return 0.0
    entry_dt = datetime.fromtimestamp(entry_ms / 1000, tz=timezone.utc)
    exit_dt  = datetime.fromtimestamp(exit_ms  / 1000, tz=timezone.utc)
    count = 0
    day = entry_dt.date()
    last_day = exit_dt.date()
    while day <= last_day:
        for h in FUNDING_HOURS_UTC:
            point = datetime(day.year, day.month, day.day, h, 0, 0, tzinfo=timezone.utc)
            if entry_dt < point <= exit_dt:
                count += 1
        day = day.fromordinal(day.toordinal() + 1)
    return count * FUND_RATE * notional

# ----------------------------------------------
# 同根K棒 SL/TP 先後判斷（與 v21 相同，未變更）
# ----------------------------------------------

def resolve_same_bar_sl_vs_tp(side, o, high, low, sl_price, tp_price):
    sl_hit_raw = (side == "BUY"  and low  <= sl_price) or \
                 (side == "SELL" and high >= sl_price)
    tp_hit_raw = False
    if tp_price is not None:
        tp_hit_raw = (side == "BUY"  and high >= tp_price) or \
                     (side == "SELL" and low  <= tp_price)
    if sl_hit_raw and tp_hit_raw:
        sl_dist = abs(o - sl_price)
        tp_dist = abs(o - tp_price)
        return (True, False) if sl_dist <= tp_dist else (False, True)
    return sl_hit_raw, tp_hit_raw

# ----------------------------------------------
# 新增：流動性關鍵位當 TP 目標
# ----------------------------------------------

LEVEL_COLS = ["open_1h", "open_4h", "open_8h", "open_1d", "open_1w", "open_1M",
              "prev_day_high", "prev_day_low"]

def build_liquidity_targets(row, side, entry):
    """取進場方向前方最近的關鍵流動性位，依距離排序，最多回傳3個"""
    levels = []
    for c in LEVEL_COLS:
        v = row.get(c)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        if side == "BUY" and v > entry:
            levels.append(float(v))
        elif side == "SELL" and v < entry:
            levels.append(float(v))

    levels = sorted(levels) if side == "BUY" else sorted(levels, reverse=True)

    dedup = []
    for lv in levels:
        if not dedup or abs(lv - dedup[-1]) / entry > 0.001:
            dedup.append(lv)
    return dedup[:3]

# ----------------------------------------------
# 單幣回測：結構(BOS/CHoCH) + OB 回測進場
# ----------------------------------------------

def backtest_symbol(symbol, df5, df15):
    positions = []
    trades    = []
    used_obs  = set()   # (timeframe, ob_time) 已進場過的結構事件，避免重複觸發

    df5 = df5.copy()
    df5["returns"]          = df5["close"].pct_change()
    df5["strategy_returns"] = 0.0
    df5 = compute_key_opens(df5)
    df5 = compute_prev_day_high_low(df5)

    print(f"    計算結構事件（5m / 15m 雙時框，BOS/CHoCH + 綁定OB）...")
    ev5  = compute_structure_events(df5,  STRUCT_LENGTH_5M,  "5m").sort_values("time").reset_index(drop=True)
    ev15 = compute_structure_events(df15, STRUCT_LENGTH_15M, "15m").sort_values("time").reset_index(drop=True)
    ev5_times  = ev5["time"].tolist()
    ev15_times = ev15["time"].tolist()
    print(f"    5m 結構事件 {len(ev5)} 筆 / 15m 結構事件 {len(ev15)} 筆")

    def get_active_event(t):
        tf = get_entry_timeframe(t)
        ev, times = (ev5, ev5_times) if tf == "5m" else (ev15, ev15_times)
        pos = bisect.bisect_right(times, t) - 1
        if pos < 0:
            return None, tf
        return ev.iloc[pos], tf

    for i in range(30, len(df5)):
        row  = df5.iloc[i]
        o    = float(row["open"])
        high = float(row["high"])
        low  = float(row["low"])
        t    = int(row["time"])
        close = float(row["close"])

        # ── 更新所有持倉（機制與 v21 完全相同）──
        closed_idx = []
        for pi, pos in enumerate(positions):
            side = pos["side"]
            tp_price_for_order = None
            if pos["tp_hit"] == 0 and pos["tp1"]:
                tp_price_for_order = pos["tp1"]
            elif pos["tp_hit"] == 1 and pos["tp2"]:
                tp_price_for_order = pos["tp2"]
            elif pos["tp_hit"] == 2 and pos["tp3"]:
                tp_price_for_order = pos["tp3"]

            sl_hit, _ = resolve_same_bar_sl_vs_tp(side, o, high, low, pos["sl"], tp_price_for_order)

            if sl_hit:
                qty_r    = pos["remaining_qty"]
                notional = pos["entry_price"] * qty_r
                pnl_raw  = (pos["sl"] - pos["entry_price"]) * qty_r
                if side == "SELL":
                    pnl_raw = -pnl_raw
                fee     = notional * FEE_RATE
                funding = calc_funding_fee_v2(pos["entry_time"], t, notional)
                net     = pnl_raw - fee - funding + pos["realized_pnl"]
                df5.at[i, "strategy_returns"] += \
                    (pos["sl"] - pos["entry_price"]) / pos["entry_price"] * (1 if side == "BUY" else -1)
                trades.append(_make_trade(symbol, pos, t, pos["sl"],
                              "撞到止損" if pos["tp_hit"] == 0 else "撞到止損(已套保)",
                              net, fee + pos["fee_paid"], funding + pos["fund_paid"]))
                closed_idx.append(pi)
                continue

            tp1_hit = (side == "BUY"  and pos["tp_hit"] == 0 and pos["tp1"] and high >= pos["tp1"]) or \
                      (side == "SELL" and pos["tp_hit"] == 0 and pos["tp1"] and low  <= pos["tp1"])
            if tp1_hit:
                qty_c   = pos["initial_qty"] * TP1_RATIO
                notional= pos["entry_price"] * qty_c
                pnl_raw = abs(pos["tp1"] - pos["entry_price"]) * qty_c
                fee     = notional * FEE_RATE
                funding = calc_funding_fee_v2(pos["entry_time"], t, notional)
                net     = pnl_raw - fee - funding
                pos["realized_pnl"]  += net
                pos["fee_paid"]      += fee
                pos["fund_paid"]     += funding
                pos["remaining_qty"] -= qty_c
                pos["tp_hit"]         = 1
                pos["sl"]             = pos["entry_price"]
                pos["hedged"]         = True

                new_sl_hit, _ = resolve_same_bar_sl_vs_tp(side, o, high, low, pos["sl"], pos["tp2"])
                if new_sl_hit:
                    qty_r    = pos["remaining_qty"]
                    notional = pos["entry_price"] * qty_r
                    fee      = notional * FEE_RATE
                    funding  = calc_funding_fee_v2(pos["entry_time"], t, notional)
                    net      = 0.0 - fee - funding + pos["realized_pnl"]
                    trades.append(_make_trade(symbol, pos, t, pos["sl"], "撞到止損(已套保)",
                                              net, fee + pos["fee_paid"], funding + pos["fund_paid"]))
                    closed_idx.append(pi)
                    continue

            tp2_hit = (side == "BUY"  and pos["tp_hit"] == 1 and pos["tp2"] and high >= pos["tp2"]) or \
                      (side == "SELL" and pos["tp_hit"] == 1 and pos["tp2"] and low  <= pos["tp2"])
            if tp2_hit:
                qty_c   = pos["initial_qty"] * TP2_RATIO
                notional= pos["entry_price"] * qty_c
                pnl_raw = abs(pos["tp2"] - pos["entry_price"]) * qty_c
                fee     = notional * FEE_RATE
                funding = calc_funding_fee_v2(pos["entry_time"], t, notional)
                net     = pnl_raw - fee - funding
                pos["realized_pnl"]  += net
                pos["fee_paid"]      += fee
                pos["fund_paid"]     += funding
                pos["remaining_qty"] -= qty_c
                pos["tp_hit"]         = 2
                pos["sl"]             = pos["tp1"]

                new_sl_hit, _ = resolve_same_bar_sl_vs_tp(side, o, high, low, pos["sl"], pos["tp3"])
                if new_sl_hit:
                    qty_r    = pos["remaining_qty"]
                    notional = pos["entry_price"] * qty_r
                    pnl_raw  = abs(pos["sl"] - pos["entry_price"]) * qty_r
                    fee      = notional * FEE_RATE
                    funding  = calc_funding_fee_v2(pos["entry_time"], t, notional)
                    net      = pnl_raw - fee - funding + pos["realized_pnl"]
                    trades.append(_make_trade(symbol, pos, t, pos["sl"], "撞到止損(已套保)",
                                              net, fee + pos["fee_paid"], funding + pos["fund_paid"]))
                    closed_idx.append(pi)
                    continue

            tp3_hit = (side == "BUY"  and pos["tp_hit"] == 2 and pos["tp3"] and high >= pos["tp3"]) or \
                      (side == "SELL" and pos["tp_hit"] == 2 and pos["tp3"] and low  <= pos["tp3"])
            if tp3_hit:
                qty_c   = pos["remaining_qty"]
                notional= pos["entry_price"] * qty_c
                pnl_raw = abs(pos["tp3"] - pos["entry_price"]) * qty_c
                fee     = notional * FEE_RATE
                funding = calc_funding_fee_v2(pos["entry_time"], t, notional)
                net     = pnl_raw - fee - funding + pos["realized_pnl"]
                df5.at[i, "strategy_returns"] += abs(pos["tp3"] - pos["entry_price"]) / pos["entry_price"]
                trades.append(_make_trade(symbol, pos, t, pos["tp3"], "撞到止盈",
                                          net, fee + pos["fee_paid"], funding + pos["fund_paid"]))
                closed_idx.append(pi)

        for pi in sorted(closed_idx, reverse=True):
            positions.pop(pi)

        # ── 進場條件：結構事件(BOS/CHoCH) + OB 回測 ──
        event, tf = get_active_event(t)
        if event is None:
            continue

        age_ms = t - int(event["time"])
        bar_min = 5 if tf == "5m" else 15
        max_age_ms = OB_MAX_AGE_BARS * bar_min * 60 * 1000
        key = (tf, int(event["ob_time"]))

        if age_ms > max_age_ms or key in used_obs:
            continue

        ob_low, ob_high = float(event["ob_low"]), float(event["ob_high"])
        side = "BUY" if event["direction"] == "bullish" else "SELL"

        retest = ob_low <= close <= ob_high
        if not retest:
            continue

        entry = close
        sl = sl_from_ob(ob_low, ob_high, side, SL_BUFFER_PCT)
        risk_dist = abs(entry - sl)
        if risk_dist <= 0:
            continue

        targets = build_liquidity_targets(row, side, entry)
        while len(targets) < 3:
            mult = [1.5, 2.5, 4.0][len(targets)]
            targets.append(entry + risk_dist * mult if side == "BUY" else entry - risk_dist * mult)
        tp1, tp2, tp3 = targets[:3]

        qty      = NOTIONAL / entry
        open_fee = NOTIONAL * FEE_RATE
        risk_usdt = risk_dist * qty

        positions.append({
            "symbol": symbol, "side": side, "entry_price": entry, "sl": sl,
            "tp1": tp1, "tp2": tp2, "tp3": tp3, "tp_hit": 0, "hedged": False,
            "initial_qty": qty, "remaining_qty": qty, "realized_pnl": -open_fee,
            "fee_paid": open_fee, "fund_paid": 0.0, "entry_time": t, "risk_usdt": risk_usdt,
            "structure_tf": tf, "structure_type": event["type"],
        })
        used_obs.add(key)

    return trades, df5


def _make_trade(symbol, pos, exit_time, exit_price, exit_reason, net_pnl, fee_total, fund_total):
    risk = pos["risk_usdt"] if pos["risk_usdt"] > 0 else 1e-9
    r_multiple = net_pnl / risk
    return {
        "Time"      : datetime.fromtimestamp(pos["entry_time"] / 1000).strftime("%Y/%m/%d %H:%M"),
        "Symbol"    : symbol,
        "Direction" : "long" if pos["side"] == "BUY" else "short",
        "Entry"     : round(pos["entry_price"], 4),
        "Stop"      : round(pos["sl"] if pos["tp_hit"] == 0 else pos["entry_price"], 4),
        "Target"    : round(pos["tp1"], 4) if pos["tp1"] else "-",
        "Exit"      : round(exit_price, 4),
        "Size"      : round(pos["initial_qty"], 6),
        "進場原因"   : f"{pos['structure_tf']} {pos['structure_type']} 結構後OB回測進場",
        "出場原因"   : exit_reason,
        "RISK"      : round(risk, 4),
        "Result"    : round(net_pnl, 4),
        "R_Multiple": round(r_multiple, 4),
        "Hedged?"   : "Y" if pos["hedged"] else "N",
        "tp_hit"    : pos["tp_hit"],
        "exit_time" : datetime.fromtimestamp(exit_time / 1000).strftime("%Y/%m/%d %H:%M"),
        "fee_total" : round(fee_total, 4),
        "fund_total": round(fund_total, 4),
    }

# ----------------------------------------------
# 統計與輸出（與 v21 相同，未變更）
# ----------------------------------------------

def compute_stats(df_all):
    df_all = df_all.sort_values("Time").reset_index(drop=True)
    df_all["cum_pnl"] = df_all["Result"].cumsum()
    total  = len(df_all)
    wins   = df_all[df_all["Result"] > 0]
    losses = df_all[df_all["Result"] <= 0]
    win_rate = len(wins) / total * 100 if total else 0
    not_hedged = df_all[df_all["Hedged?"] == "N"]
    avg_r_no_hedge = not_hedged["R_Multiple"].mean() if len(not_hedged) else 0
    hedged = df_all[df_all["Hedged?"] == "Y"]
    hedged_count = len(hedged)
    avg_r_hedged = hedged["R_Multiple"].mean() if hedged_count else 0
    avg_win  = wins["Result"].mean()   if len(wins)   else 0
    avg_loss = losses["Result"].mean() if len(losses) else 0
    avg_rr   = abs(avg_win / avg_loss) if avg_loss != 0 else float("nan")
    returns = df_all["Result"]
    sharpe = returns.mean() / returns.std() * np.sqrt(len(returns)) if returns.std() > 0 else float("nan")
    cum = df_all["cum_pnl"]
    max_dd = (cum - cum.cummax()).min()
    return {
        "total": total, "win_rate": win_rate, "avg_r_no_hedge": avg_r_no_hedge,
        "avg_win": avg_win, "avg_loss": avg_loss, "avg_rr": avg_rr, "sharpe": sharpe,
        "max_dd": max_dd, "hedged_count": hedged_count, "avg_r_hedged": avg_r_hedged,
        "final_cum_pnl": cum.iloc[-1] if total else 0,
    }

def print_results(all_trades, dfs):
    if not all_trades:
        print("無交易信號")
        return
    df_all = pd.DataFrame(all_trades)
    stats  = compute_stats(df_all)
    sym_counts = df_all.groupby("Symbol").size().to_dict()
    total_fee  = df_all["fee_total"].sum()
    total_fund = df_all["fund_total"].sum()

    print(f"\n{'='*70}")
    print(f"{' / '.join(SYMBOLS)}  ICT/SMC結構+OB回測進場  流動性關鍵位分批止盈 [smc_v1]")
    print(f"倉位：{NOTIONAL} USDT/筆  手續費：VIP0 {FEE_RATE*100}%  資金費率：{FUND_RATE*100}%/8h")
    print(f"{'='*70}")
    for sym in SYMBOLS:
        n       = sym_counts.get(sym, 0)
        sym_net = df_all[df_all["Symbol"] == sym]["Result"].sum()
        sym_l   = (df_all[df_all["Symbol"] == sym]["Direction"] == "long").sum()
        sym_s   = (df_all[df_all["Symbol"] == sym]["Direction"] == "short").sum()
        print(f"  {sym:<10} 交易 {n:>4} 次（多 {sym_l} / 空 {sym_s}）  淨盈虧 {sym_net:>+.4f} USDT")
    print(f"{'─'*70}")
    print(f"總交易次數      : {stats['total']}")
    print(f"累積 PnL        : {stats['final_cum_pnl']:+.4f} USDT")
    print(f"勝率(%)         : {stats['win_rate']:.1f}%")
    print(f"平均R倍數(不含套保): {stats['avg_r_no_hedge']:+.4f}")
    print(f"平均盈利單      : {stats['avg_win']:+.4f} USDT")
    print(f"平均虧損單      : {stats['avg_loss']:+.4f} USDT")
    print(f"平均盈虧比      : {stats['avg_rr']:.2f}")
    print(f"夏普比率        : {stats['sharpe']:.3f}")
    print(f"最大回撤        : {stats['max_dd']:.4f} USDT")
    print(f"套保策略數      : {stats['hedged_count']}")
    print(f"套保後平均R倍數 : {stats['avg_r_hedged']:+.4f}")
    print(f"{'─'*70}")
    print(f"總手續費        : -{total_fee:.4f} USDT")
    print(f"總資金費率      : -{total_fund:.4f} USDT")
    print(f"{'='*70}")

    out = "backtest_result_smc_v1.csv"
    cols = ["Time","Symbol","Direction","Entry","Stop","Target","Exit","Size",
            "進場原因","出場原因","RISK","Result","R_Multiple","Hedged?"]
    try:
        df_all[cols].to_csv(out, index=False, encoding="utf-8-sig")
        print(f"\n結果已存至 {out}")
    except PermissionError:
        print(f"\n[!] {out} 被佔用，請關閉 Excel")

# ----------------------------------------------
# 主程序
# ----------------------------------------------

if __name__ == "__main__":
    all_trades = []
    dfs        = {}
    for sym in SYMBOLS:
        print(f"\n=== {sym} ===")
        df5  = fetch_all_klines(sym, "5m",  PAGES_5M)
        df15 = fetch_all_klines(sym, "15m", PAGES_15M)
        print(f"  回測中...")
        trades, df5 = backtest_symbol(sym, df5, df15)
        all_trades.extend(trades)
        dfs[sym] = df5
        print(f"  {sym} 完成，{len(trades)} 筆交易")
    print_results(all_trades, dfs)