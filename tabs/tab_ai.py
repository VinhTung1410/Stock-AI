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
    generate_institutional_stock_report
)

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
        "📊 Đánh Giá Danh Mục",
        "🗺️ Kịch Bản Rủi Ro Thị Trường & Sóng",
        "🔬 Nghiên Cứu Cổ Phiếu Chuyên Sâu (8 Trụ Cột)"
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
                st.markdown(analysis_result)

    # -------------------------------------------------------------
    # SUB-TAB 2: KỊCH BẢN RỦI RO THỊ TRƯỜNG & DỰ BÁO SÓNG
    # -------------------------------------------------------------
    with sub_tab2:
        st.markdown("##### 🗺️ Ma Trận Kịch Bản Rủi Ro Thị Trường & Chu Kỳ Sóng")
        st.caption("Mô hình hóa ít nhất 3-4 kịch bản thị trường (Lạc quan, Trung lập, Bi quan, Thiên nga đen) kèm xác suất, điều kiện kích hoạt, tỷ lệ phân bổ vốn và định vị chu kỳ sóng Elliott / Wyckoff.")

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
                st.markdown(market_report)

    # -------------------------------------------------------------
    # SUB-TAB 3: NGHIÊN CỨU CỔ PHIẾU CHUYÊN SÂU (8 TRỤ CỘT & 100 ĐIỂM)
    # -------------------------------------------------------------
    with sub_tab3:
        st.markdown("##### 🔬 Institutional Equity Research - Báo Cáo Định Chế 8 Trụ Cột")
        st.caption("Chuẩn mực phân tích CFA: Kiểm tra dữ liệu, Cơ bản, Định giá & Biên an toàn, Kỹ thuật, Dòng tiền Big Boys, Rủi ro, 3 Kịch bản và Chấm điểm thang 100 kèm tóm tắt 5 dòng.")

        # Lấy danh sách mã gợi ý từ danh mục
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

        # Hiển thị snapshot nhanh các chỉ số nếu có
        tech_data = fetch_stock_technical(target_symbol)
        fin_data = get_financial_ratios(target_symbol)

        if tech_data:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Thị giá", f"{tech_data.get('current_price', 'N/A')} k", f"{tech_data.get('change_pct', 0):+.2f}%")
            c2.metric("RSI (14)", f"{tech_data.get('rsi14', 'N/A')}")
            c3.metric("P/E", f"{fin_data.get('pe', 'N/A')}")
            c4.metric("P/B", f"{fin_data.get('pb', 'N/A')}")
            c5.metric("ROE (%)", f"{fin_data.get('roe', 'N/A')}%" if fin_data.get('roe') is not None else "N/A")

        if st.button(f"⚡ Lập Báo Cáo Chuyên Sâu 8 Trụ Cột Cho [{target_symbol}]", type="primary", use_container_width=True, key=f"btn_run_deep_{target_symbol}"):
            with st.spinner(f"Chuyên gia AI đang phân tích toàn diện 8 trụ cột cho mã {target_symbol}..."):
                news = fetch_macro_news(keywords=[target_symbol, "chứng khoán", "kết quả kinh doanh"])
                report = generate_institutional_stock_report(target_symbol, fin_data, tech_data, news)
                st.markdown(report)
