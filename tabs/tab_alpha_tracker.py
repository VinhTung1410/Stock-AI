import textwrap
from typing import Any, Final

import pandas as pd
import streamlit as st

from db_manager import get_signal_audit_metrics, update_daily_tracking

COL_SIGNAL_DATE: Final[str] = "Ngày phát"
COL_ACTION: Final[str] = "Hành động"
COL_STATUS: Final[str] = "Trạng thái"
FILTER_ALL: Final[str] = "Tất cả"


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


def _render_alpha_hero_cards(metrics: dict) -> None:
    """Render top hero KPI cards for alpha audit."""
    total_signals = metrics.get("total_signals", 0)
    resolved_count = metrics.get("resolved_signals", 0)
    open_count = metrics.get("open_signals", 0)
    win_rate = float(metrics.get("win_rate") or 0.0)
    profit_factor = float(metrics.get("profit_factor") or 0.0)
    alpha_vni = float(metrics.get("alpha_vs_vnindex") or 0.0)
    avg_win = float(metrics.get("avg_win") or 0.0)
    avg_loss = float(metrics.get("avg_loss") or 0.0)

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


def _filter_and_render_signals_table(df_signals: pd.DataFrame) -> pd.DataFrame:
    """Render filters and signal table, returning filtered DataFrame."""
    st.markdown("### 📋 Danh Sách Khuyến Nghị & Lịch Sử Đối Soát")
    col_f1, col_f2, _ = st.columns([2, 2, 2])
    with col_f1:
        filter_status = st.selectbox(
            "Lọc theo trạng thái:",
            [FILTER_ALL, "Đang mở (OPEN)", "Chốt lời (TARGET_HIT)", "Cắt lỗ (STOP_LOSS)", "Hết hạn (EXPIRED)"]
        )
    with col_f2:
        all_syms = [FILTER_ALL] + sorted(df_signals["Mã"].dropna().astype(str).unique().tolist())
        filter_sym = st.selectbox("Lọc theo mã CP:", all_syms)

    status_map = {
        "Đang mở (OPEN)": "OPEN",
        "Chốt lời (TARGET_HIT)": "TARGET_HIT",
        "Cắt lỗ (STOP_LOSS)": "STOP_LOSS",
        "Hết hạn (EXPIRED)": "EXPIRED",
    }
    filtered_df = df_signals.copy()
    if filter_status in status_map:
        filtered_df = filtered_df[filtered_df[COL_STATUS] == status_map[filter_status]]
    if filter_sym != FILTER_ALL:
        filtered_df = filtered_df[filtered_df["Mã"] == filter_sym]

    display_cols = [
        "ID", "Mã", COL_SIGNAL_DATE, COL_ACTION, "Giá vào", "Giá Target", "Stop-Loss",
        COL_STATUS, "PnL Thực tế (%)", "Alpha vs VNI (%)", "Đỉnh MFE", "Đáy MAE",
        "MoS (%)", "F-Score", "Nguyên nhân nếu lỗ"
    ]
    avail_cols = [c for c in display_cols if c in filtered_df.columns]
    st.dataframe(filtered_df[avail_cols], width="stretch", hide_index=True)
    return filtered_df


