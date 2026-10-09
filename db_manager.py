import logging
import os
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

# Guard against Windows AppLocker / WDAC blocking pyarrow DLL
try:
    import pyarrow.compute  # noqa: F401
except Exception:
    import sys

    sys.modules["pyarrow"] = None

import pandas as pd

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
from supabase import Client, create_client

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_supabase: Client = None

BUY_ACTIONS = {"🟢 MUA", "🟢 TÍCH LŨY", "🟢 ACCUMULATE", "🟢 VALUE BUY", "RECOMMEND_BUY", "MUA", "BUY"}
BUY_KEYWORDS = ("MUA", "TÍCH LŨY", "ACCUMULATE", "BUY")


def count_trading_days(start_date: Any, end_date: Any, holidays: set | None = None) -> int:
    """Calculate the number of trading days between start_date and end_date.

    Excludes weekends (Saturday, Sunday) and holidays.
    If start_date == end_date, returns 0.
    """
    if not start_date or not end_date:
        return 0
    if hasattr(start_date, "date"):
        d1 = start_date.date()
    elif isinstance(start_date, str):
        d1 = datetime.fromisoformat(start_date.replace("Z", "+00:00")).date()
    else:
        d1 = start_date

    if hasattr(end_date, "date"):
        d2 = end_date.date()
    elif isinstance(end_date, str):
        d2 = datetime.fromisoformat(end_date.replace("Z", "+00:00")).date()
    else:
        d2 = end_date

    if d1 >= d2:
        return 0

    holidays_set = holidays or set()
    cur = d1 + timedelta(days=1)
    trading_days = 0
    while cur <= d2:
        if cur.weekday() < 5 and cur not in holidays_set:
            trading_days += 1
        cur += timedelta(days=1)
    return trading_days


def get_supabase_client() -> Client:
    """Initialize and return the Supabase client (singleton, auto-cleans URL)."""
    global _supabase
    if _supabase is None:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_KEY", "").strip()

        if not url or not key:
            logging.warning("SUPABASE_URL or SUPABASE_KEY not configured in .env")
            return None

        # Automatically strip /rest/v1 suffix or trailing slashes
        clean_url = url.split("/rest/v1")[0].rstrip("/")

        try:
            _supabase = create_client(clean_url, key)
        except Exception as e:
            logging.exception("Failed to initialize Supabase client")
            return None
    return _supabase


def save_quant_signal(
    symbol: str,
    action: str,
    decision_tag: str,
    entry_price: float,
    market_price_at_signal: float = None,
    target_price: float = None,
    stop_loss: float = None,
    hard_gates: dict = None,
    f_score_res: dict = None,
    z_score_res: dict = None,
    prob_dict: dict = None,
    model_version: str = "gemini-flash-v2.1",
    input_snapshot: dict = None,
    decision_id: str = None,
) -> int:
    """Save an immutable signal snapshot to Supabase when a buy/sell signal fires.

    Stores the complete context at signal time: entry price, hard gate results,
    F-Score, Z-Score, probabilities, and raw input data. Also creates an
    initial OPEN tracking record for post-market audit.

    Returns:
        Signal ID (int) on success, or None on failure.
    """
    client = get_supabase_client()
    if not client:
        return None

    # TASK-0052: Conditional save_quant_signal - chỉ lưu các lệnh MUA thật sự
    action_clean = str(action or "").strip()
    is_buy = (
        action_clean in BUY_ACTIONS
        or any(k in action_clean.upper() for k in BUY_KEYWORDS)
    )
    if not is_buy:
        logging.info("Bỏ qua lưu quyết định non-BUY vào bảng signals: action='%s'", action)
        return None

    hard_gates = hard_gates or {}
    f_score_res = f_score_res or {}
    z_score_res = z_score_res or {}
    prob_dict = prob_dict or {}
    mkt_price = float(market_price_at_signal) if market_price_at_signal else float(entry_price)

    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        data = {
            "symbol": symbol.upper().strip(),
            "created_at": now_iso,
            "action": action,
            "decision_tag": decision_tag,
            "entry_price": float(entry_price),
            "target_price": float(target_price) if target_price else None,
            "stop_loss": float(stop_loss) if stop_loss else None,
            "mos_pct": float(hard_gates.get("mos_pct", 0.0)),
            "ev_price": float(hard_gates.get("ev", 0.0)),
            "kelly_f": float(hard_gates.get("kelly_f", 0.0)),
            "risk_reward": float(hard_gates.get("risk_reward", 0.0)),
            "f_score": int(f_score_res.get("score", 0)),
            "z_score": float(z_score_res.get("z_score", 0.0)),
            "p_bull": float(prob_dict.get("P_bull", 0.25)),
            "p_base": float(prob_dict.get("P_base", 0.50)),
            "p_bear": float(prob_dict.get("P_bear", 0.25)),
            "ai_thesis": prob_dict.get("rationale_base", ""),
            "model_version": model_version,
            "data_gate_passed": bool(hard_gates.get("data_gate_passed", True)),
            "input_snapshot": {
                "market_price_at_signal": mkt_price,
                "timestamp_vn": datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S"),
                **(input_snapshot or {}),
            },
        }

        res = client.table("signals").insert(data).execute()
        if not res.data:
            return None
        signal_id = res.data[0]["id"]

        # Khởi tạo bản ghi tracking tương ứng ở trạng thái OPEN
        client.table("signal_tracking").insert(
            {"signal_id": signal_id, "status": "OPEN", "max_favorable_price": mkt_price, "max_adverse_price": mkt_price}
        ).execute()

        # Lưu bản ghi vòng đời tín hiệu (Phase 3)
        try:
            save_signal_lifecycle(
                {
                    "signal_id": signal_id,
                    "decision_id": decision_id,
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "f_score": f_score_res.get("score", 0),
                    "mos_pct": hard_gates.get("mos_pct", 0.0),
                    "initial_target_price": target_price,
                    "initial_stop_price": stop_loss,
                }
            )
        except Exception:
            logging.exception("Lỗi khi lưu signal_lifecycle")

        logging.info(f"✅ ĐÃ LƯU SNAPSHOT TÍN HIỆU {symbol} (ID: {signal_id}) VÀO SUPABASE THÀNH CÔNG!")
        return signal_id
    except Exception:
        logging.exception("Lỗi khi lưu tín hiệu vào Supabase")
        return None


