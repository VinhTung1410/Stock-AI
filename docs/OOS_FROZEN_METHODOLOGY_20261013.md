# Pre-Registered Forward Testing Governance Protocol (Kiểm Định Tiến Tới Đã Đăng Ký Trước)

**Mốc Khởi Điểm Chính Thức (Day 1):** 14/10/2026 (Bản ghi EOD 15:05 chuẩn)  
**Mẫu Thí Điểm Hiệu Chỉnh (Pilot Sample):** 13/10/2026 (262 bản ghi trong phiên)  
**Định Danh Phương Pháp:** Kiểm định tiến tới đã đăng ký trước (*Pre-Registered Forward Test*)  
**Logic Version:** `v15.0_frozen_20261013`  
**Build Hash:** Theo dõi độc lập qua `logic_manifest.json`  
**Model Version:** `v15.0_post_fix`  
**Schema Version:** `v2.0`  
**Logic Manifest:** `logic_manifest.json` (Niêm phong toàn diện 10 file quyết định)  

---

## 1. Bản Chất Phương Pháp: Kiểm Định Tiến Tới Đã Đăng Ký Trước (Không Phải OOS Thuần Túy)

> [!IMPORTANT]
> **Tuyên bố Tính Liêm chính Phương pháp & Khiêm nhường Nhận thức (Epistemic Humility):**  
> 1. Các quy tắc kỹ thuật và định lượng (như định giá P/B trực tiếp cho nhóm Ngân hàng, bội số chu kỳ 8.5× cho GVR, khiên chắn sàn kẹp Floor-Clamped, v.v.) được hoàn thiện và hiệu chỉnh sau khi quan sát hành vi dữ liệu thực tế từ ngày **08/10 đến 12/10** và các mốc đầu phiên **13/10/2026**. Do đó, phiên **13/10 được phân định là Mẫu Thí Điểm (Pilot Calibration Sample)**. Tuyệt đối **KHÔNG** được báo cáo như bằng chứng ngoài mẫu (Out-Of-Sample - OOS) thuần túy.  
> 2. **Giới hạn mẫu và khung kiểm định phản nghiệm (Falsification Paradigm):** Mẫu kiểm định tiến tới gồm 55 mã trong cửa sổ 60 phiên (từ 14/10/2026 đến đầu tháng 01/2027) hoàn toàn nằm trong **một chế độ thị trường giảm (Bear Market Regime)**. Do đó, mục tiêu của giai đoạn này **KHÔNG PHẢI ĐỂ CHỨNG MINH ALPHA**, mà là **tìm kiếm xem có hay không có bằng chứng rõ ràng cho thấy hệ thống bị hỏng hóc hoặc mất cân bằng nghiêm trọng**. Mọi kết luận ở mốc 60 phiên chỉ mang tính mô tả và phản nghiệm cho một chế độ thị trường duy nhất.

### Nguyên Tắc Đóng Băng & Quản Trị `build_hash` vs `logic_version`
1. **Phân biệt `build_hash` và `logic_version`:**  
   - `build_hash`: Băm composite SHA256 của toàn bộ 10 file quyết định. Ghi nhận trung thực mọi thay đổi mã nguồn (kể cả refactor, sửa nhãn metadata, format).  
   - `logic_version`: Đại diện cho thuật toán ra quyết định. Việc nâng `logic_version` được **phân xử bởi kiểm định Replay Zero-Diff trên 55 mã chuẩn**: Nếu replay phát hiện bất kỳ thay đổi nào về `decision`, `primary_rejection_gate`, `mos_pct`, hoặc `conviction`, thì `logic_version` bắt buộc phải nâng. Nếu 0 diff, `logic_version` được giữ nguyên và chỉ ghi nhận thông báo cập nhật `build_hash`.
2. **Khóa Cấu Hình Hiệu Lực & Vũ Trụ Quét:**  
   Mỗi bản ghi và manifest lưu thêm:
   - `effective_config_hash`: Băm của `LOCKED_QUANT_THRESHOLDS`, biến môi trường runtime và `SECTOR_MAP`.
   - `universe_hash`: Băm của danh sách 55 mã canonical trong `BROAD_MARKET_POOL`.

