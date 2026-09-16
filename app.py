import os
os.environ["VNSTOCK_TELEMETRY"] = "off"
import streamlit as st
from dotenv import load_dotenv

from data_engine import (
    load_portfolio, 
    evaluate_portfolio, 
    load_watchlist, 
    evaluate_watchlist, 
    get_vnindex_valuation_data,
    _GSHEET_CACHE
)
from tabs import (
    render_tab_overview,
    render_tab_market,
    render_tab_charts,
    render_tab_portfolio,
    render_tab_ai,
    render_tab_alpha_tracker,
)

load_dotenv()

# Cấu hình trang Dashboard
st.set_page_config(
    page_title="AI Stock Copilot - Quản trị & Định giá Thị trường",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# HỆ THỐNG DESIGN SYSTEM & CUSTOM CSS (FINTECH PRO UI)
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* 1. TYPOGRAPHY & BẢO VỆ FONT ICON (TRÁNH LỖI HIỂN THỊ CHỮ keyboard_double) */
    html, body {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        color: #0f172a;
    }

    /* Các thẻ văn bản thông thường */
    p, h1, h2, h3, h4, h5, h6, label, input, textarea, select {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }

    /* BẢO VỆ FONT ICON MATERIAL: Tuyệt đối không để font Inter ghi đè lên icon */
    [data-testid="stIconMaterial"],
    [data-testid="stSidebarCollapseButton"] *,
    button[kind="header"] *,
    [data-testid="stBaseButton-header"] *,
    .material-symbols-rounded,
    .material-symbols-outlined,
    .material-icons,
    [class*="material-symbols"],
    [class*="stIcon"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
        font-weight: normal !important;
        font-style: normal !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        display: inline-block !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        direction: ltr !important;
    }

    /* 2. THANH ĐIỀU HƯỚNG TABS (LAZY LOADING VIA ST.RADIO - BRAND BLUE #2563eb) */
    div[data-baseweb="tab-list"] {
        gap: 8px !important;
        border-bottom: 2px solid #e2e8f0 !important;
        padding-bottom: 0px !important;
        background: transparent !important;
    }

    /* Thanh điều hướng Lazy Loading Radio Group: Tự động đổi dáng thành Tab Bar 100% */
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 8px !important;
        border-bottom: 2px solid #e2e8f0 !important;
        padding-bottom: 0px !important;
        margin-bottom: 20px !important;
        background: transparent !important;
    }

    div[data-testid="stRadio"] > div[role="radiogroup"] > label {
        padding: 10px 18px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        color: #64748b !important;
        border: none !important;
        border-bottom: 2.5px solid transparent !important;
        margin-bottom: -2px !important;
        background: transparent !important;
        border-radius: 6px 6px 0 0 !important;
        cursor: pointer !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
        color: #1e293b !important;
        background: rgba(241, 245, 249, 0.6) !important;
    }

    /* Ẩn dấu chấm tròn radio mặc định */
    div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }

    /* Tab đang Active: Màu Xanh thương hiệu đồng nhất với Primary Buttons */
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
        border-bottom: 2.5px solid #2563eb !important;
        background: transparent !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p,
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) span {
        color: #2563eb !important;
        font-weight: 700 !important;
    }

    button[data-baseweb="tab"] {
        padding: 10px 18px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        color: #64748b !important;
        border: none !important;
        border-bottom: 2.5px solid transparent !important;
        margin-bottom: -2px !important;
        background: transparent !important;
        border-radius: 6px 6px 0 0 !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    button[data-baseweb="tab"]:hover {
        color: #1e293b !important;
        background: rgba(241, 245, 249, 0.6) !important;
    }

    /* Tab đang Active: Màu Xanh thương hiệu đồng nhất với Primary Buttons */
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #2563eb !important;
        border-bottom: 2.5px solid #2563eb !important;
        background: transparent !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] p,
    button[data-baseweb="tab"][aria-selected="true"] span {
        color: #2563eb !important;
        font-weight: 700 !important;
    }

    /* Vạch gạch chân chuyển động của Streamlit: Ép buộc 100% về Brand Blue */
    div[data-baseweb="tab-highlight"] {
        background-color: #2563eb !important;
        height: 2.5px !important;
        border-radius: 2px 2px 0 0 !important;
    }
    div[data-baseweb="tab-border"] {
        background-color: transparent !important;
    }

    /* Nút mũi tên cuộn Tab (< và >): Có nền trắng và bóng đổ, không đè lên chữ */
    div[data-testid="stTabsOverflow"] button, button[data-testid="stBaseButton-header"] {
        background-color: #ffffff !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12) !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
        z-index: 20 !important;
        padding: 4px 8px !important;
        margin: 0 4px !important;
    }

    /* 3. NÚT BẤM HÀNH ĐỘNG CHÍNH (PRIMARY BUTTON: NỀN XANH SÁNG #2563eb, CHỮ TRẮNG SẮC NÉT #ffffff) */
    button[kind="primary"], 
    button[data-testid="baseButton-primary"] {
        background: #2563eb !important;
        border: 1px solid #1d4ed8 !important;
        border-radius: 8px !important;
        padding: 9px 20px !important;
        box-shadow: 0 2px 4px rgba(37, 99, 235, 0.25) !important;
        transition: all 0.2s ease !important;
    }

    /* Chữ bên trong nút Primary LUÔN LUÔN TRẮNG TINH (Tuyệt đối không bị chữ đen làm chìm) */
    button[kind="primary"] *,
    button[data-testid="baseButton-primary"] *,
    button[kind="primary"] p,
    button[data-testid="baseButton-primary"] p,
    button[kind="primary"] span,
    button[data-testid="baseButton-primary"] span {
        color: #ffffff !important;
        font-weight: 700 !important;
        letter-spacing: 0.2px !important;
    }

    button[kind="primary"]:hover, 
    button[data-testid="baseButton-primary"]:hover {
        background: #1d4ed8 !important;
        border-color: #1e40af !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4) !important;
        transform: translateY(-1px) !important;
    }

    /* Nút phụ (Secondary Button): Nền trắng, viền rõ, chữ đậm không mờ */
    button[kind="secondary"], 
    button[data-testid="baseButton-secondary"] {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        padding: 8px 18px !important;
        transition: all 0.2s ease !important;
    }

    button[kind="secondary"] *,
    button[data-testid="baseButton-secondary"] *,
    button[kind="secondary"] p,
    button[data-testid="baseButton-secondary"] p {
        color: #1e293b !important;
        font-weight: 600 !important;
    }

    button[kind="secondary"]:hover, 
    button[data-testid="baseButton-secondary"]:hover {
        background: #f8fafc !important;
        border-color: #94a3b8 !important;
    }
    button[kind="secondary"]:hover p,
    button[data-testid="baseButton-secondary"]:hover p {
        color: #0f172a !important;
    }

    /* 4. ĐỒNG BỘ TUYỆT ĐỐI Ô NHẬP LIỆU & DROPDOWN SELECTBOX (CHÍNH XÁC TỪNG PIXEL) */
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"],
    div[data-baseweb="base-input"] {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        min-height: 42px !important;
        height: 42px !important;
        box-sizing: border-box !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    }

    div[data-baseweb="select"] > div:hover,
    div[data-baseweb="input"]:hover {
        border-color: #94a3b8 !important;
    }

    div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="textarea"]:focus-within {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16) !important;
        background-color: #ffffff !important;
    }

    div[data-baseweb="input"] input,
    div[data-baseweb="select"] input {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        font-size: 13.5px !important;
        color: #0f172a !important;
        height: 40px !important;
        line-height: 40px !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        background: transparent !important;
    }

    /* Đảm bảo Label của Widget đồng bộ in hoa, gọn gàng */
    label[data-testid="stWidgetLabel"] p {
        font-family: 'Inter', sans-serif !important;
        font-size: 12px !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.4px !important;
        color: #475569 !important;
        margin-bottom: 6px !important;
    }

    /* 5. BẢNG DỮ LIỆU (TABLE UI HEADER ĐẬM & HOVER EFFECT) */
    [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        overflow: hidden !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
    }
    [data-testid="stDataFrame"] th, [data-testid="stDataEditor"] th {
        font-weight: 700 !important;
        background-color: #f8fafc !important;
        color: #334155 !important;
        font-size: 13px !important;
    }

    /* 6. THẺ CHỈ SỐ METRIC CARDS (PADDING ĐỒNG ĐỀU, BO GÓC, SHADOW SANG TRỌNG) */
    [data-testid="stMetric"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
        transition: all 0.2s ease !important;
    }
    [data-testid="stMetric"]:hover {
        border-color: #cbd5e1 !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05) !important;
    }
    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {
        font-size: 11.5px !important;
        font-weight: 700 !important;
        color: #64748b !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 22px !important;
        font-weight: 800 !important;
        color: #0f172a !important;
        letter-spacing: -0.5px !important;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=180)