def fetch_open_signals() -> list:
    """Fetch all signals with OPEN status for the post-market audit process."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        res = client.table("signals").select("*, signal_tracking(*)").execute()
        open_list = []
        for row in res.data or []:
            trackings = row.get("signal_tracking") or []
            if trackings and trackings[0].get("status") == "OPEN":
                row["tracking"] = trackings[0]
                open_list.append(row)
        return open_list
    except Exception as e:
        logging.exception("Failed to query open signals")
        return []


def check_symbol_recent_signal(symbol: str, days: int = 5) -> bool:
    """Check if a ticker has had a BUY signal within the last N days on Supabase."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = (
            client.table("signals")
            .select("id, symbol, created_at, action")
            .eq("symbol", symbol.upper().strip())
            .gte("created_at", cutoff)
        )
        try:
            query = query.or_("action.ilike.%MUA%,action.ilike.%TÍCH LŨY%,action.ilike.%ACCUMULATE%,action.ilike.%BUY%")
        except Exception:
            pass
        res = query.execute()
        if not res.data:
            return False

        matching = [
            r for r in res.data
            if any(k in (r.get("action") or "").upper() for k in BUY_KEYWORDS)
        ]
        return len(matching) > 0
    except Exception as e:
        logging.debug(f"Error checking Supabase signal cooldown for {symbol}: {e}")
        return False


def mark_non_buy_signals_invalid() -> int:
    """Sanitize legacy signals and tracking by marking non-BUY records as INVALID.

    Prevents legacy WATCH / REDUCE records from clogging OPEN positions.
    """
    client = get_supabase_client()
    if not client:
        return 0
    try:
        res = client.table("signals").select("id, action").execute()
        if not res.data:
            return 0
        invalid_ids = []
        for r in res.data:
            act = str(r.get("action", "")).upper()
            if not any(k in act for k in BUY_KEYWORDS):
                invalid_ids.append(r["id"])

        if invalid_ids:
            client.table("signal_tracking").update({"status": "INVALID"}).in_("signal_id", invalid_ids).execute()
        return len(invalid_ids)
    except Exception:
        logging.exception("Lỗi khi đánh dấu tín hiệu non-buy thành INVALID")
        return 0


def get_open_signals_count() -> int:
    """Count active OPEN positions in Supabase signal_tracking table."""
    client = get_supabase_client()
    if not client:
        return 0
    try:
        res = client.table("signal_tracking").select("id", count="exact").eq("status", "OPEN").execute()
        if hasattr(res, "count") and res.count is not None:
            return res.count
        return len(res.data or [])
    except Exception as e:
        logging.debug(f"Error counting open signals: {e}")
        return 0


