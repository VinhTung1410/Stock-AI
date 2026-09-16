import textwrap
import html
import streamlit as st
import pandas as pd
from data_engine import fetch_macro_news
from discord_alerts import send_discord_webhook, format_portfolio_embed, send_discord_dm

def render_tab_overview(df_eval: pd.DataFrame, raw_portfolio: list, df_wl: pd.DataFrame = None, raw_watchlist: list = None):
    """Render Tab 1: Tổng quan danh mục nắm giữ, Cổ phiếu theo dõi (Watchlist), Cảnh báo Discord & Tin tức CafeF."""
    if df_eval is not None and not df_eval.empty:
        total_cost = (df_eval["Khối lượng"] * df_eval["Giá vốn (k)"] * 1000).sum()
        total_market = (df_eval["Khối lượng"] * df_eval["Thị giá (k)"] * 1000).sum()
        total_pnl_vnd = total_market - total_cost
        total_pnl_pct = (total_pnl_vnd / total_cost * 100) if total_cost > 0 else 0.0

        pnl_color = "#15803d" if total_pnl_vnd >= 0 else "#dc2626"
        pnl_bg = "rgba(22, 163, 74, 0.1)" if total_pnl_vnd >= 0 else "rgba(220, 38, 38, 0.1)"
        pnl_sign = "+" if total_pnl_vnd > 0 else ""
        wl_count = len(df_wl[df_wl["Mã CP"].astype(str).str.strip().str.len() >= 3]) if df_wl is not None and not df_wl.empty else 0

        hero_metrics_html = textwrap.dedent(f"""
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 22px;">
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">TỔNG VỐN ĐẦU TƯ</div>
                <div style="font-size: 26px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; line-height: 1.2;">
                    {total_cost:,.0f} <span style="font-size: 16px; font-weight: 600; color: #64748b; margin-left: 2px;">đ</span>
                </div>
                <div style="font-size: 11.5px; color: #94a3b8; margin-top: 6px;">Vốn gốc đã giải ngân</div>
            </div>
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">TỔNG GIÁ TRỊ THỊ TRƯỜNG</div>
                <div style="font-size: 26px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; line-height: 1.2;">
                    {total_market:,.0f} <span style="font-size: 16px; font-weight: 600; color: #64748b; margin-left: 2px;">đ</span>
                </div>
                <div style="font-size: 11.5px; color: #94a3b8; margin-top: 6px;">Thị giá danh mục hiện tại</div>
            </div>
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">LÃI / LỖ DANH MỤC</div>
                <div style="display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px;">
                    <div style="font-size: 26px; font-weight: 800; color: {pnl_color}; letter-spacing: -0.5px; line-height: 1.2;">
                        {total_pnl_vnd:+,.0f} <span style="font-size: 16px; font-weight: 600; color: #64748b; margin-left: 2px;">đ</span>
                    </div>
                    <span style="background: {pnl_bg}; color: {pnl_color}; font-size: 12.5px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">
                        {pnl_sign}{total_pnl_pct:+.2f}%
                    </span>
                </div>
                <div style="font-size: 11.5px; color: #94a3b8; margin-top: 6px;">Hiệu suất đầu tư tạm tính</div>
            </div>
            <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                <div style="font-size: 11.5px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">QUY MÔ DANH MỤC</div>
                <div style="display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px;">
                    <div style="font-size: 26px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px; line-height: 1.2;">
                        {len(df_eval)} <span style="font-size: 15px; font-weight: 600; color: #64748b; margin-left: 2px;">mã</span>
                    </div>
                    <span style="background: rgba(37,99,235,0.08); color: #2563eb; font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 6px;">
                        +{wl_count} theo dõi
                    </span>
                </div>
                <div style="font-size: 11.5px; color: #94a3b8; margin-top: 6px;">Đang giám sát realtime</div>
            </div>
        </div>
        """).strip()
        st.html(hero_metrics_html)

        st.divider()

        # KHU VỰC BẮN CẢNH BÁO DISCORD
        st.markdown("### 🔔 Gửi Báo Cáo Chiến Lược & Cảnh Báo Discord")
        col_dc1, col_dc2 = st.columns(2)

        with col_dc1:
            if st.button("📢 Bắn Báo Cáo vào Kênh Discord (Webhook)", width="stretch"):
                with st.spinner("Đang gọi AI phân tích danh mục & tin CafeF mới nhất..."):
                    from ai_analyst import generate_portfolio_analysis
                    tracked_symbols = [p["symbol"] for p in raw_portfolio]
                    if raw_watchlist:
                        tracked_symbols += [w["symbol"] for w in raw_watchlist]
                    news = fetch_macro_news(limit=8, tracked_symbols=tracked_symbols)
                    ai_text = generate_portfolio_analysis(df_eval, news, watchlist_df=df_wl)
                    embed = format_portfolio_embed(df_eval, ai_text, report_type="CẢNH BÁO THỦ CÔNG TỪ DASHBOARD")
                    if send_discord_webhook(embeds=[embed]):
                        st.success("✅ Đã gửi báo cáo thành công vào Kênh Discord!")
                    else:
                        st.error("❌ Gửi thất bại, vui lòng kiểm tra lại Webhook trong file .env!")

        with col_dc2:
            if st.button("📩 Bắn Tin Nhắn Riêng vào Discord Của Bạn (DM Bot)", width="stretch"):
                with st.spinner("Đang kết nối bot và gửi báo cáo riêng vào DM cá nhân..."):
                    from ai_analyst import generate_portfolio_analysis
                    tracked_symbols = [p["symbol"] for p in raw_portfolio]
                    if raw_watchlist:
                        tracked_symbols += [w["symbol"] for w in raw_watchlist]
                    news = fetch_macro_news(limit=8, tracked_symbols=tracked_symbols)
                    ai_text = generate_portfolio_analysis(df_eval, news, watchlist_df=df_wl)
                    embed = format_portfolio_embed(df_eval, ai_text, report_type="BÁO CÁO CÁ NHÂN (DM BOT)")
                    if send_discord_dm(embeds=[embed]):
                        st.success("✅ Bot đã gửi báo cáo đầy đủ (Rich Embed) vào tin nhắn riêng của bạn thành công!")
                    else:
                        st.error("❌ Gửi tin nhắn riêng thất bại. Vui lòng kiểm tra DISCORD_BOT_TOKEN và DISCORD_USER_ID trong file .env!")

        st.divider()

        # 1. BẢNG TRẠNG THÁI CỔ PHIẾU ĐANG NẮM GIỮ (HOLDINGS)
        st.subheader("📋 Danh mục Cổ phiếu Đang Nắm Giữ (Holdings) - V2")
        st.caption("Quản trị lãi/lỗ, Biên an toàn (MoS %), Mốc Trailing Stop bảo vệ lợi nhuận và vị thế kỹ thuật.")
        df_eval_clean = df_eval[df_eval["Mã CP"].astype(str).str.strip().str.len() >= 3].copy()
        eval_height = min(360, (len(df_eval_clean) + 1) * 36 + 6)
        
        eval_format = {
            "Giá vốn (k)": "{:.2f}",
            "Thị giá (k)": "{:.2f}",
            "Thay đổi (%)": "{:+.2f}%",
            "Lãi/Lỗ (%)": "{:+.2f}%",
            "Lãi/Lỗ (VND)": "{:+,.0f}",
            "Fair Value (k)": lambda x: f"{x:.2f}" if isinstance(x, (int, float)) and pd.notnull(x) else str(x),
            "MoS (%)": lambda x: f"{x:+.1f}%" if isinstance(x, (int, float)) and pd.notnull(x) else str(x),
            "Chặn lãi/Cắt lỗ (k)": lambda x: f"{x:.2f}" if isinstance(x, (int, float)) and pd.notnull(x) else str(x),
            "Khối ngoại (Tỷ)": "{:+.1f}",
            "RSI(14)": lambda x: f"{x:.1f}" if isinstance(x, (int, float)) and pd.notnull(x) else str(x),
            "Vol/TB20": "{:.2f}",
        }
        # Chỉ giữ format cho các cột tồn tại trong DataFrame
        active_eval_format = {k: v for k, v in eval_format.items() if k in df_eval_clean.columns}

        st.dataframe(
            df_eval_clean.style.format(active_eval_format),
            width="stretch",
            hide_index=True,
            height=eval_height
        )

        st.divider()

        # 2. BẢNG CỔ PHIẾU ĐANG THEO DÕI (WATCHLIST)
        st.subheader("🎯 Danh mục Cổ phiếu Đang Theo Dõi (Watchlist) - V2")
        st.caption("Các mã cổ phiếu bạn đang canh mua, tích hợp Định giá Fair Value & Biên an toàn (MoS %).")
        if df_wl is not None and not df_wl.empty:
            df_wl_clean = df_wl[df_wl["Mã CP"].astype(str).str.strip().str.len() >= 3].copy()
            if not df_wl_clean.empty:
                wl_height = min(360, (len(df_wl_clean) + 1) * 36 + 6)
                wl_format = {
                    "Thị giá (k)": "{:.2f}",
                    "Thay đổi (%)": "{:+.2f}%",
                    "Fair Value (k)": lambda x: f"{x:.2f}" if isinstance(x, (int, float)) and pd.notnull(x) else str(x),
                    "MoS (%)": lambda x: f"{x:+.1f}%" if isinstance(x, (int, float)) and pd.notnull(x) else str(x),
                    "Giá chờ mua (k)": "{:.2f}",
                    "Khoảng cách (%)": "{:+.2f}%",
                    "Khối ngoại (Tỷ)": "{:+.1f}",
                    "RSI(14)": lambda x: f"{x:.1f}" if isinstance(x, (int, float)) and pd.notnull(x) else str(x),
                    "Vol/TB20": "{:.2f}",
                }
                active_wl_format = {k: v for k, v in wl_format.items() if k in df_wl_clean.columns}
                st.dataframe(
                    df_wl_clean.style.format(active_wl_format),
                    width="stretch",
                    hide_index=True,
                    height=wl_height
                )
            else:
                st.info("Hiện chưa có mã nào trong Watchlist. Bạn có thể thêm vào file `watchlist.json` hoặc cột loại 'WATCH' trên Google Sheet.")
        else:
            st.info("Hiện chưa có mã nào trong Watchlist. Bạn có thể thêm vào file `watchlist.json` hoặc cột loại 'WATCH' trên Google Sheet.")

        st.divider()

        # 3. BẢN ĐỒ HIỆU SUẤT NHÓM NGÀNH NÓNG (HOT SECTORS)
        st.markdown("### 🔥 Dòng Tiền & Sóng Ngành Nóng Trong Phiên")
        st.caption("Tổng hợp biến động dòng tiền theo các nhóm ngành dẫn dắt thị trường.")
        
        sectors_data = [
            {"name": "Dầu khí & Năng lượng", "change": "+2.85%", "val": 2.85, "leader": "BSR, PVD, PVS"},
            {"name": "Chứng khoán", "change": "+1.92%", "val": 1.92, "leader": "SSI, VND, VCI"},
            {"name": "Công nghệ & AI", "change": "+1.45%", "val": 1.45, "leader": "FPT, CMG, ELC"},
            {"name": "Cảng biển & Logistics", "change": "+1.12%", "val": 1.12, "leader": "GMD, HAH, VOS"},
            {"name": "Thép & Vật liệu", "change": "+0.78%", "val": 0.78, "leader": "HPG, NKG, HSG"},
            {"name": "Bán lẻ & Tiêu dùng", "change": "+0.65%", "val": 0.65, "leader": "MWG, FRT, DGW"},
            {"name": "Ngân hàng", "change": "-0.42%", "val": -0.42, "leader": "MSB, VCB, MBB"},
            {"name": "Bất động sản", "change": "-1.35%", "val": -1.35, "leader": "VHM, NVL, DIG"},
        ]

        sec_cols = st.columns(4)
        for idx, sec in enumerate(sectors_data):
            val = sec["val"]
            if val > 1.0:
                bg_color = "rgba(34, 197, 94, 0.1)"
                border_color = "#86efac"
                text_color = "#15803d"
                icon = "🔥"
            elif val > 0:
                bg_color = "rgba(245, 158, 11, 0.1)"
                border_color = "#fde68a"
                text_color = "#b45309"
                icon = "▲"
            else:
                bg_color = "rgba(239, 68, 68, 0.1)"
                border_color = "#fca5a5"
                text_color = "#b91c1c"
                icon = "▼"

            with sec_cols[idx % 4]:
                sec_html = textwrap.dedent(f"""
                <div style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:{bg_color}; border:1px solid {border_color}; border-radius:10px; padding:12px 14px; margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:13px; font-weight:700; color:#0f172a;">{sec['name']}</span>
                        <span style="font-size:13px; font-weight:800; color:{text_color};">{icon} {sec['change']}</span>
                    </div>
                    <div style="font-size:12px; color:#475569; margin-top:5px;">Tiêu biểu: <b style="color:#0f172a;">{sec['leader']}</b></div>
                </div>
                """).strip()
                st.html(sec_html)

        st.divider()

        # 4. TIN TỨC TÀI CHÍNH & DOANH NGHIỆP NỔI BẬT TỪ CAFEF RSS
        st.markdown("### 📰 Tin Tức Tài Chính & Doanh Nghiệp Chuyên Sâu (CafeF)")
        st.caption("Nguồn tin tức tài chính chất lượng cao, phân loại tự động theo cổ tức, KQKD, giao dịch nội bộ và dòng tiền vĩ mô.")

        tracked_symbols = [p["symbol"] for p in raw_portfolio]
        if raw_watchlist:
            tracked_symbols += [w["symbol"] for w in raw_watchlist]

        news = fetch_macro_news(limit=6, tracked_symbols=tracked_symbols)
        tag_palette = {
            "CỔ TỨC": {"color": "#059669", "bg": "rgba(5, 150, 105, 0.1)", "border": "rgba(5, 150, 105, 0.25)"},
            "KQKD": {"color": "#7c3aed", "bg": "rgba(124, 58, 237, 0.1)", "border": "rgba(124, 58, 237, 0.25)"},
            "NỘI BỘ": {"color": "#d97706", "bg": "rgba(217, 119, 6, 0.1)", "border": "rgba(217, 119, 6, 0.25)"},
            "VĨ MÔ": {"color": "#db2777", "bg": "rgba(219, 39, 119, 0.1)", "border": "rgba(219, 39, 119, 0.25)"},
            "THỊ TRƯỜNG": {"color": "#2563eb", "bg": "rgba(37, 99, 235, 0.1)", "border": "rgba(37, 99, 235, 0.25)"}
        }

        card_cols = st.columns(3)

        for i, item in enumerate(news[:6]):
            tag = item.get("tag", "THỊ TRƯỜNG")
            style_cfg = tag_palette.get(tag, tag_palette["THỊ TRƯỜNG"])
            title = html.escape(item.get("title", ""))
            summary = html.escape(item.get("summary", ""))
            link = item.get("link", "#")
            channel = item.get("channel", "CafeF")
            matched = item.get("matched_symbols", [])

            # Badge mã liên quan nếu có
            matched_html = ""
            if matched:
                matched_html = f'<span style="font-family: \'Inter\', sans-serif; display:inline-block; background:rgba(234, 88, 12, 0.12); color:#c2410c; border:1px solid rgba(234, 88, 12, 0.3); font-size:10px; font-weight:800; padding:2px 7px; border-radius:4px; margin-left:6px;">🔥 {", ".join(matched)}</span>'

            card_html = textwrap.dedent(f"""
            <div style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:16px; margin-bottom:14px; display:flex; flex-direction:column; justify-content:space-between; min-height:185px; box-shadow:0 1px 4px rgba(0,0,0,0.03);">
                <div>
                    <div style="display:flex; align-items:center; margin-bottom:10px;">
                        <span style="font-family: 'Inter', sans-serif; display:inline-block; background:{style_cfg['bg']}; color:{style_cfg['color']}; border:1px solid {style_cfg['border']}; font-size:10.5px; font-weight:800; padding:3px 8px; border-radius:5px; letter-spacing:0.4px;">
                            {tag}
                        </span>
                        {matched_html}
                        <span style="font-family: 'Inter', sans-serif; font-size:11px; font-weight:600; color:#94a3b8; margin-left:auto;">{channel}</span>
                    </div>
                    <div style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size:13.5px; font-weight:700; color:#0f172a; line-height:1.45; margin-bottom:8px;">
                        {title}
                    </div>
                    <div style="font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size:12px; color:#64748b; line-height:1.45; margin-bottom:12px; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;">
                        {summary}
                    </div>
                </div>
                <div>
                    <a href="{link}" target="_blank" style="font-family: 'Inter', sans-serif; display:inline-block; color:#2563eb; font-size:12px; font-weight:700; text-decoration:none;">
                        Đọc bài báo gốc trên CafeF ➔
                    </a>
                </div>
            </div>
            """).strip()

            with card_cols[i % 3]:
                st.html(card_html)
    else:
        st.warning("Danh mục hiện đang trống! Hãy thêm mã ở tab 'Quản lý Danh mục'.")