---

## 2. Lịch Trình Các Sự Kiện Định Giá Đã Định Sẵn & Băm Số Liệu Đầu Vào

Trong cửa sổ đo lường hiệu suất tiến tới, Fair Value (FV) và MoS có thể biến động do các sự kiện dữ liệu đầu vào đã định sẵn:

| Ngày Dự Kiến | Sự Kiện Định Lượng | Cơ Chế Tác Động | Danh Sách Mã Ảnh Hưởng |
|---|---|---|---|
| **20/10/2026 – 31/10/2026** | **Mùa Báo Cáo Tài Chính Q3/2026** | Các doanh nghiệp niêm yết công bố BCTC Q3/2026. EPS TTM và BVPS cập nhật mới qua luồng KBS/TCBS, làm thay đổi Fair Value nội tại một cách hợp lệ. | Toàn bộ 55 mã trong danh mục |
| **18/11/2026** | **Hết Hạn Mỏ Neo Consensus FPT (90 Ngày)** | Consensus Target FPT (88.0k) có `last_updated = 2026-08-20` (sau Q2 từ SSI/Vietcap/HSC). Chạm ngưỡng 90 ngày vào **18/11/2026**, kích hoạt quy tắc `check_institutional_target_freshness(max_age_days=90)` và chốt chặn `is_benchmark_dated = False`. | FPT (Compounder) |
| **29/12/2026** | **Hết Hạn Mỏ Neo Consensus MWG (90 Ngày)** | Consensus Target MWG (83.5k) có `last_updated = 2026-09-30` (từ VCBS/SSI). Chạm ngưỡng 90 ngày vào **29/12/2026**. | MWG (Retail) |
| **30/12/2026** | **Hết Hạn Mỏ Neo Consensus 13 Mã Trọng Điểm (90 Ngày)** | Các mỏ neo consensus của 13 mã (HPG, SSI, TCB, MBB, ACB, VCB, VHM, VNM, DGC, PNJ, REE, MSB, BSR) có ngày phát hành báo cáo nguồn là **2026-10-01** (Báo cáo chiến lược Q4/2026 của SSI Research, Vietcap, HSC). Chạm ngưỡng 90 ngày vào **30/12/2026**. *Xác nhận kiểm toán: Ngày 01/10 là ngày phát hành báo cáo phân tích nguồn, không phải ngày sửa mã nguồn.* | 13 mã thuộc Universe 55 |

### Giám Sát Bất Biến Giá Trị Nội Tại Ngầm Định & Băm `fin_hash`
Công thức bất biến toán học:
$$\text{Implicit Fair Value} = \frac{\text{Price}}{1 - (\text{MoS} / 100)}$$

- **Băm số liệu đầu vào (`fin_hash`):** Để tránh trường hợp nhà cung cấp sửa số liệu mà giữ nguyên nhãn kỳ báo cáo (như vụ BVPS của KBS), hệ thống băm trực tiếp `(eps, bvps, roe, pe, consensus_price, bctc_period)` thành `fin_hash`.
- **Quy tắc phát hiện trôi:** Nếu `fin_hash` không đổi giữa hai phiên, $\text{Implicit FV}$ bắt buộc không đổi ($\Delta \text{Implicit FV} \le 0.5\%$). Bất kỳ đột biến nào sẽ bị `detect_unintended_valuation_drift()` gắn cờ `UNINTENDED VALUATION DRIFT DETECTED`.

---

## 3. Quy Chuẩn Nhãn Dữ Liệu & Phiên Bản Schema (Schema Versioning)

- **`schema_version = "v2.0"`** áp dụng chính thức từ Ngày 1 (14/10/2026).
- **Quy ước nhãn `informative`:**
  - *Dữ liệu 13/10 trở về trước:* Nhãn cũ bị trùng khít với quyết định. Phân tích thống kê bắt buộc dùng quy ước **"MoS khác rỗng (`mos_pct is not None`)"** thông qua hàm `is_record_informative()`.
  - *Dữ liệu 14/10 trở đi (Schema v2.0):* Dùng cờ `informative` chuẩn của mô hình định giá.

---

## 4. Quy Ước Giá Vào Lệnh, Quét 15:05 & Phương Án Dự Phòng