def calculate_holding_period_benchmark_return(
    benchmark_symbol: str = "VNINDEX",
    start_date: Any = None,
    end_date: Any = None,
    benchmark_df: Optional[pd.DataFrame] = None,
    fallback_daily_chg: float = 0.0,
) -> float:
    """Calculate the cumulative return of a benchmark index over the exact holding period.

    Args:
        benchmark_symbol: Index ticker, e.g. "VNINDEX" or "VN30".
        start_date: Entry date (string or datetime).
        end_date: Exit date (string or datetime).
        benchmark_df: Optional pre-fetched historical DataFrame with 'time' and 'close'.
        fallback_daily_chg: Fallback return if historical data cannot be aligned.

    Returns:
        Holding period return in percent (e.g. 5.25 for +5.25%), rounded to 2 decimals.
    """
    if benchmark_df is None:
        try:
            from data_engine import fetch_index_historical

            benchmark_df = fetch_index_historical(symbol=benchmark_symbol, limit=120)
        except Exception:
            logging.debug("Could not fetch index historical for %s", benchmark_symbol)

    if benchmark_df is None or benchmark_df.empty or "close" not in benchmark_df.columns:
        return round(float(fallback_daily_chg), 2)

    df = benchmark_df.copy()
    time_col = "time" if "time" in df.columns else ("date" if "date" in df.columns else None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        df = df.dropna(subset=[time_col]).sort_values(by=time_col)

    if df.empty:
        return round(float(fallback_daily_chg), 2)

    try:
        if isinstance(start_date, str):
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00")).date()
        elif isinstance(start_date, datetime):
            start_dt = start_date.date()
        else:
            start_dt = None
    except Exception:
        start_dt = None

    try:
        if isinstance(end_date, str):
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00")).date()
        elif isinstance(end_date, datetime):
            end_dt = end_date.date()
        else:
            end_dt = None
    except Exception:
        end_dt = None

    if start_dt and time_col:
        df["dt_only"] = df[time_col].dt.date
        sub_entry = df[df["dt_only"] >= start_dt]
        entry_row = sub_entry.iloc[0] if not sub_entry.empty else df.iloc[0]
        if end_dt:
            sub_exit = df[df["dt_only"] <= end_dt]
            exit_row = sub_exit.iloc[-1] if not sub_exit.empty else df.iloc[-1]
        else:
            exit_row = df.iloc[-1]
    else:
        entry_row = df.iloc[0]
        exit_row = df.iloc[-1]

    entry_close = float(entry_row["close"])
    exit_close = float(exit_row["close"])
    if entry_close <= 0:
        return 0.0

    return round(((exit_close - entry_close) / entry_close) * 100.0, 2)


def replay_signal_path(
    signal: dict,
    ohlc_df: pd.DataFrame,
    vnindex_df: Optional[pd.DataFrame] = None,
    vn30_df: Optional[pd.DataFrame] = None,
) -> dict:
    """Idempotently re-evaluates the price trajectory of a signal from its entry date.

    Implements conservative resolution:
    - If in the same bar both target and stop are breached, STOP_LOSS is recorded first.
    - Tags t_plus_2_locked = True if exit condition is reached before T+2.5 trading days.
    - Returns updated MFE, MAE, T+ milestones, holding-period Alpha, and benchmark returns.
    """
    if ohlc_df is None or ohlc_df.empty:
        return {"status": "NO_DATA", "pnl_pct": 0.0, "alpha_pct": 0.0}

    df = ohlc_df.copy()
    time_col = "time" if "time" in df.columns else ("date" if "date" in df.columns else None)
    if time_col:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        df = df.dropna(subset=[time_col]).sort_values(by=time_col)

    entry_p = float(signal.get("entry_price", 0.0))
    if entry_p <= 0 and not df.empty:
        entry_p = float(df.iloc[0].get("open", df.iloc[0]["close"]))

    target_p = float(signal.get("target_price") or (entry_p * 1.12))
    stop_p = float(signal.get("stop_loss") or (entry_p * 0.93))

    start_date = signal.get("created_at") or signal.get("entry_date")
    if start_date and time_col:
        try:
            if isinstance(start_date, str):
                s_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00")).date()
            else:
                s_dt = start_date.date()
            df = df[df[time_col].dt.date >= s_dt]
        except Exception:
            pass

    if df.empty:
        return {"status": "EMPTY_RANGE", "pnl_pct": 0.0, "alpha_pct": 0.0}

    mfe = entry_p
    mae = entry_p
    status = "OPEN"
    exit_p = None
    exit_idx = None
    exit_date = None
    t_marks: dict = {}

    is_after_noon = False
    if start_date:
        try:
            if isinstance(start_date, str):
                s_dt_full = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                is_after_noon = s_dt_full.time() >= time(11, 30)
            elif isinstance(start_date, datetime):
                is_after_noon = start_date.time() >= time(11, 30)
        except Exception:
            pass

    for idx, (_, row) in enumerate(df.iterrows()):
        high_p = float(row.get("high", row["close"]))
        low_p = float(row.get("low", row["close"]))
        close_p = float(row["close"])
        row_time = row[time_col] if time_col else None

        # TASK-0055: Tín hiệu phát sau 11:30 thì ở ngày T=0 (idx=0) chỉ dùng closing price
        if idx == 0 and is_after_noon:
            high_p = close_p
            low_p = close_p

        mfe = round(max(mfe, high_p), 2)
        mae = round(min(mae, low_p), 2)

        if idx == 1:
            t_marks["price_t1"] = close_p
        elif idx == 3:
            t_marks["price_t3"] = close_p
        elif idx == 5:
            t_marks["price_t5"] = close_p
        elif idx == 10:
            t_marks["price_t10"] = close_p
        elif idx == 20:
            t_marks["price_t20"] = close_p
        elif idx == 60:
            t_marks["price_t60"] = close_p

        # Conservative Rule (7.0b): If BOTH stop and target are breached on same bar, STOP first
        if low_p <= stop_p:
            status = "STOP_LOSS"
            exit_p = stop_p
            exit_idx = idx
            exit_date = str(row_time) if row_time else None
            break
        elif high_p >= target_p:
            status = "TARGET_HIT"
            exit_p = target_p
            exit_idx = idx
            exit_date = str(row_time) if row_time else None
            break
        elif idx >= 60:
            status = "EXPIRED"
            exit_p = close_p
            exit_idx = idx
            exit_date = str(row_time) if row_time else None
            break

    if status == "OPEN":
        exit_p = float(df.iloc[-1]["close"])
        exit_date = str(df.iloc[-1][time_col]) if time_col else None

    # T+2.5 settlement lock check: exit before trading bar 2 is locked
    t_plus_2_locked = bool(exit_idx is not None and exit_idx < 2)

    pnl_pct = round(((exit_p - entry_p) / entry_p) * 100.0, 2) if entry_p > 0 else 0.0

    # Calculate holding period benchmarks
    vnindex_ret = calculate_holding_period_benchmark_return(
        "VNINDEX", start_date=start_date, end_date=exit_date, benchmark_df=vnindex_df
    )
    vn30_ret = calculate_holding_period_benchmark_return(
        "VN30", start_date=start_date, end_date=exit_date, benchmark_df=vn30_df
    )
    alpha_pct = round(pnl_pct - vnindex_ret, 2)

    return {
        "status": status,
        "entry_price": entry_p,
        "exit_price": exit_p,
        "exit_date": exit_date,
        "exit_bar": exit_idx,
        "max_favorable_price": mfe,
        "max_adverse_price": mae,
        "actual_pnl_pct": pnl_pct,
        "vnindex_pct_same_period": vnindex_ret,
        "vn30_pct_same_period": vn30_ret,
        "pnl_vs_vnindex": alpha_pct,
        "t_plus_2_locked": t_plus_2_locked,
        **t_marks,
    }


def update_daily_tracking() -> dict:
    """Post-market audit process (runs at 15:15 VN time).

    Steps:
    1. Data Freshness Check — verify official close prices are available
    2. Update MFE (max favorable), MAE (max adverse), and T+1/5/20/60 marks
    3. Transition signals to TARGET_HIT or STOP_LOSS when thresholds are crossed
    4. Calculate Alpha vs VN-Index and attribute losses (market vs AI)

    Returns:
        Dict with 'status', 'updated_count', 'resolved_count'.
    """
    client = get_supabase_client()
    if not client:
        return {"status": "NO_CLIENT", "message": "Supabase chưa được cấu hình"}

    from data_engine import fetch_stock_technical

    # 1. DATA FRESHNESS CHECK
    vnindex_tech = fetch_stock_technical("VNINDEX")
    if not vnindex_tech or not vnindex_tech.get("current_price"):
        logging.warning("⚠️ DATA FRESHNESS CHECK FAILED: Market close data not finalized. Tagged as PENDING_DATA.")
        return {"status": "PENDING_DATA", "message": "Market data not ready", "updated": 0}

    vnindex_chg = vnindex_tech.get("change_pct", 0.0)

    open_signals = fetch_open_signals()
    if not open_signals:
        logging.info("ℹ️ No signals in OPEN status require auditing.")
        return {"status": "SUCCESS", "message": "No open signals", "updated": 0}

    updated_count = 0
    now_utc = datetime.now(timezone.utc).isoformat()
    now_vn = datetime.now(VN_TZ)

    for item in open_signals:
        sig_id = item["id"]
        sym = item["symbol"]
        entry_p = float(item["entry_price"])
        target_p = float(item.get("target_price") or (entry_p * 1.12))
        stop_p = float(item.get("stop_loss") or (entry_p * 0.93))
        tracking = item.get("tracking") or {}
        tracking_id = tracking.get("id")

        tech = fetch_stock_technical(sym)
        if not tech or not tech.get("current_price"):
            continue

        curr_p = float(tech["current_price"])
        high_p = float(tech.get("high", curr_p))
        low_p = float(tech.get("low", curr_p))

        # Tính số ngày giao dịch trôi qua (TASK-0055)
        created_dt = None
        try:
            created_dt = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).astimezone(VN_TZ)
            days_elapsed = count_trading_days(created_dt.date(), now_vn.date())
        except Exception:
            days_elapsed = 1

        # TASK-0055: Time-Aware Audit Fill (Signal sau 11:30 chỉ khớp theo giá đóng cửa ở phiên T=0)
        if days_elapsed == 0 and created_dt and created_dt.time() >= time(11, 30):
            high_p = curr_p
            low_p = curr_p

        # Cập nhật MFE (Đỉnh cao nhất) và MAE (Đáy thấp nhất)
        prev_mfe = float(tracking.get("max_favorable_price") or entry_p)
        prev_mae = float(tracking.get("max_adverse_price") or entry_p)
        new_mfe = round(max(prev_mfe, high_p), 2)
        new_mae = round(min(prev_mae, low_p), 2)

        # Cập nhật các mốc T+
        tracking_updates = {
            "updated_at": now_utc,
            "max_favorable_price": new_mfe,
            "max_adverse_price": new_mae,
        }

        if days_elapsed >= 1 and tracking.get("price_t1") is None:
            tracking_updates["price_t1"] = curr_p
        if days_elapsed >= 5 and tracking.get("price_t5") is None:
            tracking_updates["price_t5"] = curr_p
        if days_elapsed >= 20 and tracking.get("price_t20") is None:
            tracking_updates["price_t20"] = curr_p
        if days_elapsed >= 60 and tracking.get("price_t60") is None:
            tracking_updates["price_t60"] = curr_p

        # 2. KIỂM TRA ĐIỀU KIỆN ĐÓNG LỆNH (CONSERVATIVE STOP FIRST & HOLDING ALPHA)
        new_status = "OPEN"
        exit_price = None
        loss_attribution = None
        pnl_pct = 0.0

        # Ưu tiên 1: Chạm Cắt Lỗ (STOP_LOSS) - Quy tắc bảo thủ 7.0b
        if low_p <= stop_p:
            new_status = "STOP_LOSS"
            exit_price = stop_p
            pnl_pct = round(((stop_p - entry_p) / entry_p) * 100, 2)
        elif high_p >= target_p:
            new_status = "TARGET_HIT"
            exit_price = target_p
            pnl_pct = round(((target_p - entry_p) / entry_p) * 100, 2)
        elif days_elapsed >= 60:
            new_status = "EXPIRED"
            exit_price = curr_p
            pnl_pct = round(((curr_p - entry_p) / entry_p) * 100, 2)
            loss_attribution = "TIME_EXPIRED"

        if new_status != "OPEN":
            # Task 7.0a: Tính Alpha chuẩn xác theo chu kỳ nắm giữ thực tế
            vnindex_holding = calculate_holding_period_benchmark_return(
                "VNINDEX", start_date=item.get("created_at"), end_date=now_utc, fallback_daily_chg=vnindex_chg
            )
            vn30_holding = calculate_holding_period_benchmark_return(
                "VN30", start_date=item.get("created_at"), end_date=now_utc, fallback_daily_chg=vnindex_chg
            )
            alpha_pct = round(pnl_pct - vnindex_holding, 2)
            t_plus_2_locked = bool(days_elapsed < 2.5)

            if new_status == "STOP_LOSS":
                if vnindex_holding <= -2.0:
                    loss_attribution = "MARKET_SYSTEMIC_CRASH"
                elif item.get("f_score", 6) <= 4:
                    loss_attribution = "FUNDAMENTAL_DETERIORATION"
                elif item.get("p_bull", 0.3) >= 0.65:
                    loss_attribution = "AI_OVERCONFIDENCE"
                else:
                    loss_attribution = "TECHNICAL_FALSE_BREAKOUT"

            tracking_updates.update(
                {
                    "status": new_status,
                    "exit_price": exit_price,
                    "exit_date": now_utc,
                    "actual_pnl_pct": pnl_pct,
                    "pnl_vs_vnindex": alpha_pct,
                    "vnindex_pct_same_period": vnindex_holding,
                    "vn30_pct_same_period": vn30_holding,
                    "t_plus_2_locked": t_plus_2_locked,
                    "loss_attribution": loss_attribution,
                }
            )
            logging.info(
                f"🎯 POSITION {sym} CLOSED: Status = {new_status} | P/L = {pnl_pct:+.2f}% | Alpha = {alpha_pct:+.2f}%"
            )

            # Cập nhật thông tin Exit cho signal_lifecycle (Phase 3)
            try:
                r_multiple = None
                if item.get("stop_loss") and item.get("entry_price"):
                    risk_pct = abs(item["entry_price"] - item["stop_loss"]) / item["entry_price"] * 100
                    r_multiple = round(pnl_pct / risk_pct, 2) if risk_pct > 0 else 0.0

                update_signal_lifecycle_exit(
                    str(sig_id),
                    {
                        "status": new_status,
                        "exit_price": float(exit_price),
                        "pnl_pct": float(pnl_pct),
                        "r_multiple": float(r_multiple) if r_multiple is not None else None,
                        "loss_attribution": loss_attribution,
                    },
                )
            except Exception:
                logging.exception("Lỗi khi update_signal_lifecycle_exit")

        # Cập nhật Supabase
        if tracking_id:
            client.table("signal_tracking").update(tracking_updates).eq("id", tracking_id).execute()
        else:
            tracking_updates["signal_id"] = sig_id
            client.table("signal_tracking").insert(tracking_updates).execute()

        updated_count += 1

    logging.info(f"✅ POST-MARKET AUDIT COMPLETE: Updated {updated_count} signals.")
    return {"status": "SUCCESS", "message": f"Successfully updated {updated_count} signals", "updated": updated_count}


