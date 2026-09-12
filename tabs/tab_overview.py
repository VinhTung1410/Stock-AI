import streamlit as st
import pandas as pd
from data_engine import fetch_macro_news
from discord_alerts import send_discord_message, format_portfolio_embed, send_personal_dm

def render_tab_overview(df_eval: pd.DataFrame, raw_portfolio: list):
    """Render Tab 1: Tổng quan danh mục, Bảng trạng thái, Cảnh báo Discord & Tin tức vĩ mô."""
    if df_eval is not None and not df_eval.empty:
        total_cost = (df_eval["Khối lượng"] * df_eval["Giá vốn (k)"] * 1000).sum()
        total_market = (df_eval["Khối lượng"] * df_eval["Thị giá (k)"] * 1000).sum()
        total_pnl_vnd = total_market - total_cost
        total_pnl_pct = (total_pnl_vnd / total_cost * 100) if total_cost > 0 else 0.0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Tổng vốn đầu tư", f"{total_cost:,.0f} đ")
        col2.metric("Tổng giá trị thị trường", f"{total_market:,.0f} đ")
        col3.metric("Lãi / Lỗ danh mục", f"{total_pnl_vnd:+,.0f} đ", f"{total_pnl_pct:+.2f}%")
        col4.metric("Số mã theo dõi", f"{len(df_eval)} mã")

        st.divider()

        # KHU VỰC BẮN CẢNH BÁO DISCORD
        st.markdown("### 🔔 Gửi Cảnh Báo Discord Ngay Lập Tức")
        col_dc1, col_dc2 = st.columns(2)

        with col_dc1:
            if st.button("📢 Bắn Cảnh Báo vào Kênh Discord (Webhook)", use_container_width=True):
                with st.spinner("Đang gửi báo cáo vào Kênh Discord..."):
                    from ai_analyst import generate_portfolio_analysis
                    news = fetch_macro_news()
                    ai_text = generate_portfolio_analysis(df_eval, news)
                    embed = format_portfolio_embed(df_eval, ai_text, report_type="CẢNH BÁO THỦ CÔNG TỪ DASHBOARD")
                    if send_discord_message(embeds=[embed]):
                        st.success("✅ Đã gửi báo cáo thành công vào Kênh Discord!")
                    else:
                        st.error("❌ Gửi thất bại, vui lòng kiểm tra lại Webhook trong file .env!")

        with col_dc2:
            if st.button("📩 Bắn Tin Nhắn Riêng vào Discord Của Bạn (DM Bot)", use_container_width=True):
                with st.spinner("Đang kết nối bot và gửi tin nhắn riêng cho bạn..."):
                    from ai_analyst import generate_portfolio_analysis
                    news = fetch_macro_news()
                    ai_text = generate_portfolio_analysis(df_eval, news)
                    summary_msg = f"📊 **BÁO CÁO NHANH DANH MỤC**\n- Tổng vốn: {total_cost:,.0f}đ\n- Thị giá: {total_market:,.0f}đ\n- Lãi/Lỗ: {total_pnl_vnd:+,.0f}đ ({total_pnl_pct:+.2f}%)\n\n🧠 **Nhận định AI:**\n{ai_text[:1200]}..."
                    if send_personal_dm(summary_msg):
                        st.success("✅ Bot đã gửi tin nhắn riêng (DM) vào Discord của bạn thành công!")
                    else:
                        st.error("❌ Gửi tin nhắn riêng thất bại. Vui lòng kiểm tra DISCORD_BOT_TOKEN và DISCORD_USER_ID trong file .env!")

        st.divider()

        # BẢNG TRẠNG THÁI CỔ PHIẾU
        st.subheader("📋 Bảng trạng thái cổ phiếu")
        st.dataframe(
            df_eval.style.format({
                "Giá vốn (k)": "{:.2f}",
                "Thị giá (k)": "{:.2f}",
                "Thay đổi (%)": "{:+.2f}%",
                "Lãi/Lỗ (%)": "{:+.2f}%",
                "Lãi/Lỗ (VND)": "{:+,.0f}",
                "Vol/TB20": "{:.2f}",
            }),
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        # TIN TỨC VĨ MÔ & NGÀNH NÓNG
        st.subheader("📰 Tin tức Vĩ mô & Ngành nóng")
        news = fetch_macro_news()
        cols = st.columns(3)
        for i, item in enumerate(news[:6]):
            with cols[i % 3]:
                st.markdown(f"**[{item['keyword'].upper()}]** [{item['title']}]({item['link']})")
    else:
        st.warning("Danh mục hiện đang trống! Hãy thêm mã ở tab 'Quản lý Danh mục'.")
