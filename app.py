import streamlit as st
from dotenv import load_dotenv

from data_engine import load_portfolio, evaluate_portfolio, get_vnindex_valuation_data
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

# Custom CSS Dark Theme cao cấp
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .metric-title { font-size: 13px; color: #94a3b8; margin-bottom: 4px; }
    .metric-val { font-size: 22px; font-weight: 700; color: #f8fafc; }
    .stDataFrame { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def get_cached_portfolio_eval():
    """Cache đánh giá danh mục trong 5 phút."""
    portfolio = load_portfolio()
    return evaluate_portfolio(portfolio), portfolio


@st.cache_data(ttl=1800)
def get_cached_vnindex_data():
    """Cache dữ liệu nến và bội số P/E, P/B của VN-Index trong 30 phút."""
    return get_vnindex_valuation_data()


# --- SIDEBAR ĐIỀU KHIỂN ---
with st.sidebar:
    st.title("🤖 AI Stock Copilot")
    st.caption("Hệ thống Giám sát Danh mục & Định giá Thị trường")
    st.divider()

    st.subheader("⚡ Thao tác nhanh")
    if st.button("🔄 Làm mới dữ liệu", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.info("💡 **Gợi ý:** Bạn có thể chỉnh sửa trực tiếp danh mục bên tab 'Quản lý Danh mục'.")


# --- DỮ LIỆU ĐẦU VÀO ---
df_eval, raw_portfolio = get_cached_portfolio_eval()


# --- ĐIỀU PHỐI CÁC TABS GIAO DIỆN CHÍNH ---
tab_overview, tab_market_val, tab_charts, tab_portfolio, tab_ai = st.tabs([
    "📊 Tổng quan Danh mục", 
    "🏛️ Thị Trường & Định Giá (VN-Index, P/E, P/B)",
    "📈 Biểu đồ Kỹ thuật", 
    "⚙️ Quản lý Danh mục", 
    "🧠 Trợ lý Phân tích AI"
])

with tab_overview:
    render_tab_overview(df_eval, raw_portfolio)

with tab_market_val:
    df_vnindex = get_cached_vnindex_data()
    render_tab_market(df_vnindex)

with tab_charts:
    render_tab_charts(raw_portfolio)

with tab_portfolio:
    render_tab_portfolio(raw_portfolio)

with tab_ai:
    render_tab_ai(df_eval)