def get_signal_audit_metrics() -> dict:
    """Query and calculate signal audit metrics for Alpha Tracker (Hit Rate, Profit Factor, Alpha vs VN-Index, Loss Attribution)."""
    client = get_supabase_client()
    empty_res = {
        "total_signals": 0,
        "open_signals": 0,
        "resolved_signals": 0,
        "win_rate": 0.0,
        "avg_return": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "profit_factor": 0.0,
        "alpha_vs_vnindex": 0.0,
        "signals_df": pd.DataFrame(),
        "loss_reasons": {},
    }
    if not client:
        return empty_res

    try:
        res = client.table("signals").select("*, signal_tracking(*)").order("created_at", desc=True).execute()
        rows = res.data or []
        if not rows:
            return empty_res

        flattened = []
        for r in rows:
            trackings = r.get("signal_tracking") or [{}]
            t = trackings[0] if trackings else {}

            flattened.append(
                {
                    "ID": r.get("id"),
                    "Mã": r.get("symbol"),
                    "Ngày phát": str(r.get("created_at", ""))[:10],
                    "Hành động": r.get("action"),
                    "Giá vào": r.get("entry_price"),
                    "Giá Target": r.get("target_price"),
                    "Stop-Loss": r.get("stop_loss"),
                    "MoS (%)": r.get("mos_pct"),
                    "F-Score": r.get("f_score"),
                    "Z-Score": r.get("z_score"),
                    "Kelly f*": r.get("kelly_f"),
                    "P_Bull": r.get("p_bull"),
                    "P_Base": r.get("p_base"),
                    "P_Bear": r.get("p_bear"),
                    "Trạng thái": t.get("status", "OPEN"),
                    "Giá đóng": t.get("exit_price"),
                    "PnL Thực tế (%)": t.get("actual_pnl_pct"),
                    "Alpha vs VNI (%)": t.get("pnl_vs_vnindex"),
                    "Đỉnh MFE": t.get("max_favorable_price"),
                    "Đáy MAE": t.get("max_adverse_price"),
                    "Giá T+1": t.get("price_t1"),
                    "Giá T+5": t.get("price_t5"),
                    "Giá T+20": t.get("price_t20"),
                    "Nguyên nhân nếu lỗ": t.get("loss_attribution", ""),
                    "AI Thesis": r.get("ai_thesis", ""),
                    "Model": r.get("model_version", "gemini-flash"),
                    "Input Snapshot": r.get("input_snapshot", {}),
                }
            )

        df = pd.DataFrame(flattened)

        total_signals = len(df)
        open_signals = len(df[df["Trạng thái"] == "OPEN"])
        resolved_df = df[df["Trạng thái"].isin(["TARGET_HIT", "STOP_LOSS", "TRAILING_EXIT", "EXPIRED"])]
        resolved_count = len(resolved_df)

        if resolved_count > 0:
            win_df = resolved_df[resolved_df["PnL Thực tế (%)"] > 0]
            loss_df = resolved_df[resolved_df["PnL Thực tế (%)"] <= 0]

            win_rate = round((len(win_df) / resolved_count) * 100, 1)
            avg_return = round(resolved_df["PnL Thực tế (%)"].mean(), 2)
            avg_win = round(win_df["PnL Thực tế (%)"].mean(), 2) if not win_df.empty else 0.0
            avg_loss = round(loss_df["PnL Thực tế (%)"].mean(), 2) if not loss_df.empty else 0.0

            sum_win = win_df["PnL Thực tế (%)"].sum() if not win_df.empty else 0.0
            sum_loss = abs(loss_df["PnL Thực tế (%)"].sum()) if not loss_df.empty else 0.0
            profit_factor = round(sum_win / sum_loss, 2) if sum_loss > 0 else (99.0 if sum_win > 0 else 1.0)

            alpha_mean = round(resolved_df["Alpha vs VNI (%)"].mean(), 2) if "Alpha vs VNI (%)" in resolved_df else 0.0
            loss_reasons = loss_df["Nguyên nhân nếu lỗ"].value_counts().to_dict() if not loss_df.empty else {}
        else:
            win_rate = 0.0
            avg_return = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            profit_factor = 0.0
            alpha_mean = 0.0
            loss_reasons = {}

        return {
            "total_signals": total_signals,
            "open_signals": open_signals,
            "resolved_signals": resolved_count,
            "win_rate": win_rate,
            "avg_return": avg_return,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "alpha_vs_vnindex": alpha_mean,
            "signals_df": df,
            "loss_reasons": loss_reasons,
        }
    except Exception as e:
        logging.exception("Lỗi tính toán chỉ số kiểm toán")
        return empty_res


