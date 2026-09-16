import os
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_supabase: Client = None


def get_supabase_client() -> Client:
    """Khởi tạo và trả về Supabase Client an toàn, tự động chuẩn hóa URL."""
    global _supabase
    if _supabase is None:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_KEY", "").strip()

        if not url or not key:
            logging.warning("Chưa cấu hình SUPABASE_URL hoặc SUPABASE_KEY trong .env")
            return None

        # Tự động loại bỏ đuôi /rest/v1 hoặc dấu / thừa
        clean_url = url.split("/rest/v1")[0].rstrip("/")

        try:
            _supabase = create_client(clean_url, key)
        except Exception as e:
            logging.error(f"Lỗi khởi tạo Supabase Client: {e}")
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
    """
    LƯU TRỌN VẸN SNAPSHOT BẤT BIẾN (IMMUTABLE SNAPSHOT) KHI NỔ TÍN HIỆU:
    Lưu đầy đủ: signal_id, signal_timestamp, entry_price, market_price_at_signal,
    Data Gate, F-Score, Z-Score, MoS, Kelly, EV, Probability và input_snapshot nguyên bản.
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
        logging.error(f"Lỗi khi lưu tín hiệu vào Supabase: {e}")
        return None


def fetch_open_signals() -> list:
    """Lấy danh sách các tín hiệu đang OPEN để tiến trình kiểm toán theo dõi."""
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
        logging.error(f"Lỗi truy vấn Open Signals: {e}")
        return []


def update_daily_tracking() -> dict:
    """
    TIẾN TRÌNH KIỂM TOÁN TÍN HIỆU SAU PHIÊN (15:15 POST-MARKET AUDIT):
    1. Data Freshness Check: Kiểm tra dữ liệu đóng cửa chính thức của sàn. Nếu chưa ổn định -> PENDING_DATA.
    2. Cập nhật MFE (Đỉnh cao nhất), MAE (Đáy sâu nhất), và các mốc T+1, T+5, T+20, T+60.
    3. Đánh giá Hit Target / Stop Loss dứt khoát -> Chuyển trạng thái TARGET_HIT / STOP_LOSS.
    4. Tính toán Alpha so với VN-Index và gắn nhãn nguyên nhân nếu thua (Loss Attribution).
    """
    client = get_supabase_client()
    if not client:
        return {"status": "NO_CLIENT", "message": "Supabase chưa được cấu hình"}

    from data_engine import fetch_stock_technical

    # 1. DATA FRESHNESS CHECK
    vnindex_tech = fetch_stock_technical("VNINDEX")
    if not vnindex_tech or not vnindex_tech.get("current_price"):
        logging.warning("⚠️ DATA FRESHNESS CHECK FAILED: Dữ liệu thị trường chưa chốt phiên. Đánh dấu PENDING_DATA.")
        return {"status": "PENDING_DATA", "message": "Dữ liệu thị trường chưa sẵn sàng", "updated": 0}

    vnindex_chg = vnindex_tech.get("change_pct", 0.0)

    open_signals = fetch_open_signals()
    if not open_signals:
        logging.info("ℹ️ Không có tín hiệu nào đang ở trạng thái OPEN cần kiểm toán.")
        return {"status": "SUCCESS", "message": "Không có tín hiệu OPEN", "updated": 0}

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
            logging.info(f"🎯 VỊ THẾ {sym} ĐÃ ĐÓNG: Trạng thái = {new_status} | P/L = {pnl_pct:+.2f}% | Alpha = {alpha_pct:+.2f}%")

        # Cập nhật Supabase
        if tracking_id:
            client.table("signal_tracking").update(tracking_updates).eq("id", tracking_id).execute()
        else:
            tracking_updates["signal_id"] = sig_id
            client.table("signal_tracking").insert(tracking_updates).execute()

        updated_count += 1

    logging.info(f"✅ HOÀN TẤT KIỂM TOÁN SAU PHIÊN: Đã cập nhật {updated_count} tín hiệu!")
    return {"status": "SUCCESS", "message": f"Cập nhật thành công {updated_count} tín hiệu", "updated": updated_count}


def get_signal_audit_metrics() -> dict:
    """
    TRUY VẤN VÀ TÍNH TOÁN CÁC CHỈ SỐ KIỂM TOÁN HIỆU QUẢ CHO TAB 6 (ALPHA TRACKER):
    Hit Rate, Average Return, Profit Factor, Alpha vs VN-Index, Lịch sử chi tiết & Bóc tách nguyên nhân.
    """
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
        logging.error(f"Lỗi tính toán chỉ số kiểm toán: {e}")
        return empty_res
