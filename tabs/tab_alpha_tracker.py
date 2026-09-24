import textwrap

import pandas as pd
import streamlit as st

from db_manager import get_signal_audit_metrics, update_daily_tracking


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
    🎯 TAB 6: HỆ THỐNG KIỂM TOÁN HIỆU QUẢ TÍN HIỆU & BACKTEST / PAPER TRADING
    - Subtab 1: Kiểm toán Tín hiệu (Alpha Ledger)
    - Subtab 2: Backtest Lõi Định Lượng Theo Regime
    - Subtab 3: Forward Testing (Paper Trading)
    """
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h2 style="font-size: 24px; font-weight: 800; color: #0f172a; margin-bottom: 4px; display: flex; align-items: center; gap: 8px;">
            🎯 KIỂM TOÁN TÍN HIỆU & ENGINE BACKTEST / PAPER TRADING
        </h2>
        <p style="font-size: 13.5px; color: #64748b; margin: 0; font-family: 'Inter', -apple-system, sans-serif;">
            Hệ thống đối soát độc lập: Kiểm toán Alpha thực tế, Backtest 3 Regime HOSE, và Forward Testing đo lường Implementation Shortfall.
        </p>
    </div>
    """, unsafe_allow_html=True)

    subtab1, subtab2, subtab3 = st.tabs([
        "🎯 Kiểm Toán Tín Hiệu (Alpha Ledger)",
        "🚀 Backtest Lõi Định Lượng Theo Regime",
        "📝 Forward Testing (Paper Trading)",
    ])

    with subtab1:
        _render_alpha_audit_subtab()

    with subtab2:
        _render_regime_backtest_subtab()

    with subtab3:
        _render_paper_trading_subtab()


def _render_alpha_audit_subtab():
    """Subtab 1: Original Alpha Audit and Post-market verification."""
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