def save_signal_lifecycle(signal_data: dict) -> dict | None:
    """Lưu bản ghi vòng đời tín hiệu (Signal Lifecycle) bất biến vào Supabase (Phase 1a).

    - Đóng băng toàn bộ các yếu tố định lượng và AI metadata tại thời điểm phát tín hiệu.
    - initial_stop_price được lưu cố định để tính R-Multiple chuẩn xác, không bị ảnh hưởng bởi trailing stop.
    """
    client = get_supabase_client()
    if not client:
        return None

    symbol = str(signal_data.get("symbol", "")).upper().strip()
    if not symbol:
        return None

    signal_id = signal_data.get("signal_id", f"{symbol}_{datetime.now(VN_TZ).strftime('%Y%m%d_%H%M%S')}")

    # TASK-0054: Adapter maps target_price & stop_loss và điền đầy đủ 5 trường calibration
    target_val = float(signal_data.get("target_price") or signal_data.get("initial_target_price", 0.0) or 0.0)
    stop_val = float(
        signal_data.get("stop_loss_price")
        or signal_data.get("initial_stop_price")
        or signal_data.get("stop_loss", 0.0)
        or 0.0
    )
    entry_val = float(signal_data.get("entry_price", 0.0) or 0.0)
    f_score_val = int(signal_data.get("f_score", 0) or 0)
    mos_pct_val = float(signal_data.get("mos_pct", 0.0) or 0.0)

    row = {
        "signal_id": signal_id,
        "symbol": symbol,
        "entry_price": entry_val,
        "entry_regime": signal_data.get("entry_regime", "UNKNOWN"),
        "entry_sector": signal_data.get("entry_sector", "UNKNOWN"),
        "f_score": f_score_val,
        "z_score": float(signal_data.get("z_score", 0.0) or 0.0),
        "mos_pct": mos_pct_val,
        "kelly_f": float(signal_data.get("kelly_f", 0.0) or 0.0),
        "rsi14": float(signal_data.get("rsi14", 0.0) or 0.0),
        "conviction_score": float(signal_data.get("conviction_score", 0.0) or 0.0),
        "adv20_billion": float(signal_data.get("adv20_billion", 0.0) or 0.0),
        "ai_confidence": float(signal_data.get("ai_confidence", 0.0) or 0.0),
        "ai_recommendation": signal_data.get("ai_recommendation", ""),
        "prompt_version": signal_data.get("prompt_version", "quant_2pass_v3.2"),
        "model_version": signal_data.get("model_version", "gemini-2.5-flash"),
        "initial_stop_price": stop_val,
        "stop_loss_price": stop_val,
        "target_price": target_val,
        "initial_target_price": target_val,
        "arm": signal_data.get("arm", "QUANT_AI"),
        "status": "OPEN",
    }

    try:
        res = client.table("signal_lifecycle").insert(row).execute()
        if res.data:
            logging.info("Đã lưu signal lifecycle cho %s (ID: %s)", symbol, signal_id)
            return res.data[0]
        return None
    except Exception:
        logging.exception("Lỗi khi lưu signal lifecycle")
        return None