1. **Bản ghi chuẩn lúc 15:05 ICT & Quy tắc Fallback:**  
   - Job quét chuẩn `EOD_CANONICAL` kích hoạt lúc **15:05 ICT** mỗi ngày giao dịch. Giá lấy từ `EOD_CACHE` tại thời điểm này là **Giá Đóng Cửa Đã Điều Chỉnh (Adjusted Close)** chính thức của ngày giao dịch đó (ví dụ 52/55 mã ngày 14/10).
   - **Quy tắc dự phòng (`canonical_fallback = True`):** Nếu một mã canonical gặp sự cố ở lần quét 15:05 (`TECH_FETCH`, thiếu giá, lỗi kết nối), bot tự động truy xuất bản ghi thành công gần nhất trong ngày (phiên `CLOSE` lúc 14:32 hoặc `NOON`), thăng hạng làm bản ghi chuẩn kèm cờ `canonical_fallback = True` và ghi nhận `fallback_from_session`.
   - Bot tính và báo cáo tỷ lệ `canonical_fallback_rate_pct` mỗi ngày trong báo cáo tổng kết 15:15.
2. **Khớp Lệnh Thực Tế & Xử Lý Kịch Trần/Kịch Sàn (Limit Locks):**  
   - Giá vào lệnh danh nghĩa là **Giá Mở Cửa T+1 (Open Price)**.
   - Khi lệnh MUA gặp mở cửa kịch trần (`CEILING_LOCKED` $\pm 7\%$ HOSE): Gắn cờ `fillable_at_open = False`, loại khỏi thống kê khớp lệnh Open và ghi nhận thêm biến thể vào lệnh ở **Giá Đóng Cửa T+1**.
3. **Idempotent Hook `WATCHLIST_ADDED` & Khóa Liên Kết:**  
   - Khóa sự kiện theo **đợt theo dõi: `(symbol, entry_date)`** thông qua hàm `is_watchlist_stint_event_emitted()`. Mỗi đợt chỉ phát đúng 1 sự kiện duy nhất, bền vững qua các lần restart trên Render.
   - **Chuẩn hóa `correlation_id`:** Sự kiện `WATCHLIST_ADDED` mang `correlation_id` là chính `decision_id` của bản ghi chuẩn khởi sinh (đảm bảo tỷ lệ nối 100% với `decision_records`), đồng thời lưu mã đợt `watch_stint_id` (dạng `WL_<SYMBOL>_<DATE>`) bên trong `event_data`.
4. **Thống nhất TTL theo phiên:**  
   Thời hạn Watchlist đếm theo **phiên giao dịch thực tế** (`ttl_sessions = 10`, sử dụng `np.busday_count` kết hợp lịch nghỉ lễ Việt Nam mở rộng 2026–2027 `VN_HOLIDAYS_ALL`). Đã xóa bỏ hoàn toàn trường `ttl_days`.

---

## 5. Rào Cản Thống Kê & Moving Block Bootstrap

1. **Chặn Đầu Ra Khi Dưới 30 Phiên ($N_{\text{sessions}} < 30$):**  
   Trả về `NOT_ENOUGH_CLUSTERS`, triệt tiêu hoàn toàn `ci_lower`, `ci_upper`, `p_value` (gán về `None`), chỉ hiển thị `alpha_mean` và số phiên $n$.
2. **Moving Block Bootstrap cho Chân Tính T+20:**  
   Với mốc nắm giữ 20 phiên, các ngày liền kề có cửa sổ lợi nhuận chồng lấn sinh ra tự tương quan chuỗi MA(19). Hàm `compute_block_bootstrap_alpha()` thực hiện lấy mẫu theo các khối thời gian liên tục với độ dài khối $L = 20$ phiên để bảo toàn cấu trúc tự tương quan, ngăn chặn khoảng tin cậy bị thu hẹp giả tạo.
3. **Rào Cản Mẫu Phân Tầng Ngành:**  
   Nếu phân nhóm WATCH hoặc REJECT trong một ngành có dưới 5 mã ($n < 5$), ẩn hoàn toàn chênh lệch alpha, chỉ hiển thị số lượng mã $n$.

---