def _render_signal_detail_inspector(filtered_df: pd.DataFrame, df_signals: pd.DataFrame) -> None:
    """Render inspector card for selected signal snapshot."""
    st.divider()
    st.markdown("### 🔍 Hộp Đen Kiểm Toán: 'Tại thời điểm phát tín hiệu, Bot thực sự nhìn thấy gì?'")

    def _format_label(x):
        matches = filtered_df[filtered_df["ID"] == x]
        if matches.empty:
            return f"Signal #{x}"
        row = matches.iloc[0]
        return f"Signal #{x} - {row.get('Mã', '')} ({row.get(COL_SIGNAL_DATE, '')} | Trạng thái: {row.get(COL_STATUS, 'OPEN')})"

    selected_id = st.selectbox(
        "Chọn một tín hiệu để mở hộp đen dữ liệu gốc:",
        options=filtered_df["ID"].tolist(),
        format_func=_format_label
    )
    if not selected_id:
        return

    target_rows = df_signals[df_signals["ID"] == selected_id]
    if target_rows.empty:
        return

    target_row = target_rows.iloc[0]
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
        - Mã: **{target_row.get('Mã', 'N/A')}** ({target_row.get(COL_ACTION, 'N/A')})
        - Ngày phát: `{target_row.get(COL_SIGNAL_DATE, 'N/A')}`
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
        - Trạng thái hiện tại: **{target_row.get(COL_STATUS, 'OPEN')}**
        - P/L Thực tế: **{pnl_txt}**
        - Alpha vs VN-Index: **{alpha_txt}**
        - Đỉnh MFE: `{mfe_txt}` | Đáy MAE: `{mae_txt}`
        - Giá T+1: `{t1_txt}` | T+5: `{t5_txt}` | T+20: `{t20_txt}`
        """)

    thesis = target_row.get("AI Thesis") or "Không có ghi chú luận điểm."
    st.markdown(f"**Luận điểm AI (Pass 1 & Pass 2):** {thesis}")
    if target_row.get("Nguyên nhân nếu lỗ"):
        st.error(f"⚠️ **Nguyên nhân thất bại (Loss Attribution):** `{target_row['Nguyên nhân nếu lỗ']}`")

    snapshot = target_row.get("Input Snapshot")
    if snapshot:
        with st.expander("📦 Xem Raw JSON Input Snapshot (Toàn bộ dữ liệu BCTC & Chỉ báo nạp vào AI lúc đó)"):
            st.json(snapshot)


def _render_loss_attribution(loss_reasons: dict) -> None:
    """Render loss attribution bar chart if loss reasons exist."""
    if not loss_reasons:
        return
    st.divider()
    st.markdown("### 📊 Phân Tích Nguyên Nhân Thất Bại (Loss Attribution)")
    st.caption("Thống kê xem các lệnh thua là do thị trường chung gãy, do doanh nghiệp xấu đi hay do AI lạc quan tếu:")
    loss_df = pd.DataFrame(list(loss_reasons.items()), columns=["Nguyên nhân", "Số lệnh"])
    st.bar_chart(loss_df.set_index("Nguyên nhân"), color="#dc2626", width="stretch")


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

    subtab1, subtab2, subtab3, subtab4 = st.tabs([
        "🎯 Kiểm Toán Tín Hiệu (Alpha Ledger)",
        "🚀 Backtest Lõi Định Lượng Theo Regime",
        "📝 Forward Testing (Paper Trading)",
        "🌪️ Kiểm Tra Áp Lực & Rủi Ro Đuôi (Stress Test)",
    ])

    with subtab1:
        _render_alpha_audit_subtab()

    with subtab2:
        _render_regime_backtest_subtab()

    with subtab3:
        _render_paper_trading_subtab()

    with subtab4:
        _render_stress_test_subtab()


def _render_alpha_audit_subtab():
    """Subtab 1: Original Alpha Audit and Post-market verification."""
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

    metrics = get_signal_audit_metrics()
    _render_alpha_hero_cards(metrics)

    df_signals = metrics.get("signals_df", pd.DataFrame())
    if df_signals.empty:
        st.info("💡 **Chưa có dữ liệu kiểm toán trên Supabase.** Khi Trading Bot quét thị trường hoặc bạn bấm phân tích mã trên Tab 5, các khuyến nghị sẽ tự động được ghi nhận và lưu vết tại đây.")
        return

    filtered_df = _filter_and_render_signals_table(df_signals)
    if filtered_df.empty:
        st.info("ℹ️ Không tìm thấy khuyến nghị nào phù hợp với bộ lọc hiện tại.")
        return

    _render_signal_detail_inspector(filtered_df, df_signals)
    _render_loss_attribution(metrics.get("loss_reasons", {}))


def _normalize_price_index(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure price DataFrame has normalized DatetimeIndex."""
    df_out = df.copy()
    if "time" in df_out.columns:
        df_out["time"] = pd.to_datetime(df_out["time"]).dt.normalize()
        df_out = df_out.set_index("time")
    else:
        df_out.index = pd.to_datetime(df_out.index).normalize()
    return df_out


def _prepare_backtest_data(sym_input: str, limit_days: int, method: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series | None, pd.Series]:
    """Fetch and align stock price, VN-Index benchmark, returns, and regime series."""
    from data_engine import fetch_index_historical, fetch_stock_historical
    from regime_classifier import classify_market_regime

    df_p = fetch_stock_historical(sym_input, limit=limit_days)
    df_vni = fetch_index_historical("VNINDEX", limit=max(limit_days + 150, 300))

    if df_p.empty or len(df_p) < 20:
        return pd.DataFrame(), pd.DataFrame(), None, pd.Series()

    df_p = _normalize_price_index(df_p)
    vni_returns = None
    if not df_vni.empty:
        df_vni = _normalize_price_index(df_vni)
        vni_close = df_vni["close"].astype(float)
        vni_returns = vni_close.pct_change().dropna().reindex(df_p.index).fillna(0.0)
        raw_regimes = classify_market_regime(df_vni, method=method)
        regimes = raw_regimes.reindex(df_p.index).ffill().bfill()
    else:
        regimes = classify_market_regime(df_p, method=method)

    return df_p, df_vni, vni_returns, regimes