def update_signal_lifecycle_exit(signal_id: str, exit_data: dict) -> dict | None:
    """Cập nhật dữ liệu đóng vị thế và các chỉ số Path Metrics cho signal lifecycle."""
    client = get_supabase_client()
    if not client:
        return None

    try:
        res = client.table("signal_lifecycle").update(exit_data).eq("signal_id", signal_id).execute()
        return res.data[0] if res.data else None
    except Exception:
        logging.exception("Lỗi khi cập nhật exit cho signal lifecycle")
        return None


def save_decision_record(record: dict) -> str | None:
    """Save an immutable decision record (BUY, WATCH, REJECT) to Supabase decision_records."""
    client = get_supabase_client()
    if not client:
        return None

    symbol = record.get("symbol", "").upper().strip()
    session = record.get("session", "NOON")
    decision = record.get("decision", "REJECT").upper()
    now_str = datetime.now(VN_TZ).strftime("%Y%m%d_%H%M%S")
    decision_id = record.get("decision_id") or f"DEC_{symbol}_{now_str}"

    # Chốt chặn cách ly môi trường test/dry-run không cho ghi bẩn vào Supabase
    if os.environ.get("ENV") in ("testing", "test") or os.environ.get("DRY_RUN", "").lower() in ("true", "1"):
        logging.info("Testing/Dry-run mode: skipped writing decision_record for %s", symbol)
        return decision_id

    # Chuẩn hóa trường giá trong facts
    facts = dict(record.get("facts") or {})
    m_price = facts.get("market_price") or facts.get("price") or facts.get("snapshot_price") or 0.0
    if m_price:
        facts.setdefault("market_price", m_price)
        facts.setdefault("snapshot_price", m_price)
        facts.setdefault("price", m_price)

    # Chuẩn hóa trường audit hash trong opinions
    opinions = dict(record.get("opinions") or {})
    for hash_key in ("prompt_hash", "input_hash", "code_version"):
        if record.get(hash_key) and hash_key not in opinions:
            opinions[hash_key] = record.get(hash_key)

    # Chuẩn hóa trường counterfactual
    counterfactual = dict(record.get("counterfactual") or {})
    if record.get("thesis_breaker") and "thesis_breaker" not in counterfactual:
        counterfactual["thesis_breaker"] = record.get("thesis_breaker")

    row = {
        "decision_id": decision_id,
        "symbol": symbol,
        "session": session,
        "decision": decision,
        "primary_rejection_gate": record.get("primary_rejection_gate"),
        "rejection_reasons": record.get("rejection_reasons", []),
        "facts": facts,
        "inferences": record.get("inferences", {}),
        "opinions": opinions,
        "counterfactual": counterfactual,
        # Phiên bản 6.3 - Analyst Context Tracking (Migration 0004)
        "analyst_context_used": record.get("analyst_context_used", False),
        "regime_conflict": record.get("regime_conflict", False),
        "context_source_file": record.get("context_source_file"),
        "context_date": record.get("context_date"),
        # Phiên bản 6.4 - Audit Fields (Migration 0005)
        "prompt_version": record.get("prompt_version"),
        "model_version": record.get("model_version"),
        "raw_response": record.get("raw_response"),
    }

    try:
        res = client.table("decision_records").insert(row).execute()
        if res.data:
            logging.info("Saved decision record %s for %s (%s)", decision_id, symbol, decision)
            return decision_id
        return None
    except Exception:
        logging.exception("Failed to insert decision record for %s", symbol)
        return None


