import os
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

    /* 1. TYPOGRAPHY & FONT CHUẨN TIẾNG VIỆT (KHÔNG LỖI CHÂN CHỮ / KHÔNG VỠ FONT) */
    html, body, [class*="css"], [class*="st-"], h1, h2, h3, h4, h5, p, span, div, a, button, input {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        color: #0f172a;
    }

    /* 2. THANH ĐIỀU HƯỚNG TABS (FIX LỆCH GẠCH CHÂN & LỖI ĐÈ CHỮ ICON CUỘN) */
    div[data-baseweb="tab-list"] {
        gap: 8px !important;
        border-bottom: 2px solid #e2e8f0 !important;
        padding-bottom: 0px !important;
        background: transparent !important;
    }

    button[data-baseweb="tab"] {
        padding: 10px 18px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        color: #64748b !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        margin-bottom: -2px !important;
        background: transparent !important;
        border-radius: 6px 6px 0 0 !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    button[data-baseweb="tab"]:hover {
        color: #1e293b !important;
        background: rgba(241, 245, 249, 0.6) !important;
    }

    /* Tab đang Active: Màu Xanh thương hiệu, gạch chân chuẩn hàng, KHÔNG đỏ */
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #1d4ed8 !important;
        border-bottom: 2px solid #2563eb !important;
        background: transparent !important;
    }

    /* Ẩn hoặc đồng bộ line mặc định màu đỏ của Streamlit */
    div[data-baseweb="tab-highlight"] {
        background-color: #2563eb !important;
        height: 2px !important;
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

    /* 3. NÚT BẤM HÀNH ĐỘNG CHÍNH (UX PRIMARY BUTTON: ĐỔI TỪ ĐỎ SANG XANH DƯƠNG BRAND) */
    button[kind="primary"], button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        border: 1px solid #1d4ed8 !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        padding: 8px 18px !important;
        box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2) !important;
        transition: all 0.2s ease !important;
    }

    button[kind="primary"]:hover, button[data-testid="baseButton-primary"]:hover {
        background: #1d4ed8 !important;
        box-shadow: 0 4px 10px rgba(37, 99, 235, 0.35) !important;
        transform: translateY(-1px) !important;
    }

    button[kind="secondary"], button[data-testid="baseButton-secondary"] {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        color: #334155 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }

    button[kind="secondary"]:hover, button[data-testid="baseButton-secondary"]:hover {
        background: #f8fafc !important;
        border-color: #94a3b8 !important;
        color: #0f172a !important;
    }

    /* 4. Ô NHẬP LIỆU (INPUT & TEXTAREA FOCUS RING) */
    div[data-baseweb="input"], div[data-baseweb="textarea"] {
        border-radius: 8px !important;
        border: 1px solid #cbd5e1 !important;
        background-color: #ffffff !important;
        transition: all 0.2s ease !important;
    }

    div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16) !important;
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
    [data-testid="stMetricLabel"] {
        font-size: 12px !important;
        font-weight: 700 !important;
        color: #64748b !important;
        text-transform: uppercase !important;
        letter-spacing: 0.4px !important;
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
    if st.button("🔄 Làm mới dữ liệu tức thì", use_container_width=True):
        st.cache_data.clear()
        _GSHEET_CACHE["timestamp"] = 0
        _GSHEET_CACHE["portfolio"] = None
        _GSHEET_CACHE["watchlist"] = None
        st.rerun()

    st.divider()
    st.info("💡 **Gợi ý:** Bot tự động bắn tín hiệu Mua/Bán vào tin nhắn riêng (DM) Discord của bạn.")


# --- ĐIỀU PHỐI CÁC TABS GIAO DIỆN CHÍNH (TÊN GỌN GÀNG, KHÔNG OVERFLOW) ---
tab_overview, tab_market_val, tab_charts, tab_portfolio, tab_ai = st.tabs([
    "Tổng quan & Watchlist", 
    "Thị trường & Định giá", 
    "Biểu đồ Kỹ thuật", 
    "Quản lý Danh mục", 
    "Trợ lý Phân tích AI"
])

with tab_overview:
    render_tab_overview(df_eval, raw_portfolio, df_wl=df_wl, raw_watchlist=raw_watchlist)

with tab_market_val:
    df_vnindex = get_cached_vnindex_data()
    render_tab_market(df_vnindex)

with tab_charts:
    render_tab_charts(raw_portfolio)

with tab_portfolio:
    render_tab_portfolio(raw_portfolio, raw_watchlist=raw_watchlist)

with tab_ai:
    render_tab_ai(df_eval)