## 6. Hạn Chế Đã Biết & Kiểm Toán Dữ Liệu Ngày 14/10/2026

1. **Kiểm Toán Nhãn `logic_version` Ngày 14/10/2026 (Pre-Registered Audit Rule):**  
   - **Thực tế vận hành:** Toàn bộ 201 bản ghi `decision_records` và 217 sự kiện `decision_lifecycle_events` của ngày 14/10/2026 đều được tạo bởi commit `git_sha = 8d353f5` và mang nhãn `logic_version = None`.
   - **Cam kết hợp lệ phương pháp:** Dữ liệu ngày 14/10 vẫn được tính hợp lệ vào chuỗi kiểm định tiến tới vì kiểm định Replay Zero-Diff đã chứng minh logic ra quyết định của `8d353f5` và bản vá telemetry `c8c4211` là đồng nhất 100% (Zero-Diff trên toàn bộ quyết định, cổng vi phạm, MoS và conviction của 55 mã).
   - **Mốc khởi điểm đủ metadata:** Phiên giao dịch ngày **15/10/2026** là ngày đầu tiên mang đầy đủ định danh metadata trên production (`c8c4211` với `logic_version = "v15.0_frozen_20261013"` và 100% `correlation_id` cho Watchlist).
2. **Độ Trễ Phân Vùng Thị Trường (`regime_features.as_of_time`):**  
   - Trong các phiên trong ngày (Morning/Afternoon), `regime_features.as_of_time` phản ánh thanh nến ngày T-1 (`2026-10-13 00:00:00`) do chỉ số VN-Index daily bar chỉ chốt sau khi đóng phiên ATC. Phân loại chế độ thị trường trong phiên mang tính trễ 1 ngày theo thiết kế.
3. **Danh Sách Đa Cổng Vi Phạm (`gates_failed` vs `primary_rejection_gate`):**  
   - Cổng chẩn đoán chi tiết trong `facts.gates_failed` dùng tiền tố hạ tầng (`GATE_MOS`, `GATE_TRAP`, `GATE_RR`, `GATE_KELLY`), trong khi cổng bác bỏ chính (`primary_rejection_gate`) mang tên trừu tượng cấp cao (`RISK_TRAP`, `TECH_CONFIRMATION`, `DATA_GATE`). Đây là quy ước phân tầng thiết kế có chủ đích.
4. **Nguồn Dữ Liệu Thực Tế (`input_source`):**  
   - Nhãn `input_source = TCBS_SNAPSHOT` phản ánh nhà cung cấp dữ liệu thị trường (Market Data Feed Provider), không phải nhãn của thuật toán định giá đa nguồn (vốn tích hợp đồng thuận SSI, Vietcap, HSC).
5. **Cơ Chế Quét Watchlist & Tần Suất Quét Cổ Phiếu (HPG & FPT):**  
   - Mỗi chu kỳ 15 phút, bot quét: (1) toàn bộ danh sách Watchlist hiện hữu + (2) xoay vòng 6 mã tiếp theo từ `BROAD_MARKET_POOL` (55 mã). Do `HPG` nằm cố định trong Google Sheet Watchlist do người dùng cài đặt và `FPT` được tự động phát hiện đưa vào Watchlist, cả hai mã luôn có mặt trong mọi lần quét (20 lần/ngày), trong khi các mã khác chỉ xuất hiện 2–3 lần khi tới lượt xoay vòng hoặc tại phiên `EOD_CANONICAL`.
6. **Độ Nhạy và Biến Động Conviction Score:**  
   - Conviction Score được cấu thành từ 4 trụ cột (MoS 40đ, Technical 25đ, Catalyst 20đ, Flow 15đ). Khi một cổ phiếu vượt hoặc rơi khỏi các ngưỡng nhị phân (như giá cắt qua MA20, rơi vào bẫy giá rơi `-15đ`, hoặc RSI thoát vùng yếu), điểm số có thể dịch chuyển 20–50 điểm giữa hai phiên (ví dụ HPG từ 0 lên 52 khi giá đóng cửa 20.8k vượt lên trên MA20 20.6k). Đây là hiệu ứng ngưỡng phi tuyến cần tiếp tục theo dõi độ ổn định theo chuỗi thời gian.