def _render_regime_kpi_table(reg_data: dict) -> None:
    """Render 4-column regime breakdown KPI table."""
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


def _render_equity_charts(result: Any, df_p: pd.DataFrame, df_vni: pd.DataFrame, initial_cap: float) -> None:
    """Render equity comparison line charts against buy-and-hold and benchmark."""
    if result.equity_curve.empty:
        return
    from backtest_engine import calculate_buy_and_hold_equity, calculate_normalized_benchmark_equity

    st.markdown("#### 📈 Biểu Đồ So Sánh Đường Vốn Tài Sản (Equity Curves - VND)")
    bh_equity = calculate_buy_and_hold_equity(df_p, initial_capital=initial_cap)
    chart_data = {
        "Chiến Lược (Strategy)": result.equity_curve,
        "Nắm Giữ Thụ Động (Buy & Hold)": bh_equity,
    }
    if not df_vni.empty:
        vni_equity = calculate_normalized_benchmark_equity(df_vni, df_p.index, initial_capital=initial_cap)
        chart_data["VN-Index Benchmark"] = vni_equity

    st.line_chart(pd.DataFrame(chart_data))


def _render_regime_backtest_subtab():
    """Render interactive Regime-based Backtest controls and performance breakdown."""
    st.markdown("""
    <div style="margin-bottom: 16px;">
        <h3 style="margin: 0; color: #0f172a; font-weight: 700;">🚀 Engine Backtest Định Lượng Theo Regime Thị Trường</h3>
        <p style="color: #64748b; font-size: 13.5px; margin-top: 4px;">
            Mô phỏng chân thực quy chế HOSE: <b>Chặn mua trần (+6.9%+)</b>, <b>Chu kỳ T+2.5</b>, <b>Trượt giá 15 bps</b>, <b>Benchmark VN-Index</b> và <b>Phí/Thuế thực tế</b>.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if "backtest_initial_cap" not in st.session_state:
        st.session_state["backtest_initial_cap"] = 100_000_000

    col1, col2, col3 = st.columns([1.5, 1.2, 2.0])
    with col1:
        sym_input = st.text_input("Mã Cổ phiếu", value="HPG").upper().strip()
    with col2:
        limit_days = st.selectbox("Số phiên nến ngày", [60, 120, 200, 300, 500], index=2)
    with col3:
        initial_cap = st.number_input(
            f"Vốn ban đầu: {st.session_state['backtest_initial_cap']:,.0f} VND",
            value=int(st.session_state["backtest_initial_cap"]),
            step=10_000_000,
            format="%d",
        )

    st.caption("Chọn nhanh quy mô vốn:")
    preset_cols = st.columns(4)
    presets = [("💵 50 Triệu", 50_000_000), ("💵 100 Triệu", 100_000_000), ("💵 500 Triệu", 500_000_000), ("💎 1 Tỷ", 1_000_000_000)]
    for col, (label, cap) in zip(preset_cols, presets):
        with col:
            if st.button(label, width="stretch"):
                st.session_state["backtest_initial_cap"] = cap
                st.rerun()

    c_strat, c_method = st.columns(2)
    with c_strat:
        strategy_label = st.selectbox(
            "Chiến lược kiểm định",
            [
                "Quant Core (FA Health + MoS + Z-Score + RSI - Khuyến nghị)",
                "MA Crossover (MA20/MA50 Trend Following)",
                "RSI Mean Reversion (Bắt đáy điều chỉnh)",
            ],
            index=0,
        )
    with c_method:
        method = st.selectbox("Phương pháp phân loại Regime VN-Index", ["MA200_SLOPE", "MOMENTUM_VOLATILITY"])

    enforce_cash_mode = st.checkbox(
        "🛡️ Kích hoạt Chốt chặn Vĩ mô Né sập (Macro Circuit Breaker / Cash Mode khi VN-Index Downtrend)",
        value=True,
        help="Tự động khóa toàn bộ lệnh MUA mới khi chỉ số VN-Index rơi vào pha Downtrend để bảo toàn 100% vốn trước các đợt sập.",
    )

    if st.button("⚡ Chạy Backtest Theo Regime", type="primary", width="stretch"):
        with st.spinner(f"Đang kéo dữ liệu {sym_input} & VN-Index để mô phỏng giao dịch định lượng..."):
            from backtest_engine import (
                STRATEGY_MA_CROSSOVER,
                STRATEGY_QUANT_CORE,
                STRATEGY_RSI_REVERSION,
                RegimeBacktestEngine,
                generate_signals_by_strategy,
            )

            df_p, df_vni, vni_returns, regimes = _prepare_backtest_data(sym_input, limit_days, method)
            if df_p.empty or len(df_p) < 20:
                st.error(f"Không thể tải đủ dữ liệu lịch sử cho {sym_input}. Vui lòng thử lại hoặc chọn mã khác.")
                return

            strat_code = STRATEGY_QUANT_CORE
            if "MA Crossover" in strategy_label:
                strat_code = STRATEGY_MA_CROSSOVER
            elif "RSI" in strategy_label:
                strat_code = STRATEGY_RSI_REVERSION

            signals = generate_signals_by_strategy(
                df_p,
                strategy=strat_code,
                regimes=regimes,
                enforce_regime_gate=enforce_cash_mode,
            )
            engine = RegimeBacktestEngine(initial_capital=float(initial_cap))
            result = engine.run_backtest(
                df_price=df_p,
                signals=signals,
                regimes=regimes,
                benchmark_returns=vni_returns,
                symbol=sym_input,
                enforce_regime_gate=enforce_cash_mode,
            )


            st.success(f"✅ Hoàn tất Backtest {sym_input} ({len(df_p)} phiên)! Tổng số lệnh: {len(result.trades)}")
            _render_regime_kpi_table(result.regime_metrics)
            _render_equity_charts(result, df_p, df_vni, float(initial_cap))

            st.markdown("""
            <div style="background: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 4px; margin-top: 20px;">
                <span style="font-size: 13px; color: #475569;">
                    ⚠️ <b>Khuyến cáo chuẩn mực CFA:</b> Hiệu suất quá khứ không đảm bảo kết quả tương lai. Backtest đã mô phỏng phí 0.15%, thuế bán 0.1%, trượt giá 15 bps, chu kỳ thanh toán T+2.5 và quy chế trần/sàn HOSE. Không phản ánh tác động thị trường (Market Impact) của quy mô vốn lớn.
                </span>
            </div>
            """, unsafe_allow_html=True)


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

    # Đấu nối dữ liệu lệnh ảo thực từ Supabase
    metrics = get_signal_audit_metrics()
    df_signals = metrics.get("signals_df", pd.DataFrame())
    if not df_signals.empty:
        st.markdown("#### 📋 Nhật Ký Lệnh Ảo Đang Theo Dõi (Forward Testing Ledger)")
        display_paper = []
        from paper_trading import calculate_implementation_shortfall
        for _, row in df_signals.head(10).iterrows():
            entry_p = float(row.get("Giá vào") or 0.0)
            t1_p = float(row.get("Giá T+1") or entry_p)
            shortfall = calculate_implementation_shortfall(entry_p, t1_p, is_buy=True)
            display_paper.append({
                "Mã": row.get("Mã"),
                COL_SIGNAL_DATE: row.get(COL_SIGNAL_DATE),
                COL_ACTION: row.get(COL_ACTION),
                "Giá đề xuất (k)": f"{entry_p:.1f}",
                "Giá thực tế T+1 (k)": f"{t1_p:.1f}" if t1_p > 0 else "Chờ khớp",
                "Trượt giá (bps)": f"{shortfall:+.1f}",
                COL_STATUS: row.get(COL_STATUS),
            })
        st.dataframe(pd.DataFrame(display_paper), width="stretch", hide_index=True)
    else:
        st.info("💡 **Chưa có lệnh ảo nào được ghi nhận.** Khi Trading Bot quét cơ hội hoặc phân tích mã trên Web, các lệnh ảo sẽ tự động lưu và đối soát trượt giá tại đây.")

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


def _build_crisis_stress_table(stress_summary: dict) -> pd.DataFrame:
    """Build formatted DataFrame from crisis stress summary."""
    rows = []
    for _, data in stress_summary.items():
        m_drop = data.get("market_drop_pct", 0.0)
        s_ret = data.get("strategy_return_pct", 0.0)
        mdd = data.get("max_drawdown_pct", 0.0)
        wr = data.get("win_rate_pct", 0.0)
        trades = data.get("total_trades", 0)

        rows.append({
            "Sự Kiện Khủng Hoảng Lịch Sử": data.get("name", "N/A"),
            "Bắt Đầu": data.get("start_date", "N/A"),
            "Kết Thúc": data.get("end_date", "N/A"),
            "VN-Index Giảm (%)": f"{m_drop:+.1f}%",
            "Chiến Lược Lãi/Lỗ (%)": f"{s_ret:+.2f}%",
            "Max Drawdown (MDD)": f"{mdd:.1f}%",
            "Số Lệnh": trades,
            "Tỷ Lệ Thắng (%)": f"{wr:.1f}%",
        })
    return pd.DataFrame(rows)


def _run_and_display_crisis_matrix(sym_input: str, enforce_cash_mode: bool) -> list[float]:
    """Fetch history, run 11-crisis stress matrix and display interactive table."""
    from backtest_engine import (
        STRATEGY_QUANT_CORE,
        RegimeBacktestEngine,
        generate_signals_by_strategy,
        run_crisis_stress_matrix,
    )
    from data_engine import fetch_index_historical, fetch_stock_historical
    from regime_classifier import classify_market_regime

    with st.spinner(f"Đang kiểm tra áp lực 11 khủng hoảng lịch sử cho {sym_input} (2018–2024)..."):
        df_p = fetch_stock_historical(sym_input, start_date="2018-01-01")
        df_vni = fetch_index_historical("VNINDEX", start_date="2018-01-01")

        if df_p.empty or len(df_p) < 50:
            st.error(f"Không thể tải đủ dữ liệu lịch sử từ 2018 cho {sym_input}.")
            return []

        df_p = _normalize_price_index(df_p)
        df_vni = _normalize_price_index(df_vni)
        vni_returns = df_vni["close"].astype(float).pct_change().reindex(df_p.index).fillna(0.0)
        regimes = classify_market_regime(df_vni).reindex(df_p.index).ffill().bfill()

        signals = generate_signals_by_strategy(
            df_p,
            strategy=STRATEGY_QUANT_CORE,
            regimes=regimes,
            enforce_regime_gate=enforce_cash_mode,
        )

        engine = RegimeBacktestEngine(initial_capital=100_000_000.0)
        res = run_crisis_stress_matrix(
            engine=engine,
            df_price=df_p,
            signals=signals,
            regimes=regimes,
            benchmark_returns=vni_returns,
            symbol=sym_input,
            enforce_regime_gate=enforce_cash_mode,
        )

        df_summary = _build_crisis_stress_table(res.get("stress_summary", {}))
        st.dataframe(df_summary, width="stretch", hide_index=True)

        full_bt = engine.run_backtest(
            df_price=df_p,
            signals=signals,
            regimes=regimes,
            benchmark_returns=vni_returns,
            symbol=sym_input,
            enforce_regime_gate=enforce_cash_mode,
        )
        return [t.pnl_pct for t in full_bt.trades] if full_bt.trades else []


def _render_flash_crash_scanner(df_vni: pd.DataFrame) -> None:
    """Render historical flash crashes detected on VN-Index."""
    from backtest_engine import scan_market_stress_events

    stress_events = scan_market_stress_events(df_vni)
    drop_50 = stress_events.get("drop_50pts_days", [])
    drop_4pct = stress_events.get("drop_4pct_days", [])

    st.markdown("#### ⚡ Nhật Ký Các Phiên Sập Chớp Nhoáng (Flash Crashes)")
    st.caption("Các phiên VN-Index giảm ≥ 50 điểm hoặc rơi tự do ≥ 4% trong ngày:")
    col_fc1, col_fc2 = st.columns(2)
    with col_fc1:
        st.write(f"**Phiên giảm ≥ 50 điểm:** `{len(drop_50)} phiên`")
        if drop_50:
            st.dataframe(pd.DataFrame(drop_50), width="stretch", hide_index=True)
    with col_fc2:
        st.write(f"**Phiên giảm ≥ 4.0%:** `{len(drop_4pct)} phiên`")
        if drop_4pct:
            st.dataframe(pd.DataFrame(drop_4pct), width="stretch", hide_index=True)


def _render_monte_carlo_tail_risk_ui(extracted_pnls: list[float]) -> None:
    """Render Monte Carlo tail risk simulation cards and metrics."""
    from quant_engine import simulate_monte_carlo_drawdown

    st.divider()
    st.markdown("### 🎲 Mô Phỏng Rủi Ro Đuôi Monte Carlo (Tail Risk 2,000 Kịch Bản - Phase 5a)")
    st.caption("Tráo đổi ngẫu nhiên thứ tự các lệnh để lượng hóa rủi ro tài khoản khi gặp chuỗi đen đủi liên tiếp:")

    default_pnls = extracted_pnls if extracted_pnls else [4.5, -2.1, 7.2, -5.0, 12.0, -6.5, 3.2, -4.0, 8.5, -3.2, 5.1, -7.0]
    col_mc1, col_mc2 = st.columns([3, 1])
    with col_mc1:
        pnl_str = st.text_input(
            "Chuỗi PnL lệnh (%) phân cách bằng dấu phẩy:",
            value=", ".join(str(round(p, 1)) for p in default_pnls[:15]),
        )
    with col_mc2:
        n_sim = st.selectbox("Số kịch bản giả lập", [1000, 2000, 5000], index=1)

    if st.button("🎲 Chạy Mô Phỏng Rủi Ro Đuôi Monte Carlo", width="stretch", type="secondary"):
        try:
            parsed_pnls = [float(x.strip()) for x in pnl_str.split(",") if x.strip()]
        except ValueError:
            st.error("Chuỗi PnL không hợp lệ. Vui lòng nhập số thực phân cách bằng dấu phẩy.")
            return

        with st.spinner(f"Đang chạy tái mẫu Bootstrap {n_sim:,} lần..."):
            res_mc = simulate_monte_carlo_drawdown(parsed_pnls, n_simulations=int(n_sim))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Max Drawdown Trung Vị", f"{res_mc['median_drawdown_pct']:.2f}%", "Median DD")
        c2.metric("Rủi Ro Đuôi P95", f"{res_mc['p95_drawdown_pct']:.2f}%", "95% Worst DD", delta_color="inverse")
        c3.metric("Rủi Ro Đuôi P99 (Khủng Hoảng)", f"{res_mc['p99_drawdown_pct']:.2f}%", "99% Catastrophic", delta_color="inverse")
        c4.metric("Xác Suất Lỗ Quá 15%", f"{res_mc['prob_drawdown_over_15pct']:.1f}%", f"Max {res_mc['max_consecutive_losses']} lệnh lỗ liên tiếp", delta_color="inverse")


def _render_stress_test_subtab():
    """Render Subtab 4: Crisis Stress Matrix & Monte Carlo Tail Risk."""
    st.markdown("""
    <div style="margin-bottom: 16px;">
        <h3 style="margin: 0; color: #0f172a; font-weight: 700;">🌪️ Kiểm Tra Áp Lực Khủng Hoảng & Mô Phỏng Rủi Ro Đuôi (Stress Test)</h3>
        <p style="color: #64748b; font-size: 13.5px; margin-top: 4px;">
            Kiểm tra sức chịu đựng của chiến lược qua <b>11 cuộc khủng hoảng lịch sử lớn nhất VN-Index (2018–2024)</b> và <b>Mô phỏng rủi ro đuôi Monte Carlo 2,000 kịch bản</b>.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([2, 2])
    with col1:
        sym_input = st.text_input("Mã Cổ phiếu Cần Stress Test", value="HPG", key="stress_sym").upper().strip()
    with col2:
        enforce_cash_mode = st.checkbox(
            "🛡️ Kích hoạt Macro Cash Mode (Khóa mua khi VN-Index Downtrend)",
            value=True,
            key="stress_cash_mode",
            help="Bảo toàn vốn tối đa trước các đợt sập lịch sử lớn.",
        )

    trade_pnls = []
    if st.button("⚡ Chạy Ma Trận 11 Khủng Hoảng Lịch Sử (2018–2024)", type="primary", width="stretch"):
        trade_pnls = _run_and_display_crisis_matrix(sym_input, enforce_cash_mode)

    from data_engine import fetch_index_historical
    df_vni = fetch_index_historical("VNINDEX", start_date="2018-01-01")
    if not df_vni.empty:
        _render_flash_crash_scanner(_normalize_price_index(df_vni))

    _render_monte_carlo_tail_risk_ui(trade_pnls)


