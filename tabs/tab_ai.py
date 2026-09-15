import re
import textwrap
import streamlit as st
import pandas as pd
from data_engine import (
    fetch_macro_news,
    fetch_stock_technical,
    get_financial_ratios,
    get_vnindex_valuation_data
)
from ai_analyst import (
    generate_portfolio_analysis,
    generate_market_risk_scenarios,
    generate_institutional_stock_report,
    generate_quantamental_2pass_report
)

def sanitize_markdown_report(text: str) -> str:
    """
    Chuẩn hóa báo cáo Markdown trước khi đưa vào st.markdown:
    1. Thay thế hàng ký tự dấu bằng (===...) bằng đường kẻ ngang chuẩn (---).
    2. Chuyển Unicode bullet '• ' thành Markdown list marker '- ' để parser sinh thẻ <ul><li>.
    3. Đảm bảo khoảng cách dòng trước các tiêu đề để tránh bẫy Setext Heading.
    """
    if not text:
        return ""

    # 1. Thay thế hàng dấu bằng thành thẻ phân cách ---
    cleaned = re.sub(r'^[ \t]*={3,}[ \t]*$', '---', text, flags=re.MULTILINE)

    # 2. Chuyển bullet Unicode (•) thành Markdown list marker (- )
    cleaned = re.sub(r'^[ \t]*•[ \t]*', '- ', cleaned, flags=re.MULTILINE)

    # 3. Đảm bảo tiêu đề (#, ##, ###) có dòng trống phía trước
    cleaned = re.sub(r'(?<!\n)\n(#{1,4}\s+)', r'\n\n\1', cleaned)

    return cleaned