def get_decision_records(filters: Optional[dict] = None, limit: int = 50) -> list[dict]:
    """Query decision records with optional filters."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        query = client.table("decision_records").select("*").order("created_at", desc=True).limit(limit)
        if filters:
            if filters.get("symbol"):
                query = query.eq("symbol", filters["symbol"].upper().strip())
            if filters.get("decision"):
                query = query.eq("decision", filters["decision"].upper())
            if filters.get("session"):
                query = query.eq("session", filters["session"].upper())
            if filters.get("primary_rejection_gate"):
                query = query.eq("primary_rejection_gate", filters["primary_rejection_gate"])
        res = query.execute()
        return res.data or []
    except Exception:
        logging.exception("Error querying decision records")
        return []


def get_scan_block_distribution(session_id: str, limit: int = 500) -> dict:
    """Aggregate rejection reasons and data completeness ratio for a scan session (TASK-0073).
    
    Returns:
        dict with total_scanned, total_blocked, block_rate, gate_distribution,
        data_completeness_ratio, and alarm_100pct_same_gate.
    """
    records = get_decision_records(filters={"session": session_id}, limit=limit)
    total = len(records)
    if total == 0:
        return {
            "total_scanned": 0,
            "total_blocked": 0,
            "block_rate": 0.0,
            "gate_distribution": {},
            "data_completeness_ratio": 1.0,
            "alarm_100pct_same_gate": False,
        }

    blocked = [r for r in records if r.get("decision") in ("REJECT", "BLOCKED")]
    gate_counts = Counter(r.get("primary_rejection_gate") or "UNKNOWN" for r in blocked)
    completeness = sum(1 for r in records if bool(r.get("facts"))) / total

    is_alarm = len(blocked) == total and len(gate_counts) == 1 and total >= 3

    return {
        "total_scanned": total,
        "total_blocked": len(blocked),
        "block_rate": round(len(blocked) / total, 3),
        "gate_distribution": dict(gate_counts),
        "data_completeness_ratio": round(completeness, 3),
        "alarm_100pct_same_gate": is_alarm,
    }


def update_decision_forward_returns(decision_id: str, returns_data: dict) -> bool:
    """Save or update forward returns for a decision record."""
    client = get_supabase_client()
    if not client:
        return False

    row = {
        "decision_id": decision_id,
        "symbol": returns_data.get("symbol", ""),
        "snapshot_price": float(returns_data.get("snapshot_price", 0.0)),
        "t1_return_pct": returns_data.get("t1_return_pct"),
        "t3_return_pct": returns_data.get("t3_return_pct"),
        "t5_return_pct": returns_data.get("t5_return_pct"),
        "t10_return_pct": returns_data.get("t10_return_pct"),
        "t20_return_pct": returns_data.get("t20_return_pct"),
        "vnindex_t5_pct": returns_data.get("vnindex_t5_pct"),
        "vnindex_t20_pct": returns_data.get("vnindex_t20_pct"),
    }

    try:
        res = client.table("decision_forward_returns").upsert(row, on_conflict="decision_id").execute()
        return bool(res.data)
    except Exception:
        logging.exception("Error saving forward returns for %s", decision_id)
        return False


def get_decision_forward_returns(decision_ids: Optional[list[str]] = None, limit: int = 500) -> list[dict]:
    """Query decision forward returns records."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        query = client.table("decision_forward_returns").select("*").limit(limit)
        if decision_ids:
            query = query.in_("decision_id", decision_ids)
        res = query.execute()
        return res.data or []
    except Exception:
        logging.exception("Error querying decision forward returns")
        return []


