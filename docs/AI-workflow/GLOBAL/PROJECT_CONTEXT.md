# 🌐 GLOBAL: PROJECT CONTEXT (BỐI CẢNH DỰ ÁN)

**Dự án:** Stock-AI — Hệ thống Phân tích & Trợ lý Đầu tư Định lượng Chứng khoán Việt Nam (Quantamental Copilot)  
**Mục tiêu cốt lõi:** Cung cấp hệ thống khuyến nghị và phân tích cổ phiếu tự động, kết hợp giữa mô hình định lượng (Quantitative Core) và hội đồng 5 chuyên gia AI (LLM Multi-Agent Committee) với chốt chặn kiểm soát rủi ro tuyệt đối.

---

## 1. Kiến trúc Tổng thể Hệ thống

Hệ thống hoạt động theo mô hình 4 lớp liên kết chặt chẽ:

```
[1. Dữ liệu Đầu vào (Data Engine)]
    ├── Vnstock (Nguồn VCI / CafeF / Vietcap)
    ├── Tin tức & Sự kiện vĩ mô (Google News, CafeF RSS)
    └── Sổ lệnh & Dữ liệu giao dịch khớp lệnh thực tế
           │
           ▼
[2. Chốt chặn Thẩm định & Định lượng (Data Gate & Quant Engine)]
    ├── Data Gate: Kiểm tra độ tươi (Freshness), Triangle cross-check, chặn dữ liệu đóng băng
    ├── Quant Engine: F-Score, Z-Score, ATR(14), Trailing Stop
    └── Risk Engine: Half-Kelly sizing, Lọc thanh khoản ADV20, Giới hạn tỷ trọng ngành
           │
           ▼
[3. Hội đồng AI & Trọng tài (AI Analyst & PM Arbitration)]
    ├── 5 Chuyên gia AI: Vĩ mô, Cơ bản, Dòng tiền & Kỹ thuật, Tin tức, Định giá
    └── Trọng tài PM (Gatekeeper): Quyền phủ quyết tuyệt đối (Thesis Breaker, Falling Knife, FOMO Protection)
           │
           ▼
[4. Trình diễn & Thông báo (Presentation Layer)]
    ├── Streamlit UI đa tab (TradingView 60 FPS, ECharts Valuation Bands, Portfolio Tracker)
    ├── Discord Bot cảnh báo tức thời (Real-time Trading Alerts)
    └── Nhật ký kiểm toán tín hiệu (Alpha Tracker & Supabase Persistence)
```

---

## 2. Công nghệ Cốt lõi & Ràng buộc Kỹ thuật

| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| Ngôn ngữ | Python 3.10+ (ưu tiên 3.11) | Tương thích Windows và Linux/VPS |
| Frontend | Streamlit + Apache ECharts + TradingView Lightweight Charts | 60 FPS native rendering |
| Cơ sở dữ liệu | Supabase (PostgreSQL REST) | Lưu `signals` + `signal_tracking` |
| Engine Dữ liệu | `vnstock` (>= 4.0.6), `vnai` (>= 2.5.7) | Nguồn VCI + CafeF |
| Mô hình AI / LLM | Google Gemini (gemini-2.5-flash / pro) | 2-pass Quantamental prompt |
| Linter & Formatter | Ruff (I001), SonarCloud Quality Gate | Exit code 0 bắt buộc |
| Kiểm thử | Pytest + pytest-cov | Coverage > 80% trên mã mới |
| CI/CD | GitHub Actions | Auto-lint, test, coverage upload |

---

## 3. Ranh giới Nghiệp vụ (Business Guardrails)

1. **Không suy đoán khi dữ liệu bất thường:** Nếu Data Gate phát hiện dữ liệu quá hạn (stale) hoặc sai lệch mẫu số/tử số (P/B, ROE ảo), hệ thống tự động khóa khuyến nghị (`recommendation_allowed = False`).
2. **Quyền phủ quyết định lượng (PM Arbitration):** Dù hội đồng AI có đồng thuận BUY 100%, nếu vi phạm các tiêu chí kỹ thuật/định lượng (RSI > 75, giá dưới MA200 > 15%, Z-score vùng nguy hiểm), lệnh mua sẽ bị hủy hoặc hạ tỷ trọng.
3. **Quản trị vốn chặt chẽ:** Tỷ trọng vị thế được tính bằng Half-Kelly Criteria kết hợp 3 tầng thanh khoản ADV20 để chống nghẽn lệnh.
4. **Ngôn ngữ đầu ra:** 100% tiếng Việt chuẩn Unicode, giọng văn phân tích tài chính chuyên nghiệp (CFA Standard), tuyệt đối không dùng từ ngữ lai tạp hoặc chữ Hán/tiếng Trung.

---

## 4. Cây Thư mục Mã nguồn Chính

```text
Stock - learning/
├── app.py                   # Entrypoint Streamlit (5 tabs)
├── ai_analyst.py            # Hội đồng AI 5 chuyên gia + PM Arbitration
├── data_engine.py           # Ingestion (Vnstock, News, Technical Indicators)
├── data_gate.py             # Chốt chặn Phase 0: Freshness + Triangle Cross-check
├── quant_engine.py          # Định lượng: F-Score, Z-Score, Half-Kelly, ADV20
├── quant_valuation.py       # 4-Archetype Valuation (P/B, DCF, Graham, SOTP)
├── quant_sanity_check.py    # Kiểm tra tính nhất quán toán học
├── discord_alerts.py        # Cảnh báo Discord Webhook
├── db_manager.py            # Supabase Persistence & Audit
├── trading_bot.py           # Lập lịch quét tự động sáng/chiều
├── tabs/                    # Giao diện từng tab Streamlit
├── components/              # Visualization: TradingView, ECharts
├── prompts/                 # Prompt templates cho LLM
├── tests/                   # Unit tests (pytest)
└── docs/AI-workflow/        # Quy trình đa vai trò (tài liệu này)
```
