import streamlit as st
import pandas as pd
from data_engine import save_portfolio

def render_tab_portfolio(raw_portfolio: list):
    """Render Tab 4: Quản lý và chỉnh sửa danh mục trực tiếp."""
    st.subheader("✏️ Chỉnh sửa Danh mục Trực tiếp")
    st.caption("Bạn có thể thêm dòng mới, sửa mã, khối lượng hoặc giá vốn trực tiếp trên bảng bên dưới rồi nhấn Lưu.")
    
    df_raw = pd.DataFrame(raw_portfolio)
    edited_df = st.data_editor(
        df_raw,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "symbol": st.column_config.TextColumn("Mã CP", required=True),
            "volume": st.column_config.NumberColumn("Số lượng", min_value=1, step=10, required=True),
            "cost_price": st.column_config.NumberColumn("Giá vốn (k)", min_value=0.1, step=0.05, format="%.2f", required=True),
            "note": st.column_config.TextColumn("Ghi chú / Nhóm ngành"),
        }
    )

    if st.button("💾 Lưu thay đổi Danh mục", type="primary"):
        new_portfolio = edited_df.to_dict(orient="records")
        save_portfolio(new_portfolio)
        st.cache_data.clear()
        st.success("✅ Đã cập nhật danh mục thành công!")
        st.rerun()