---

## 7. Tiêu Chí Dừng Đã Đăng Ký Trước (Pre-Registered Stopping Rules)

Để tránh bẫy thiên lệch nhận thức và di chuyển cột gôn trong quá trình kiểm định, hệ thống đăng ký trước 4 tiêu chí cứng kích hoạt trạng thái **Review Khẩn Cấp / Dừng Hệ Thống**:

1. **Quy tắc Kém hiệu quả (Underperformance Rule):** Tỷ suất sinh lời thực tế của nhóm WATCH thua kém danh mục REJECT hoặc VN-Index liên tục trong 30 phiên với mức chênh lệch $> 5\%$ và có ý nghĩa thống kê ($p < 0.05$).
2. **Quy tắc Giới hạn Rút vốn (Drawdown Breach):** Max Drawdown của danh mục giả lập có ma sát vượt quá **15%**.
3. **Quy tắc Tê liệt Mô hình (Model Paralysis):** Trạng thái 0 BUY kéo dài liên tục quá **45 phiên giao dịch**, bất chấp VN-Index có nhịp phục hồi kỹ thuật xác nhận $> 10\%$ với độ rộng thị trường (market breadth) đồng thuận.
4. **Quy tắc Toàn vẹn Dữ liệu (Data Integrity Breach):** Nguồn cấp dữ liệu thô gặp sự cố mất mát, sai lệch định dạng, hoặc trôi giá bất thường không thể khắc phục quá 2 phiên liên tiếp.

---

## 8. Quy Trình Sửa Lỗi Khẩn Cấp (Hotfix & Epoch Split Protocol)

Khi phát sinh lỗi logic nghiêm trọng buộc phải can thiệp mã nguồn trong giai đoạn đóng băng:
1. Nâng phiên bản `logic_version` (ví dụ từ `v15.0_frozen_20261013` lên `v15.1_frozen_YYYYMMDD`).
2. **Khởi động lại đồng hồ đo lường (Reset Clock):** Toàn bộ dữ liệu được phân tách thành 2 kỷ nguyên độc lập:
   - **Epoch 1:** Dữ liệu trước thời điểm hotfix.
   - **Epoch 2:** Dữ liệu sau thời điểm hotfix.
3. Tuyệt đối **KHÔNG gộp dữ liệu hai Epoch** để báo cáo hiệu suất chung nhằm tránh sống sót thiên lệch (survivorship bias).

---

## 9. Bản Chụp Dữ Liệu Thô Point-in-time & Chế Độ WORM (Append-Only)

1. **Bản Chụp Dữ Liệu Thô (Point-in-time Raw Snapshot):**  
   - Bảng lưu trữ bền vững `raw_input_snapshots` (Migration 0009) lưu lại 100% chuỗi phản hồi gốc (raw JSON payloads) của nhà cung cấp tại đúng microsecond ra quyết định (BCTC, giá thị trường, consensus target).
   - Khóa liên kết chặt chẽ: `(session_date, symbol, decision_id)`.
2. **Cơ Chế Bất Biến WORM (Write Once, Read Many):**  
   - Kích hoạt PostgreSQL Trigger `enforce_append_only_audit_log` chặn tuyệt đối mọi thao tác `UPDATE` và `DELETE` trên `decision_records`, `decision_lifecycle_events`, và `raw_input_snapshots`.
3. **Sao Lưu Ngoại Vi Độc Lập:**  
   - Cuối mỗi ngày giao dịch, xuất tệp sao lưu nén ra bộ nhớ ngoài Supabase, đi kèm mã kiểm tra toàn vẹn `checksum.sha256`.

---

## 10. Giám Sát Tự Động & Dead-Man's Switch

- Hệ thống giám sát độc lập gửi cảnh báo tự động (qua Webhook/Telegram) nếu:
  1. Quá 15:15 ICT mà job quét chuẩn `EOD_CANONICAL` chưa hoàn tất ghi nhận.
  2. Số lượng bản ghi chuẩn trong phiên $\ne 55$ mã thuộc `BROAD_MARKET_POOL`.
  3. Phát hiện `canonical_fallback_rate_pct > 10%`.
