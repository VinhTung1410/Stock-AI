import streamlit as st
import pandas as pd
from data_engine import fetch_macro_news
from ai_analyst import generate_portfolio_analysis

def render_tab_ai(df_eval: pd.DataFrame):
    """Render Tab 5: Trợ lý phân tích chiến lược AI (Gemini Flash)."""
    st.subheader("🧠 Hỏi Chuyên gia Chiến lược AI (Gemini Flash)")
    st.caption("AI sẽ kết hợp trạng thái danh mục, giá vốn của bạn cùng dữ liệu nến và tin tức vĩ mô mới nhất.")

    custom_q = st.text_input(
        "Câu hỏi bổ sung (tùy chọn):",
        placeholder="Ví dụ: P/E của SSI có đắt không? BSR chạm giá nào thì nên chốt lời?"
    )
    
    if st.button("🚀 Phân tích Toàn diện Danh mục", type="primary", use_container_width=True):
        with st.spinner("Gemini Flash đang phân tích dữ liệu chuyên sâu..."):
            news = fetch_macro_news()
            analysis_result = generate_portfolio_analysis(df_eval, news, custom_question=custom_q)
            st.markdown(analysis_result)
