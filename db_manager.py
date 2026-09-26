import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from supabase import Client, create_client

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_supabase: Client = None


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
    input_snapshot: dict = None
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
                **(input_snapshot or {})
            }
        }

        res = client.table("signals").insert(data).execute()
        if not res.data:
            return None
        signal_id = res.data[0]["id"]

        # Khởi tạo bản ghi tracking tương ứng ở trạng thái OPEN
        client.table("signal_tracking").insert({
            "signal_id": signal_id,
            "status": "OPEN",
            "max_favorable_price": mkt_price,
            "max_adverse_price": mkt_price
        }).execute()

        logging.info(f"✅ ĐÃ LƯU SNAPSHOT TÍN HIỆU {symbol} (ID: {signal_id}) VÀO SUPABASE THÀNH CÔNG!")
        return signal_id
    except Exception as e:
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
        for row in (res.data or []):
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
        from datetime import timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        res = (
            client.table("signals")
            .select("id, symbol, created_at, action")
            .eq("symbol", symbol.upper().strip())
            .gte("created_at", cutoff)
            .ilike("action", "%BUY%")
            .execute()
        )
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        logging.debug(f"Error checking Supabase signal cooldown for {symbol}: {e}")
        return False


def get_open_signals_count() -> int:
    """Count active OPEN positions in Supabase signal_tracking table."""
    client = get_supabase_client()
    if not client:
        return 0
    try:
        res = (
            client.table("signal_tracking")
            .select("id", count="exact")
            .eq("status", "OPEN")
            .execute()
        )
        if hasattr(res, "count") and res.count is not None:
            return res.count
        return len(res.data or [])
    except Exception as e:
        logging.debug(f"Error counting open signals: {e}")
        return 0


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

        # Tính số ngày giao dịch trôi qua
        try:
            created_dt = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).astimezone(VN_TZ)
            days_elapsed = max(1, (now_vn.date() - created_dt.date()).days)
        except Exception:
            days_elapsed = 1

        # Cập nhật MFE (Đỉnh cao nhất) và MAE (Đáy thấp nhất)
        prev_mfe = float(tracking.get("max_favorable_price") or entry_p)
        prev_mae = float(tracking.get("max_adverse_price") or entry_p)
        new_mfe = round(max(prev_mfe, high_p), 2)
        new_mae = round(min(prev_mae, low_p), 2)

        # Cập nhật các mốc T+
        tracking_updates = {
            "updated_at": now_utc,
            "max_favorable_price": new_mfe,
            "max_adverse_price": new_mae
        }

        if days_elapsed >= 1 and tracking.get("price_t1") is None:
            tracking_updates["price_t1"] = curr_p
        if days_elapsed >= 5 and tracking.get("price_t5") is None:
            tracking_updates["price_t5"] = curr_p
        if days_elapsed >= 20 and tracking.get("price_t20") is None:
            tracking_updates["price_t20"] = curr_p
        if days_elapsed >= 60 and tracking.get("price_t60") is None:
            tracking_updates["price_t60"] = curr_p

        # 2. KIỂM TRA ĐIỀU KIỆN ĐÓNG LỆNH (STATE TRANSITION)
        new_status = "OPEN"
        exit_price = None
        loss_attribution = None

        # Ưu tiên 1: Chạm Chốt Lời (TARGET_HIT)
        if high_p >= target_p:
            new_status = "TARGET_HIT"
            exit_price = target_p
            pnl_pct = round(((target_p - entry_p) / entry_p) * 100, 2)
            alpha_pct = round(pnl_pct - vnindex_chg, 2)

        # Ưu tiên 2: Chạm Cắt Lỗ (STOP_LOSS)
        elif low_p <= stop_p:
            new_status = "STOP_LOSS"
            exit_price = stop_p
            pnl_pct = round(((stop_p - entry_p) / entry_p) * 100, 2)
            alpha_pct = round(pnl_pct - vnindex_chg, 2)

            # Bóc tách nguyên nhân thất bại (Loss Attribution)
            if vnindex_chg <= -2.0:
                loss_attribution = "MARKET_SYSTEMIC_CRASH"
            elif item.get("f_score", 6) <= 4:
                loss_attribution = "FUNDAMENTAL_DETERIORATION"
            elif item.get("p_bull", 0.3) >= 0.65:
                loss_attribution = "AI_OVERCONFIDENCE"
            else:
                loss_attribution = "TECHNICAL_FALSE_BREAKOUT"

        # Ưu tiên 3: Hết hạn chu kỳ 60 ngày
        elif days_elapsed >= 60:
            new_status = "EXPIRED"
            exit_price = curr_p
            pnl_pct = round(((curr_p - entry_p) / entry_p) * 100, 2)
            alpha_pct = round(pnl_pct - vnindex_chg, 2)
            loss_attribution = "TIME_EXPIRED"

        if new_status != "OPEN":
            tracking_updates.update({
                "status": new_status,
                "exit_price": exit_price,
                "exit_date": now_utc,
                "actual_pnl_pct": pnl_pct,
                "pnl_vs_vnindex": alpha_pct,
                "loss_attribution": loss_attribution
            })
            logging.info(f"🎯 POSITION {sym} CLOSED: Status = {new_status} | P/L = {pnl_pct:+.2f}% | Alpha = {alpha_pct:+.2f}%")

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
        "loss_reasons": {}
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

            flattened.append({
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
                "Input Snapshot": r.get("input_snapshot", {})
            })

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
            "loss_reasons": loss_reasons
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

    signal_id = signal_data.get(
        "signal_id",
        f"{symbol}_{datetime.now(VN_TZ).strftime('%Y%m%d_%H%M%S')}"
    )

    row = {
        "signal_id": signal_id,
        "symbol": symbol,
        "entry_price": float(signal_data.get("entry_price", 0.0)),
        "entry_regime": signal_data.get("entry_regime", "UNKNOWN"),
        "entry_sector": signal_data.get("entry_sector", "UNKNOWN"),
        "f_score": int(signal_data.get("f_score", 0)),
        "z_score": float(signal_data.get("z_score", 0.0)),
        "mos_pct": float(signal_data.get("mos_pct", 0.0)),
        "kelly_f": float(signal_data.get("kelly_f", 0.0)),
        "rsi14": float(signal_data.get("rsi14", 0.0)),
        "conviction_score": float(signal_data.get("conviction_score", 0.0)),
        "adv20_billion": float(signal_data.get("adv20_billion", 0.0)),
        "ai_confidence": float(signal_data.get("ai_confidence", 0.0)),
        "ai_recommendation": signal_data.get("ai_recommendation", ""),
        "prompt_version": signal_data.get("prompt_version", "quant_2pass_v3.2"),
        "model_version": signal_data.get("model_version", "gemini-2.5-flash"),
        "initial_stop_price": float(signal_data.get("initial_stop_price", 0.0)),
        "stop_loss_price": float(signal_data.get("stop_loss_price", 0.0)),
        "target_price": float(signal_data.get("target_price", 0.0)),
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

