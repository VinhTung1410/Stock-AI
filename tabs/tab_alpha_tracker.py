import textwrap
import json
import streamlit as st
import pandas as pd
from db_manager import get_signal_audit_metrics, update_daily_tracking, get_supabase_client


def _safe_pct(val, default="Đang chạy (N/A)"):
    if val is not None and pd.notnull(val):
        try:
            return f"{float(val):+.2f}%"
        except (ValueError, TypeError):
            pass
    return default


def _safe_num(val, precision=1, prefix="", suffix="", default="N/A"):
    if val is not None and pd.notnull(val):
        try:
            return f"{prefix}{float(val):.{precision}f}{suffix}"
        except (ValueError, TypeError):
            return f"{prefix}{val}{suffix}"
    return default


def render_tab_alpha_tracker():
    """
    🎯 TAB 6: HỆ THỐNG KIỂM TOÁN HIỆU QUẢ TÍN HIỆU (ALPHA TRACKER)
    - Tách biệt rạch ròi: Tab 5 (AI Tư vấn: 'Tôi nghĩ gì?') vs Tab 6 (Kiểm toán: 'Thực tế đúng đến đâu?').
    - Đo lường Hit Rate, Profit Factor, Alpha vs VN-Index, MFE (Lãi cực đại), MAE (Lỗ sâu nhất).
    - Lưu giữ Immutable Snapshot: Xem lại chính xác Bot đã nhìn thấy gì tại thời điểm nổ tín hiệu.
    """
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h2 style="font-size: 24px; font-weight: 800; color: #0f172a; margin-bottom: 4px; display: flex; align-items: center; gap: 8px;">
            🎯 KIỂM TOÁN HIỆU QUẢ TÍN HIỆU (ALPHA TRACKER)
        </h2>
        <p style="font-size: 13.5px; color: #64748b; margin: 0;">
            Hệ thống đối soát độc lập: Đánh giá tỷ lệ thắng thực tế, tỷ số Lãi/Lỗ, và đo lường Alpha vượt trội so với VN-Index sau $T+1, T+5, T+20$.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 1. NÚT ĐIỀU KHIỂN & LÀM MỚI
    col_ctrl1, col_ctrl2 = st.columns([3, 1])
    with col_ctrl2:
        if st.button("⚡ Kích hoạt Kiểm toán Ngay", width="stretch", type="primary"):
            with st.spinner("Đang chạy kiểm toán đối soát sau phiên..."):
                audit_res = update_daily_tracking()
                if audit_res.get("status") == "PENDING_DATA":
                    st.warning("⚠️ Thị trường chưa chốt phiên hoặc dữ liệu chưa sẵn sàng (PENDING_DATA). Đã hoãn đối soát giả định.")
                else:
                    st.success(f"✅ Hoàn tất kiểm toán! Đã cập nhật {audit_res.get('updated', 0)} tín hiệu.")
                    st.rerun()

    # 2. TRUY VẤN DỮ LIỆU TỪ SUPABASE
    metrics = get_signal_audit_metrics()
    total_signals = metrics.get("total_signals", 0)
    resolved_count = metrics.get("resolved_signals", 0)
    open_count = metrics.get("open_signals", 0)
    win_rate = float(metrics.get("win_rate") or 0.0)
    profit_factor = float(metrics.get("profit_factor") or 0.0)
    alpha_vni = float(metrics.get("alpha_vs_vnindex") or 0.0)
    avg_win = float(metrics.get("avg_win") or 0.0)
    avg_loss = float(metrics.get("avg_loss") or 0.0)
    df_signals = metrics.get("signals_df", pd.DataFrame())

    # 3. KHỐI KPI THỐNG KÊ TOÀN DIỆN (HERO CARDS)
    win_color = "#15803d" if win_rate >= 50.0 else ("#b45309" if win_rate > 0 else "#64748b")
    pf_color = "#15803d" if profit_factor >= 1.5 else ("#b45309" if profit_factor > 0 else "#64748b")
    alpha_color = "#15803d" if alpha_vni >= 0 else "#dc2626"
    alpha_sign = "+" if alpha_vni > 0 else ""

    hero_html = textwrap.dedent(f"""
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px;">
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">TỶ LỆ THẮNG (HIT RATE)</div>
            <div style="font-size: 28px; font-weight: 800; color: {win_color}; letter-spacing: -0.5px; line-height: 1.2;">
                {win_rate:.1f}%
            </div>
            <div style="font-size: 11.5px; color: #94a3b8; margin-top: 6px;">{resolved_count} lệnh đã đóng vị thế</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">TỶ SỐ LÃI / LỖ (PROFIT FACTOR)</div>
            <div style="font-size: 28px; font-weight: 800; color: {pf_color}; letter-spacing: -0.5px; line-height: 1.2;">
                {profit_factor:.2f}x
            </div>
            <div style="font-size: 11.5px; color: #94a3b8; margin-top: 6px;">Tổng Lãi / Tổng Lỗ tuyệt đối</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">ALPHA VS VN-INDEX</div>
            <div style="font-size: 28px; font-weight: 800; color: {alpha_color}; letter-spacing: -0.5px; line-height: 1.2;">
                {alpha_sign}{alpha_vni:.2f}%
            </div>
            <div style="font-size: 11.5px; color: #94a3b8; margin-top: 6px;">Lợi nhuận vượt trội thị trường</div>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">QUY MÔ TÍN HIỆU</div>
            <div style="display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px;">
                <div style="font-size: 28px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; line-height: 1.2;">
                    {total_signals} <span style="font-size: 16px; font-weight: 600; color: #64748b;">lệnh</span>
                </div>
                <span style="background: rgba(37,99,235,0.08); color: #2563eb; font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">
                    {open_count} đang chạy
                </span>
            </div>
            <div style="font-size: 11.5px; color: #94a3b8; margin-top: 6px;">Thắng TB: +{avg_win:.1f}% | Lỗ TB: {avg_loss:.1f}%</div>
        </div>
    </div>
    """)
    st.markdown(hero_html, unsafe_allow_html=True)

    if df_signals.empty:
        st.info("💡 **Chưa có dữ liệu kiểm toán trên Supabase.** Khi Trading Bot quét thị trường hoặc bạn bấm phân tích mã trên Tab 5, các khuyến nghị sẽ tự động được ghi nhận và lưu vết tại đây.")
        return

    # 4. BỘ LỌC TÍN HIỆU
    st.markdown("### 📋 Danh Sách Khuyến Nghị & Lịch Sử Đối Soát")
    col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
    with col_f1:
        filter_status = st.selectbox("Lọc theo trạng thái:", ["Tất cả", "Đang mở (OPEN)", "Chốt lời (TARGET_HIT)", "Cắt lỗ (STOP_LOSS)", "Hết hạn (EXPIRED)"])
    with col_f2:
        all_syms = ["Tất cả"] + sorted(df_signals["Mã"].dropna().astype(str).unique().tolist())
        filter_sym = st.selectbox("Lọc theo mã CP:", all_syms)
    with col_f3:
        st.write("")

    filtered_df = df_signals.copy()
    if filter_status == "Đang mở (OPEN)":
        filtered_df = filtered_df[filtered_df["Trạng thái"] == "OPEN"]
    elif filter_status == "Chốt lời (TARGET_HIT)":
        filtered_df = filtered_df[filtered_df["Trạng thái"] == "TARGET_HIT"]
    elif filter_status == "Cắt lỗ (STOP_LOSS)":
        filtered_df = filtered_df[filtered_df["Trạng thái"] == "STOP_LOSS"]
    elif filter_status == "Hết hạn (EXPIRED)":
        filtered_df = filtered_df[filtered_df["Trạng thái"] == "EXPIRED"]

    if filter_sym != "Tất cả":
        filtered_df = filtered_df[filtered_df["Mã"] == filter_sym]

    # Hiển thị bảng tổng hợp
    display_cols = [
        "ID", "Mã", "Ngày phát", "Hành động", "Giá vào", "Giá Target", "Stop-Loss", 
        "Trạng thái", "PnL Thực tế (%)", "Alpha vs VNI (%)", "Đỉnh MFE", "Đáy MAE", 
        "MoS (%)", "F-Score", "Nguyên nhân nếu lỗ"
    ]
    avail_cols = [c for c in display_cols if c in filtered_df.columns]
    st.dataframe(
        filtered_df[avail_cols],
        width="stretch",
        hide_index=True
    )

    if filtered_df.empty:
        st.info("ℹ️ Không tìm thấy khuyến nghị nào phù hợp với bộ lọc hiện tại.")
        return

    # 5. BÓC TÁCH CHI TIẾT SNAPSHOT (INSPECTOR: BOT NHÌN THẤY GÌ LÚC ĐÓ?)
    st.divider()
    st.markdown("### 🔍 Hộp Đen Kiểm Toán: 'Tại thời điểm phát tín hiệu, Bot thực sự nhìn thấy gì?'")
    
    def _format_signal_label(x):
        matches = filtered_df[filtered_df["ID"] == x]
        if matches.empty:
            return f"Signal #{x}"
        row = matches.iloc[0]
        sym = row.get("Mã", "")
        dt = row.get("Ngày phát", "")
        stt = row.get("Trạng thái", "OPEN")
        return f"Signal #{x} - {sym} ({dt} | Trạng thái: {stt})"

    selected_id = st.selectbox(
        "Chọn một tín hiệu để mở hộp đen dữ liệu gốc:",
        options=filtered_df["ID"].tolist(),
        format_func=_format_signal_label
    )

    if selected_id:
        target_rows = df_signals[df_signals["ID"] == selected_id]
        if not target_rows.empty:
            target_row = target_rows.iloc[0]

            # Format an toàn các trường số
            entry_txt = _safe_num(target_row.get('Giá vào'), 1, suffix="k")
            target_txt = _safe_num(target_row.get('Giá Target'), 1, suffix="k")
            sl_txt = _safe_num(target_row.get('Stop-Loss'), 1, suffix="k")

            mos_val = target_row.get('MoS (%)')
            mos_prefix = "+" if (mos_val is not None and pd.notnull(mos_val) and float(mos_val or 0) > 0) else ""
            mos_txt = _safe_num(mos_val, 1, prefix=mos_prefix, suffix="%")

            f_score_val = target_row.get('F-Score')
            f_score_txt = f"{int(float(f_score_val))}/9" if (f_score_val is not None and pd.notnull(f_score_val)) else "N/A"
            z_score_txt = _safe_num(target_row.get('Z-Score'), 2)
            kelly_val = target_row.get('Kelly f*')
            kelly_txt = _safe_num(kelly_val, 2, default=str(kelly_val if kelly_val is not None else "N/A"))

            pnl_txt = _safe_pct(target_row.get('PnL Thực tế (%)'), default="Đang chạy (N/A)")
            alpha_txt = _safe_pct(target_row.get('Alpha vs VNI (%)'), default="Đang chạy (N/A)")
            mfe_txt = _safe_num(target_row.get('Đỉnh MFE'), 1, suffix="k")
            mae_txt = _safe_num(target_row.get('Đáy MAE'), 1, suffix="k")
            t1_txt = _safe_num(target_row.get('Giá T+1'), 1, suffix="k", default="Chưa đạt")
            t5_txt = _safe_num(target_row.get('Giá T+5'), 1, suffix="k", default="Chưa đạt")
            t20_txt = _safe_num(target_row.get('Giá T+20'), 1, suffix="k", default="Chưa đạt")

            col_d1, col_d2, col_d3 = st.columns(3)
            with col_d1:
                st.markdown(f"""
                **1. Thông tin Vị thế & Giá:**
                - Mã: **{target_row.get('Mã', 'N/A')}** ({target_row.get('Hành động', 'N/A')})
                - Ngày phát: `{target_row.get('Ngày phát', 'N/A')}`
                - Giá vào (Entry): `{entry_txt}`
                - Mục tiêu (Target): `{target_txt}`
                - Ngưỡng cắt lỗ: `{sl_txt}`
                """)

            with col_d2:
                st.markdown(f"""
                **2. Chỉ số Định lượng (Quant Core):**
                - Biên an toàn (MoS): **{mos_txt}**
                - Điểm Piotroski F-Score: **{f_score_txt}**
                - Điểm Altman Z-Score: **{z_score_txt}**
                - Phân bổ Kelly f*: `{kelly_txt}`
                """)

            with col_d3:
                st.markdown(f"""
                **3. Kết quả Thực tế sau T+:**
                - Trạng thái hiện tại: **{target_row.get('Trạng thái', 'OPEN')}**
                - P/L Thực tế: **{pnl_txt}**
                - Alpha vs VN-Index: **{alpha_txt}**
                - Đỉnh MFE: `{mfe_txt}` | Đáy MAE: `{mae_txt}`
                - Giá T+1: `{t1_txt}` | T+5: `{t5_txt}` | T+20: `{t20_txt}`
                """)

            # Hiển thị AI Thesis & Input Snapshot
            thesis = target_row.get("AI Thesis") or "Không có ghi chú luận điểm."
            st.markdown(f"**Luận điểm AI (Pass 1 & Pass 2):** {thesis}")
            if target_row.get("Nguyên nhân nếu lỗ"):
                st.error(f"⚠️ **Nguyên nhân thất bại (Loss Attribution):** `{target_row['Nguyên nhân nếu lỗ']}`")

            snapshot = target_row.get("Input Snapshot")
            if snapshot:
                with st.expander("📦 Xem Raw JSON Input Snapshot (Toàn bộ dữ liệu BCTC & Chỉ báo nạp vào AI lúc đó)"):
                    st.json(snapshot)

    # 6. PHÂN TÍCH NGUYÊN NHÂN THẤT BẠI (POST-MORTEM ATTRIBUTION)
    loss_reasons = metrics.get("loss_reasons", {})
    if loss_reasons:
        st.divider()
        st.markdown("### 📊 Phân Tích Nguyên Nhân Thất Bại (Loss Attribution)")
        st.caption("Thống kê xem các lệnh thua là do thị trường chung gãy, do doanh nghiệp xấu đi hay do AI lạc quan tếu:")
        loss_df = pd.DataFrame(list(loss_reasons.items()), columns=["Nguyên nhân", "Số lệnh"])
        st.bar_chart(loss_df.set_index("Nguyên nhân"), color="#dc2626", width="stretch")