def render_tab_ai(df_eval: pd.DataFrame):
    """
    Render Tab Trợ lý Chiến lược AI:
    - Phân hệ 1: Đánh giá sức khỏe danh mục đầu tư
    - Phân hệ 2: Ma trận kịch bản rủi ro thị trường & Chu kỳ sóng Elliott / Wyckoff
    - Phân hệ 3: Báo cáo phân tích cổ phiếu định chế chuyên sâu 8 trụ cột (Thang điểm 100)
    """
    st.markdown("### 🧠 Trung Tâm Phân Tích & Chiến Lược AI (Gemini Flash)")
    st.caption("Trí tuệ nhân tạo chuyên sâu tài chính: Tích hợp dữ liệu giao dịch realtime, báo cáo tài chính định chế và dòng tiền vĩ mô.")

    sub_tab1, sub_tab2, sub_tab3 = st.tabs([
        "Đánh giá Danh mục",
        "Kịch bản Rủi ro & Sóng",
        "Nghiên cứu Định chế 8 Trụ cột"
    ])

    # -------------------------------------------------------------
    # SUB-TAB 1: ĐÁNH GIÁ DANH MỤC HIỆN TẠI
    # -------------------------------------------------------------
    with sub_tab1:
        st.markdown("##### 📌 Đánh Giá Toàn Diện Danh Mục Đang Nắm Giữ")
        st.caption("AI kết hợp dữ liệu giá vốn, vị thế lãi/lỗ và tin tức vĩ mô để tư vấn điểm chốt lời / cắt lỗ chi tiết.")

        custom_q = st.text_input(
            "Câu hỏi bổ sung cho danh mục (tùy chọn):",
            placeholder="Ví dụ: SSI chạm giá nào nên hạ bớt? Có nên cơ cấu gom thêm BSR vùng giá hiện tại?",
            key="ai_portfolio_custom_q"
        )

        if st.button("🚀 Phân Tích Toàn Diện Danh Mục", type="primary", use_container_width=True, key="btn_run_portfolio_ai"):
            with st.spinner("Gemini Flash đang đọc dữ liệu danh mục và lập kế hoạch hành động..."):
                news = fetch_macro_news()
                analysis_result = generate_portfolio_analysis(df_eval, news, custom_question=custom_q)
                st.session_state["cached_portfolio_ai"] = analysis_result

        if "cached_portfolio_ai" in st.session_state:
            st.markdown(sanitize_markdown_report(st.session_state["cached_portfolio_ai"]))

    # -------------------------------------------------------------
    # SUB-TAB 2: KỊCH BẢN RỦI RO THỊ TRƯỜNG & DỰ BÁO SÓNG
    # -------------------------------------------------------------
    with sub_tab2:
        st.markdown("##### 🗺️ Ma Trận Kịch Bản Rủi Ro Thị Trường & Chu Kỳ Sóng")
        st.caption("Mô hình hóa 4 kịch bản thị trường (Lạc quan, Trung lập, Bi quan, Thiên nga đen) kèm xác suất, điều kiện kích hoạt, tỷ lệ phân bổ vốn và định vị chu kỳ sóng Elliott / Wyckoff.")

        col_m1, col_m2 = st.columns([3, 1])
        with col_m1:
            st.info("💡 **Hệ thống AI sẽ quét:** Chỉ số VN-Index, P/E thị trường, thanh khoản phiên và các dòng tin tức vĩ mô 24h qua (lãi suất, tỷ giá, giá dầu).")
        with col_m2:
            run_market_scenarios = st.button("⚡ Vẽ Kịch Bản Thị Trường", type="primary", use_container_width=True, key="btn_run_market_scenarios")

        if run_market_scenarios:
            with st.spinner("Đang định vị chu kỳ sóng và xây dựng ma trận kịch bản vĩ mô..."):
                vnindex_df = get_vnindex_valuation_data()
                news = fetch_macro_news()
                market_report = generate_market_risk_scenarios(vnindex_df, news)
                st.session_state["cached_market_scenarios"] = market_report

        if "cached_market_scenarios" in st.session_state:
            st.markdown(sanitize_markdown_report(st.session_state["cached_market_scenarios"]))

    # -------------------------------------------------------------
    # SUB-TAB 3: NGHIÊN CỨU CỔ PHIẾU CHUYÊN SÂU (8 TRỤ CỘT & 100 ĐIỂM)
    # -------------------------------------------------------------
    with sub_tab3:
        st.markdown("##### 🔬 Institutional Equity Research - Báo Cáo Định Chế 8 Trụ Cột")
        st.caption("Chuẩn mực phân tích CFA: Tóm tắt điều hành trên đầu, Bảng tín hiệu nhanh từng trụ cột, Định giá Fair Value gãy gọn và Chấm điểm thang 100.")

        portfolio_symbols = df_eval["Mã CP"].tolist() if "Mã CP" in df_eval.columns else ["BSR", "MSB", "SSI"]
        default_options = list(dict.fromkeys(portfolio_symbols + ["FPT", "HPG", "VNM", "VCB", "MWG", "DGC"]))

        col_sel, col_custom = st.columns([1, 1])
        with col_sel:
            selected_choice = st.selectbox(
                "Chọn cổ phiếu cần phân tích:",
                options=default_options,
                index=0,
                key="ai_stock_select"
            )
        with col_custom:
            custom_ticker = st.text_input(
                "Hoặc nhập mã cổ phiếu khác (3 chữ cái):",
                placeholder="Ví dụ: PVD, VHM, DGW...",
                key="ai_stock_custom"
            ).strip().upper()

        target_symbol = custom_ticker if custom_ticker else selected_choice

        # Snapshot nhanh các chỉ số
        tech_data = fetch_stock_technical(target_symbol)
        fin_data = get_financial_ratios(target_symbol)

        if tech_data:
            chg = tech_data.get('change_pct', 0)
            chg_color = "#15803d" if chg >= 0 else "#dc2626"
            chg_bg = "rgba(22, 163, 74, 0.1)" if chg >= 0 else "rgba(220, 38, 38, 0.1)"
            chg_sign = "+" if chg > 0 else ""

            rsi_val = tech_data.get('rsi14', 'N/A')
            try:
                rsi_num = float(rsi_val)
                if rsi_num > 70:
                    rsi_status = '<span style="color:#dc2626; font-size:10.5px; font-weight:700;">(Quá mua)</span>'
                elif rsi_num < 30:
                    rsi_status = '<span style="color:#15803d; font-size:10.5px; font-weight:700;">(Quá bán)</span>'
                else:
                    rsi_status = '<span style="color:#64748b; font-size:10.5px; font-weight:600;">(Trung tính)</span>'
            except:
                rsi_status = ""

            pe_val = fin_data.get('pe', 'N/A')
            pb_val = fin_data.get('pb', 'N/A')
            roe_val = f"{fin_data.get('roe', 'N/A')}%" if fin_data.get('roe') is not None else "N/A"

            ff = tech_data.get("foreign_flow", {})
            ff_net = ff.get("net_val_bil", 0.0) if ff else 0.0
            ff_color = "#15803d" if ff_net >= 0 else "#dc2626"
            ff_bg = "rgba(22, 163, 74, 0.1)" if ff_net >= 0 else "rgba(220, 38, 38, 0.1)"
            ff_sign = "+" if ff_net > 0 else ""
            ff_status_vi = ff.get("status_vi", "N/A") if ff else "N/A"

            trap_info = tech_data.get("trap_info", {})
            is_trap = trap_info.get("is_trap", False)

            metrics_grid_html = textwrap.dedent(f"""
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 14px; margin: 16px 0 16px 0;">
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.03); display: flex; flex-direction: column; align-items: center; justify-content: center;">
                    <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">THỊ GIÁ</div>
                    <div style="font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.3px;">
                        {tech_data.get('current_price', 'N/A')} <span style="font-size: 12px; font-weight: 600; color: #64748b;">k</span>
                    </div>
                    <div style="display: inline-block; background: {chg_bg}; color: {chg_color}; font-size: 11px; font-weight: 700; padding: 1px 6px; border-radius: 4px; margin-top: 3px;">
                        {chg_sign}{chg:.2f}%
                    </div>
                </div>
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.03); display: flex; flex-direction: column; align-items: center; justify-content: center;">
                    <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">RSI (14)</div>
                    <div style="font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.3px;">
                        {rsi_val}
                    </div>
                    <div style="margin-top: 3px;">{rsi_status}</div>
                </div>
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.03); display: flex; flex-direction: column; align-items: center; justify-content: center;">
                    <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">P/E</div>
                    <div style="font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.3px;">
                        {pe_val} <span style="font-size: 12px; font-weight: 600; color: #64748b;">x</span>
                    </div>
                    <div style="font-size: 10.5px; font-weight: 600; color: #94a3b8; margin-top: 3px;">Bội số giá/LN</div>
                </div>
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.03); display: flex; flex-direction: column; align-items: center; justify-content: center;">
                    <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">KHỐI NGOẠI</div>
                    <div style="font-size: 18px; font-weight: 800; color: {ff_color}; letter-spacing: -0.3px;">
                        {ff_sign}{ff_net:.1f} <span style="font-size: 11px; font-weight: 600; color: #64748b;">Tỷ</span>
                    </div>
                    <div style="font-size: 10.5px; font-weight: 700; color: {ff_color}; margin-top: 3px;">{ff_status_vi}</div>
                </div>
                <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.03); display: flex; flex-direction: column; align-items: center; justify-content: center;">
                    <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">ROE / VỐN</div>
                    <div style="font-size: 20px; font-weight: 800; color: #0f172a; letter-spacing: -0.3px;">
                        {roe_val}
                    </div>
                    <div style="font-size: 10.5px; font-weight: 600; color: #94a3b8; margin-top: 3px;">Hiệu quả vốn</div>
                </div>
            </div>
            """).strip()
            st.html(metrics_grid_html)

            if is_trap:
                trap_callout = textwrap.dedent(f"""
                <div style="background: rgba(239, 68, 68, 0.1); border-left: 4px solid #ef4444; border-radius: 6px; padding: 10px 14px; margin: 8px 0 14px 0;">
                    <div style="font-size: 13px; font-weight: 800; color: #dc2626;">
                        ⚠️ CẢNH BÁO BẪY TIN TỨC / KÉO XẢ
                    </div>
                    <div style="font-size: 12px; color: #b91c1c; margin-top: 2px;">
                        {trap_info.get('warning_msg')}
                    </div>
                </div>
                """).strip()
                st.html(trap_callout)

        col_b1, col_b2 = st.columns(2)
        btn_key = f"btn_run_deep_{target_symbol}"
        btn_quant_key = f"btn_run_quant_{target_symbol}"

        with col_b1:
            if st.button(f"⚡ Báo Cáo Định Chế 8 Trụ Cột", type="primary", use_container_width=True, key=btn_key):
                with st.spinner(f"Chuyên gia AI đang phân tích toàn diện 8 trụ cột cho mã {target_symbol}..."):
                    news = fetch_macro_news(limit=6, tracked_symbols=[target_symbol])
                    report = generate_institutional_stock_report(target_symbol, fin_data, tech_data, news)
                    st.session_state[f"cached_stock_report_{target_symbol}"] = report

        with col_b2:
            if st.button(f"🔬 Lượng Hóa 2 Lượt (Quant Pro)", type="secondary", use_container_width=True, key=btn_quant_key):
                with st.spinner(f"Hệ thống Quant đang kiểm tra Data Gate & tính toán hàng rào 2 lượt cho {target_symbol}..."):
                    res = generate_quantamental_2pass_report(target_symbol)
                    st.session_state[f"cached_stock_report_{target_symbol}"] = res.get("report_text", "")

        cache_key = f"cached_stock_report_{target_symbol}"
        if cache_key in st.session_state:
            report_text = st.session_state[cache_key]

            st.divider()

            # Nhận diện tín hiệu để hiển thị Banner Cảnh Báo Màu Sắc (Xanh / Vàng / Đỏ / Tím Veto)
            up_text = report_text.upper()
            if "CẢNH BÁO BẪY" in up_text[:800] or "TỪ CHỐI KHUYẾN NGHỊ" in up_text[:800]:
                alert_theme = {
                    "bg": "rgba(239, 68, 68, 0.15)",
                    "border": "#dc2626",
                    "title": "⛔ CẢNH BÁO: HÀNG RÀO QUANT TỪ CHỐI / PHÁT HIỆN BẪY GIÁ",
                    "sub": "Vi phạm tiêu chuẩn an toàn quỹ hoặc phát hiện bẫy tin tức kéo xả. Cấm mua tuyệt đối!"
                }
            elif "MUA MẠNH" in up_text or "MUA" in up_text[:600]:
                alert_theme = {
                    "bg": "rgba(34, 197, 94, 0.12)",
                    "border": "#22c55e",
                    "title": "🟢 TÍN HIỆU: KHUYẾN NGHỊ MUA / TÍCH CỰC",
                    "sub": "Hội tụ các tiêu chí: Tăng trưởng cơ bản, định giá hấp dẫn và dòng tiền ủng hộ."
                }
            elif "BÁN" in up_text[:600] or "HẠ TỶ TRỌNG" in up_text[:600]:
                alert_theme = {
                    "bg": "rgba(239, 68, 68, 0.12)",
                    "border": "#ef4444",
                    "title": "🔴 CẢNH BÁO: KHUYẾN NGHỊ BÁN / THẬN TRỌNG RỦI RO",
                    "sub": "Vi phạm ngưỡng kỹ thuật hoặc áp lực điều chỉnh. Cần ưu tiên bảo toàn vốn."
                }
            else:
                alert_theme = {
                    "bg": "rgba(234, 179, 8, 0.12)",
                    "border": "#eab308",
                    "title": "🟡 TÍN HIỆU: THEO DÕI / NẮM GIỮ QUAN SÁT",
                    "sub": "Cổ phiếu trong vùng tích lũy giằng co. Chờ dòng tiền bứt phá để gia tăng."
                }

            st.markdown(f"""
            <div style="background:{alert_theme['bg']}; border-left:5px solid {alert_theme['border']}; border-radius:8px; padding:12px 18px; margin-bottom:15px;">
                <div style="font-size:16px; font-weight:800; color:#f8fafc;">
                    {alert_theme['title']}
                </div>
                <div style="font-size:12px; color:#cbd5e1; margin-top:3px;">
                    {alert_theme['sub']}
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(sanitize_markdown_report(report_text))