def check_evidence_kill_switch(lookback_trades: int = 20) -> dict:
    """Evaluate recent closed trades to verify if Expectancy R < 0.

    If Expectancy is negative, triggers the Kill Switch: reduces position size by 50%
    and issues an alert.
    """
    client = get_supabase_client()
    default_res = {
        "is_triggered": False,
        "expectancy_r": 0.0,
        "sample_size": 0,
        "size_reduction_pct": 0.0,
        "reason": "OK",
    }
    if not client:
        return default_res

    try:
        res = (
            client.table("signal_lifecycle")
            .select("r_multiple, pnl_pct, status")
            .in_("status", ["TARGET_HIT", "STOP_LOSS", "EXPIRED", "CLOSED"])
            .order("created_at", desc=True)
            .limit(lookback_trades)
            .execute()
        )
        trades = res.data or []
        if len(trades) < 5:
            default_res["reason"] = f"Insufficient sample size ({len(trades)} < 5)"
            return default_res

        r_vals = [float(t["r_multiple"]) for t in trades if t.get("r_multiple") is not None]
        if not r_vals:
            return default_res

        avg_r = sum(r_vals) / len(r_vals)
        if avg_r < 0.0:
            return {
                "is_triggered": True,
                "expectancy_r": round(avg_r, 3),
                "sample_size": len(r_vals),
                "size_reduction_pct": 50.0,
                "reason": f"Negative Expectancy ({avg_r:+.2f}R across last {len(r_vals)} trades)",
            }

        return {
            "is_triggered": False,
            "expectancy_r": round(avg_r, 3),
            "sample_size": len(r_vals),
            "size_reduction_pct": 0.0,
            "reason": "Expectancy positive",
        }
    except Exception:
        logging.exception("Error evaluating evidence kill switch")
        return default_res