def get_cached_portfolio_eval():
    """Cache đánh giá danh mục trong 3 phút."""
    portfolio = load_portfolio()
    return evaluate_portfolio(portfolio), portfolio


@st.cache_data(ttl=180)
def get_cached_watchlist_eval():
    """Cache đánh giá danh mục theo dõi (Watchlist) trong 3 phút."""
    watchlist = load_watchlist()
    return evaluate_watchlist(watchlist), watchlist


@st.cache_data(ttl=1800)
def get_cached_vnindex_data():
    """Cache dữ liệu nến và bội số P/E, P/B của VN-Index trong 30 phút."""
    return get_vnindex_valuation_data()


# --- DỮ LIỆU ĐẦU VÀO ---
df_eval, raw_portfolio = get_cached_portfolio_eval()
df_wl, raw_watchlist = get_cached_watchlist_eval()


# --- SIDEBAR ĐIỀU KHIỂN (GOM NHÓM GESTALT CARD) ---
with st.sidebar:
    st.markdown("""
    <div style="padding: 12px 0 6px 0;">
        <h2 style="font-size: 19px; font-weight: 800; color: #0f172a; margin: 0;">AI Stock Copilot</h2>
        <div style="font-size: 12px; color: #64748b; margin-top: 2px;">Giám sát Danh mục & Định giá Thị trường</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # KHỐI THẺ TRẠNG THÁI LIÊN KẾT (GESTALT CARD GOM NHÓM)
    sheet_url = os.environ.get("GOOGLE_SHEET_URL", "").strip()
    update_url = os.environ.get("GOOGLE_SHEET_UPDATE_URL", "").strip()

    if sheet_url:
        sync_badge = "🟢 2 Chiều (Đọc & Ghi)" if update_url else "🔵 1 Chiều (Đọc tự động)"
        sync_desc = "Tự động đồng bộ Sheet 1 (Danh mục) & Sheet 2 (Watchlist) thời gian thực."
        st.markdown(f"""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 12px; font-weight: 700; color: #334155;">Google Sheets</span>
                <span style="font-size: 11px; font-weight: 700; color: #15803d; background: rgba(34,197,94,0.12); padding: 2px 7px; border-radius: 5px;">{sync_badge}</span>
            </div>
            <div style="font-size: 11.5px; color: #64748b; line-height: 1.45; margin-bottom: 8px;">{sync_desc}</div>
            <a href="{sheet_url}" target="_blank" style="font-size: 12px; font-weight: 600; color: #2563eb; text-decoration: none; display: inline-flex; align-items: center; gap: 4px;">
                ↗ Mở Trang tính Google
            </a>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; margin-bottom: 12px;">
            <div style="font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 4px;">📁 Nguồn dữ liệu cục bộ</div>
            <div style="font-size: 11.5px; color: #64748b; line-height: 1.45;">Đang đọc từ file <code>portfolio.json</code> & <code>watchlist.json</code> trên máy.</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.subheader("⚡ Thao tác nhanh")
    if st.button("🔄 Làm mới dữ liệu tức thì", width="stretch"):
        st.cache_data.clear()
        _GSHEET_CACHE["timestamp"] = 0
        _GSHEET_CACHE["portfolio"] = None
        _GSHEET_CACHE["watchlist"] = None
        st.rerun()

    st.divider()
    st.info("💡 **Gợi ý:** Bot tự động bắn tín hiệu Mua/Bán vào tin nhắn riêng (DM) Discord của bạn.")


# --- ĐIỀU PHỐI CÁC TABS LAZY LOADING (TỐI ƯU HIỆU NĂNG TỨC THÌ, TRÁNH TREO SERVER) ---
active_tab = st.radio(
    "Điều hướng Dashboard",
    [
        "Tổng quan & Watchlist", 
        "Thị trường & Định giá", 
        "Biểu đồ Kỹ thuật", 
        "Quản lý Danh mục", 
        "Trợ lý Phân tích AI",
        "🎯 Alpha Tracker"
    ],
    horizontal=True,
    label_visibility="collapsed"
)

if active_tab == "Tổng quan & Watchlist":
    render_tab_overview(df_eval, raw_portfolio, df_wl=df_wl, raw_watchlist=raw_watchlist)

elif active_tab == "Thị trường & Định giá":
    with st.spinner("Đang cập nhật biểu đồ & định giá VN-Index..."):
        df_vnindex = get_cached_vnindex_data()
        render_tab_market(df_vnindex)

elif active_tab == "Biểu đồ Kỹ thuật":
    with st.spinner("Đang tải dữ liệu nến TradingView..."):
        render_tab_charts(raw_portfolio)

elif active_tab == "Quản lý Danh mục":
    render_tab_portfolio(raw_portfolio, raw_watchlist=raw_watchlist)

elif active_tab == "Trợ lý Phân tích AI":
    render_tab_ai(df_eval)

elif active_tab == "🎯 Alpha Tracker":
    with st.spinner("Đang kiểm toán đối soát Alpha Tracker từ Supabase..."):
        render_tab_alpha_tracker()

