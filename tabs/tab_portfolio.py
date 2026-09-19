import os

import pandas as pd
import streamlit as st

from data_engine import save_portfolio, save_watchlist, update_google_sheet_portfolio, update_google_sheet_watchlist


def render_tab_portfolio(raw_portfolio: list, raw_watchlist: list = None):
    """Render Tab 4: Quản lý và chỉnh sửa danh mục nắm giữ & watchlist trực tiếp, đồng bộ 2 chiều với Google Sheets."""
    st.subheader("✏️ Quản lý & Chỉnh sửa Danh mục Đầu tư & Theo dõi")
    st.caption("Bạn có thể thêm/xóa dòng, sửa mã, giá vốn hoặc giá canh mua trực tiếp trên giao diện rồi nhấn Lưu.")

    # Hiển thị thông báo kết quả sau rerun
    if "portfolio_toast" in st.session_state:
        st.toast(st.session_state.pop("portfolio_toast"), icon="✅")
    if "portfolio_alert_success" in st.session_state:
        st.success(st.session_state.pop("portfolio_alert_success"))
    if "portfolio_alert_error" in st.session_state:
        st.error(st.session_state.pop("portfolio_alert_error"))

    sheet_url = os.environ.get("GOOGLE_SHEET_URL", "").strip()
    update_url = os.environ.get("GOOGLE_SHEET_UPDATE_URL", "").strip()

    if sheet_url:
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            if update_url:
                st.success("🟢 **Đồng bộ 2 chiều đã kích hoạt:** Mọi thay đổi khi bấm Lưu sẽ tự động cập nhật trực tiếp lên Google Sheet (cả Sheet 1 và Sheet 2)!")
            else:
                st.warning("⚠️ **Google Sheet đang ở chế độ Chỉ Đọc:** Chưa cấu hình GOOGLE_SHEET_UPDATE_URL nên nút Lưu chưa thể ghi đè lên Google Sheet.")
        with col_s2:
            st.link_button("🔗 Mở Google Sheet", sheet_url, width="stretch")

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
        width="stretch",
        height=p_height,
        key="editor_portfolio",
        column_config={
            "symbol": st.column_config.TextColumn("Mã CP", required=True, help="Nhập mã 3 ký tự (Ví dụ: FPT, HPG, SSI...)"),
            "volume": st.column_config.NumberColumn("Số lượng", min_value=0, step=10, required=True, help="Khối lượng cổ phiếu nắm giữ"),
            "cost_price": st.column_config.NumberColumn("Giá vốn (k)", min_value=0.0, step=0.05, format="%.2f", required=True, help="Giá vốn tính theo nghìn đồng (k)"),
            "note": st.column_config.TextColumn("Ghi chú / Nhóm ngành", help="Ghi chú hoặc phân loại ngành"),
        }
    )

    if st.button("💾 Lưu Danh mục Nắm Giữ (Sheet 1)", type="primary"):
        new_portfolio = []
        for r in edited_p_df.to_dict(orient="records"):
            sym = str(r.get("symbol", "")).strip().upper()
            if not sym or sym in ["NAN", "NONE", "NULL"]:
                continue

            # Xử lý an toàn khối lượng (tránh NaN)
            raw_vol = r.get("volume")
            try:
                if raw_vol is not None and not pd.isna(raw_vol) and str(raw_vol).strip().lower() != "nan":
                    volume = max(0, int(float(raw_vol)))
                else:
                    volume = 0
            except:
                volume = 0

            # Xử lý an toàn giá vốn (tránh float nan)
            raw_cost = r.get("cost_price")
            try:
                if raw_cost is not None and not pd.isna(raw_cost) and str(raw_cost).strip().lower() != "nan":
                    cost_price = round(float(raw_cost), 2)
                else:
                    cost_price = 0.0
            except:
                cost_price = 0.0

            # Xử lý an toàn ghi chú
            raw_note = r.get("note")
            note = "" if (raw_note is None or pd.isna(raw_note) or str(raw_note).strip().lower() == "nan") else str(raw_note).strip()

            new_portfolio.append({
                "symbol": sym,
                "volume": volume,
                "cost_price": cost_price,
                "note": note
            })

        save_portfolio(new_portfolio)

        # Xóa cache widget data editor để nạp lại dữ liệu sạch
        if "editor_portfolio" in st.session_state:
            del st.session_state["editor_portfolio"]

        st.cache_data.clear()

        if update_url:
            with st.spinner("Đang đồng bộ dữ liệu lên Google Sheet (Sheet 1)..."):
                ok, msg = update_google_sheet_portfolio(new_portfolio)
            if ok:
                st.session_state["portfolio_toast"] = "Đã đồng bộ Danh mục lên Google Sheet!"
                st.session_state["portfolio_alert_success"] = "✅ Đã lưu và đồng bộ Danh mục thành công lên Sheet 1 của Google Sheet!"
            else:
                st.session_state["portfolio_alert_error"] = f"❌ Không thể đồng bộ lên Google Sheet: {msg}. Hãy thử lại hoặc kiểm tra Apps Script."
        elif sheet_url:
            st.session_state["portfolio_alert_error"] = "⚠️ Chưa cấu hình GOOGLE_SHEET_UPDATE_URL! Dữ liệu chưa thể ghi lên Google Sheet."
        else:
            st.session_state["portfolio_alert_success"] = "✅ Đã cập nhật Danh mục nắm giữ thành công!"

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
        width="stretch",
        height=wl_height,
        key="editor_watchlist",
        column_config={
            "symbol": st.column_config.TextColumn("Mã CP", required=True, help="Nhập mã 3 ký tự canh mua (Ví dụ: VHM, MWG...)"),
            "target_buy": st.column_config.NumberColumn("Giá canh mua (k)", min_value=0.0, step=0.05, format="%.2f", help="Vùng giá hỗ trợ muốn canh giải ngân"),
            "note": st.column_config.TextColumn("Câu chuyện / Lý do theo dõi", help="Luận điểm đầu tư hoặc chất xúc tác"),
        }
    )

    if st.button("💾 Lưu Danh mục Theo Dõi (Sheet 2)", type="primary"):
        new_watchlist = []
        for r in edited_wl_df.to_dict(orient="records"):
            sym = str(r.get("symbol", "")).strip().upper()
            if not sym or sym in ["NAN", "NONE", "NULL"]:
                continue

            # Xử lý an toàn giá canh mua (tránh float nan)
            raw_target = r.get("target_buy")
            try:
                if raw_target is not None and not pd.isna(raw_target) and str(raw_target).strip().lower() != "nan":
                    target_buy = round(float(raw_target), 2)
                else:
                    target_buy = 0.0
            except:
                target_buy = 0.0

            # Xử lý an toàn ghi chú
            raw_note = r.get("note")
            note = "" if (raw_note is None or pd.isna(raw_note) or str(raw_note).strip().lower() == "nan") else str(raw_note).strip()

            new_watchlist.append({
                "symbol": sym,
                "target_buy": target_buy,
                "note": note
            })

        save_watchlist(new_watchlist)

        # Xóa cache widget data editor để nạp lại dữ liệu sạch
        if "editor_watchlist" in st.session_state:
            del st.session_state["editor_watchlist"]

        st.cache_data.clear()

        if update_url:
            with st.spinner("Đang đồng bộ Watchlist lên Google Sheet (Sheet 2)..."):
                ok, msg = update_google_sheet_watchlist(new_watchlist)
            if ok:
                st.session_state["portfolio_toast"] = "Đã đồng bộ Watchlist lên Google Sheet!"
                st.session_state["portfolio_alert_success"] = "✅ Đã lưu và đồng bộ Watchlist thành công lên Sheet 2 của Google Sheet!"
            else:
                st.session_state["portfolio_alert_error"] = f"❌ Không thể đồng bộ Watchlist lên Google Sheet: {msg}."
        elif sheet_url:
            st.session_state["portfolio_alert_error"] = "⚠️ Chưa cấu hình GOOGLE_SHEET_UPDATE_URL! Watchlist chưa thể ghi lên Google Sheet."
        else:
            st.session_state["portfolio_alert_success"] = "✅ Đã cập nhật Watchlist thành công!"

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

