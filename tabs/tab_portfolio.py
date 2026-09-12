import os
import streamlit as st
import pandas as pd
from data_engine import save_portfolio, save_watchlist, update_google_sheet_portfolio, update_google_sheet_watchlist

def render_tab_portfolio(raw_portfolio: list, raw_watchlist: list = None):
    """Render Tab 4: Quản lý và chỉnh sửa danh mục nắm giữ & watchlist trực tiếp, đồng bộ 2 chiều với Google Sheets."""
    st.subheader("✏️ Quản lý & Chỉnh sửa Danh mục Đầu tư & Theo dõi")
    st.caption("Bạn có thể thêm/xóa dòng, sửa mã, giá vốn hoặc giá canh mua trực tiếp trên giao diện rồi nhấn Lưu.")

    sheet_url = os.environ.get("GOOGLE_SHEET_URL", "").strip()
    update_url = os.environ.get("GOOGLE_SHEET_UPDATE_URL", "").strip()

    if sheet_url:
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            if update_url:
                st.success("🟢 **Đồng bộ 2 chiều đã kích hoạt:** Mọi thay đổi khi bấm Lưu sẽ tự động cập nhật trực tiếp lên Google Sheet (cả Sheet 1 và Sheet 2)!")
            else:
                st.info("📊 **Google Sheet đã kết nối (Chế độ đọc tự động).** Cả Sheet 1 (Danh mục) và Sheet 2 (Watchlist) đang được đồng bộ thời gian thực.")
        with col_s2:
            st.link_button("🔗 Mở Google Sheet", sheet_url, use_container_width=True)

    # ==========================================
    # PHẦN 1: QUẢN LÝ CỔ PHIẾU NẮM GIỮ (HOLDINGS)
    # ==========================================
    st.markdown("#### 📋 1. Danh mục Cổ phiếu Đang Nắm Giữ (Holdings - Trang tính 1)")
    valid_p = [p for p in raw_portfolio if p.get("symbol") and str(p["symbol"]).strip()] if raw_portfolio else []
    df_raw = pd.DataFrame(valid_p) if valid_p else pd.DataFrame(columns=["symbol", "volume", "cost_price", "note"])
    p_height = min(360, (len(df_raw) + 2) * 36 + 10)

    edited_p_df = st.data_editor(
        df_raw,
        num_rows="dynamic",
        use_container_width=True,
        height=p_height,
        key="editor_portfolio",
        column_config={
            "symbol": st.column_config.TextColumn("Mã CP", required=True, placeholder="+ Nhập mã (FPT, HPG...)"),
            "volume": st.column_config.NumberColumn("Số lượng", min_value=0, step=10, required=True, placeholder="100"),
            "cost_price": st.column_config.NumberColumn("Giá vốn (k)", min_value=0.0, step=0.05, format="%.2f", required=True, placeholder="25.50"),
            "note": st.column_config.TextColumn("Ghi chú / Nhóm ngành", placeholder="+ Thêm ghi chú..."),
        }
    )

    if st.button("💾 Lưu Danh mục Nắm Giữ (Sheet 1)", type="primary"):
        new_portfolio = edited_p_df.to_dict(orient="records")
        # Chuẩn hóa mã viết hoa
        for p in new_portfolio:
            p["symbol"] = str(p.get("symbol", "")).strip().upper()
        new_portfolio = [p for p in new_portfolio if p["symbol"] and p["symbol"] != "NAN"]

        save_portfolio(new_portfolio)
        synced_sheet = False
        if update_url:
            synced_sheet = update_google_sheet_portfolio(new_portfolio)

        st.cache_data.clear()
        if synced_sheet:
            st.success("✅ Đã lưu và đồng bộ Danh mục thành công lên Sheet 1 của Google Sheet!")
        else:
            st.success("✅ Đã cập nhật Danh mục nắm giữ thành công!")
        st.rerun()

    st.divider()

    # ==========================================
    # PHẦN 2: QUẢN LÝ CỔ PHIẾU THEO DÕI (WATCHLIST)
    # ==========================================
    st.markdown("#### 🎯 2. Danh mục Cổ phiếu Đang Theo Dõi (Watchlist - Trang tính 2)")
    st.caption("Các mã bạn canh mua. Bot sẽ quét tín hiệu kỹ thuật & tin tức CafeF để gửi DM cảnh báo khi có điểm mua an toàn.")
    valid_wl = [w for w in raw_watchlist if w.get("symbol") and str(w["symbol"]).strip()] if raw_watchlist else []
    df_wl_raw = pd.DataFrame(valid_wl) if valid_wl else pd.DataFrame(columns=["symbol", "target_buy", "note"])
    wl_height = min(360, (len(df_wl_raw) + 2) * 36 + 10)

    edited_wl_df = st.data_editor(
        df_wl_raw,
        num_rows="dynamic",
        use_container_width=True,
        height=wl_height,
        key="editor_watchlist",
        column_config={
            "symbol": st.column_config.TextColumn("Mã CP", required=True, placeholder="+ Nhập mã canh mua..."),
            "target_buy": st.column_config.NumberColumn("Giá canh mua (k)", min_value=0.0, step=0.05, format="%.2f", placeholder="28.50"),
            "note": st.column_config.TextColumn("Câu chuyện / Lý do theo dõi", placeholder="+ Lý do / điểm mua..."),
        }
    )

    if st.button("💾 Lưu Danh mục Theo Dõi (Sheet 2)", type="primary"):
        new_watchlist = edited_wl_df.to_dict(orient="records")
        for w in new_watchlist:
            w["symbol"] = str(w.get("symbol", "")).strip().upper()
        new_watchlist = [w for w in new_watchlist if w["symbol"]]

        save_watchlist(new_watchlist)
        synced_sheet = False
        if update_url:
            synced_sheet = update_google_sheet_watchlist(new_watchlist)

        st.cache_data.clear()
        if synced_sheet:
            st.success("✅ Đã lưu và đồng bộ Watchlist thành công lên Sheet 2 của Google Sheet!")
        else:
            st.success("✅ Đã cập nhật Watchlist thành công!")
        st.rerun()

    # Hướng dẫn kích hoạt ghi ngược 2 chiều
    if sheet_url and not update_url:
        with st.expander("⚡ Hướng dẫn kích hoạt sửa trực tiếp từ Web Dashboard lên Google Sheet (1 phút)"):
            st.markdown("""
            Để khi bạn nhấn nút **"Lưu"** trên Dashboard thì Google Sheet của bạn tự động cập nhật ngay lập tức:
            1. Mở file Google Sheet của bạn, trên thanh menu bấm: **Tiện ích mở rộng (Extensions) ➔ Apps Script**.
            2. Xóa hết code cũ và dán đoạn code này vào (hỗ trợ tự động cả Sheet 1 Danh mục & Sheet 2 Watchlist):
            ```javascript
            function doPost(e) {
              var ss = SpreadsheetApp.getActiveSpreadsheet();
              var payload = JSON.parse(e.postData.contents);

              if (payload.type === "watchlist") {
                // Ghi vào Sheet thứ 2
                var sheets = ss.getSheets();
                var sheet2 = sheets.length > 1 ? sheets[1] : ss.insertSheet("Watchlist");
                sheet2.clear();
                sheet2.appendRow(["Mã CP", "Giá canh mua", "Câu chuyện / Ghi chú"]);
                var items = payload.data || [];
                for (var i = 0; i < items.length; i++) {
                  sheet2.appendRow([items[i].symbol, items[i].target_buy || "", items[i].note || ""]);
                }
              } else {
                // Ghi vào Sheet thứ 1 (Danh mục)
                var sheet1 = ss.getSheets()[0];
                sheet1.clear();
                sheet1.appendRow(["Mã CP", "Khối lượng", "Giá vốn", "Ghi chú"]);
                var items = Array.isArray(payload) ? payload : (payload.data || []);
                for (var i = 0; i < items.length; i++) {
                  sheet1.appendRow([items[i].symbol, items[i].volume, items[i].cost_price, items[i].note || ""]);
                }
              }
              return ContentService.createTextOutput("SUCCESS");
            }
            ```
            3. Nhấn nút **Triển khai (Deploy)** ở góc trên bên phải ➔ Chọn **Triển khai mới (New Deployment)**:
               - Chọn loại: **Ứng dụng web (Web App)**.
               - Thực thi dưới dạng: **Tôi (Me)**.
               - Ai có quyền truy cập: **Bất kỳ ai (Anyone)**.
               - Bấm **Triển khai** và copy **URL ứng dụng web**.
            4. Dán URL đó vào file `.env`: `GOOGLE_SHEET_UPDATE_URL="<URL_VỪA_COPY>"` là hoàn tất!
            """)