def _render_regime_backtest_subtab():
    """Render interactive Regime-based Backtest controls and performance breakdown."""
    st.markdown("""
    <div style="margin-bottom: 16px;">
        <h3 style="margin: 0; color: #0f172a; font-weight: 700;">🚀 Engine Backtest Định Lượng Theo Regime Thị Trường</h3>
        <p style="color: #64748b; font-size: 13.5px; margin-top: 4px;">
            Mô phỏng chân thực quy chế HOSE: <b>Chặn mua trần (+6.9%+)</b>, <b>Chu kỳ T+2.5</b>, <b>Trượt giá bps</b>, và <b>Phí/Thuế thực tế</b>.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns([1.5, 1.2, 1.5, 1.8])
    with col1:
        sym_input = st.text_input("Mã Cổ phiếu", value="HPG").upper().strip()
    with col2:
        limit_days = st.selectbox("Số phiên nến ngày", [60, 120, 200, 300], index=2)
    with col3:
        initial_cap = st.number_input("Vốn ban đầu (VND)", value=100_000_000, step=10_000_000)
    with col4:
        method = st.selectbox("Phương pháp phân loại Regime", ["MA200_SLOPE", "MOMENTUM_VOLATILITY"])

    if st.button("⚡ Chạy Backtest Theo Regime", type="primary", width="stretch"):
        with st.spinner(f"Đang kéo dữ liệu {sym_input} và mô phỏng giao dịch lịch sử..."):
            from backtest_engine import RegimeBacktestEngine
            from data_engine import fetch_stock_historical
            from regime_classifier import classify_market_regime

            df_p = fetch_stock_historical(sym_input, limit=limit_days)
            if df_p.empty or len(df_p) < 30:
                st.error(f"Không thể tải đủ dữ liệu lịch sử cho {sym_input}. Vui lòng thử lại hoặc chọn mã khác.")
                return

            # Chuẩn hóa chỉ mục ngày tháng và tạo tín hiệu MA crossover
            if "time" in df_p.columns:
                df_p["time"] = pd.to_datetime(df_p["time"])
                df_p = df_p.set_index("time")

            close = df_p["close"].astype(float)
            ma20 = close.rolling(20, min_periods=10).mean()
            ma50 = close.rolling(50, min_periods=20).mean()

            signals = pd.Series(0, index=df_p.index)
            bullish = (ma20 > ma50) & (ma20.shift(1) <= ma50.shift(1))
            bearish = (ma20 < ma50) & (ma20.shift(1) >= ma50.shift(1))
            signals[bullish] = 1
            signals[bearish] = -1

            regimes = classify_market_regime(df_p, method=method)
            engine = RegimeBacktestEngine(initial_capital=float(initial_cap))
            result = engine.run_backtest(df_p, signals, regimes)

            st.success(f"✅ Hoàn tất Backtest {sym_input} ({len(df_p)} phiên)! Tổng số lệnh: {len(result.trades)}")

            # Hiển thị bảng số liệu 4 cột
            reg_data = result.regime_metrics
            table_rows = []
            metric_keys = [
                ("Tổng số lệnh", "total_trades"),
                ("Lệnh không khớp (Trần HOSE)", "unfilled_trades"),
                ("Tỷ lệ thắng (Win Rate %)", "win_rate_pct"),
                ("Profit Factor", "profit_factor"),
                ("Kỳ vọng mỗi lệnh (Expectancy)", "expectancy"),
                ("Lợi nhuận gộp CAGR (%)", "cagr_pct"),
                ("Sụt giảm tối đa MDD (%)", "max_drawdown_pct"),
                ("Thời gian hồi phục (Ngày)", "recovery_days"),
                ("Sharpe Ratio (Rf=4.5%)", "sharpe_ratio"),
                ("Sortino Ratio", "sortino_ratio"),
                ("Alpha vs VN-Index (%)", "alpha_pct"),
                ("Beta", "beta"),
            ]
            for label, key in metric_keys:
                table_rows.append({
                    "Chỉ Số Định Lượng": label,
                    "Toàn Kỳ (FULL)": reg_data.get("FULL", {}).get(key, "N/A"),
                    "Uptrend (Tăng)": reg_data.get("UPTREND", {}).get(key, "N/A"),
                    "Downtrend (Giảm)": reg_data.get("DOWNTREND", {}).get(key, "N/A"),
                    "Sideways (Đi Ngang)": reg_data.get("SIDEWAYS", {}).get(key, "N/A"),
                })

            st.markdown("#### 📊 Bảng Chỉ Số Bóc Tách Theo 3 Chế Độ Thị Trường")
            st.dataframe(pd.DataFrame(table_rows), width="stretch", hide_index=True)

            if not result.equity_curve.empty:
                st.markdown("#### 📈 Biểu Đồ Đường Vốn Tài Sản (Equity Curve - VND)")
                st.line_chart(result.equity_curve)


def _render_paper_trading_subtab():
    """Render Forward Testing & Implementation Shortfall tracking."""
    st.markdown("""
    <div style="margin-bottom: 16px;">
        <h3 style="margin: 0; color: #0f172a; font-weight: 700;">📝 Khung Forward Testing (Paper Trading)</h3>
        <p style="color: #64748b; font-size: 13.5px; margin-top: 4px;">
            Đo lường <b>Implementation Shortfall (Trượt giá thực thi tính theo bps)</b> và kiểm chứng tỷ lệ khớp lệnh trên thị trường thực.
        </p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Vốn ảo thử nghiệm (NAV)", "100,000,000 VND", "Simulated Capital")
    with c2:
        st.metric("Hạn mức tín hiệu", "2 BUY / ngày", "Daily Signal Budget")
    with c3:
        st.metric("Thời gian kiểm chứng", "3 - 6 Tháng", "Bậc 0: Zero Real Capital")

    st.divider()
    st.markdown("#### 🎯 Bộ Đo Lường Implementation Shortfall (Thử Nghiệm Độ Lệch Giá)")
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        dec_price = st.number_input("Giá Quyết Định / Bắn Tín Hiệu (k)", value=30.0, step=0.1)
    with col_s2:
        fill_price = st.number_input("Giá Khớp Thực Tế / Giả Lập (k)", value=30.2, step=0.1)
    with col_s3:
        side = st.selectbox("Loại Lệnh", ["BUY (Mua)", "SELL (Bán)"])

    from paper_trading import calculate_implementation_shortfall
    is_buy = "BUY" in side
    shortfall_bps = calculate_implementation_shortfall(dec_price, fill_price, is_buy=is_buy)
    slip_color = "#dc2626" if shortfall_bps > 0 else "#15803d"
    st.markdown(f"""
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; margin-top: 8px;">
        <b>Độ trượt giá thực thi (Implementation Shortfall):</b>
        <span style="font-size: 20px; font-weight: 800; color: {slip_color}; margin-left: 8px;">
            {shortfall_bps:+.2f} bps
        </span>
        <span style="font-size: 12px; color: #64748b; margin-left: 8px;">
            ({(shortfall_bps / 100.0):+.2f}% so với giá dự kiến)
        </span>
    </div>
    """, unsafe_allow_html=True)

