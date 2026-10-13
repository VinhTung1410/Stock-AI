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
> **Tuyên bố Tính Liêm chính Phương pháp (Methodological Honesty):**  
> Các quy tắc kỹ thuật và định lượng (như định giá P/B trực tiếp cho nhóm Ngân hàng, bội số chu kỳ 8.5× cho GVR, khiên chắn sàn kẹp Floor-Clamped, v.v.) được hoàn thiện và hiệu chỉnh sau khi quan sát hành vi dữ liệu thực tế từ ngày **08/10 đến 12/10** và các mốc đầu phiên **13/10/2026**.  
> Do đó, phiên **13/10 được phân định là Mẫu Thí Điểm (Pilot Calibration Sample)**. Giai đoạn kiểm định tiến tới chính thức bắt đầu từ **14/10/2026 (Ngày 1 - Day 1)**. Tuyệt đối **KHÔNG** được báo cáo như bằng chứng ngoài mẫu (Out-Of-Sample - OOS) thuần túy.

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
| **28/10/2026** | **Hết Hạn Mỏ Neo Consensus (90 Ngày)** | Hằng số Consensus Target có `last_updated = 2026-07-30`. Cộng đúng 90 ngày chạm mốc **28/10/2026**, kích hoạt quy tắc `check_institutional_target_freshness(max_age_days=90)` và chốt chặn `quant_valuation.py:1202` (`is_benchmark_dated = False`). | 5 – 15 mã Compounder (MWG, FPT, PNJ, VNM, REE, v.v.) |

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
   - Job quét chuẩn `EOD_CANONICAL` kích hoạt lúc **15:05 ICT** mỗi ngày giao dịch.
   - **Quy tắc dự phòng (`canonical_fallback = True`):** Nếu một mã canonical gặp sự cố ở lần quét 15:05 (`TECH_FETCH`, thiếu giá, lỗi kết nối), bot tự động truy xuất bản ghi thành công gần nhất trong ngày (phiên `CLOSE` lúc 14:32 hoặc `NOON`), thăng hạng làm bản ghi chuẩn kèm cờ `canonical_fallback = True` và ghi nhận `fallback_from_session`.
   - Bot tính và báo cáo tỷ lệ `canonical_fallback_rate_pct` mỗi ngày trong báo cáo tổng kết 15:15.
2. **Khớp Lệnh Thực Tế & Xử Lý Kịch Trần/Kịch Sàn (Limit Locks):**  
   - Giá vào lệnh danh nghĩa là **Giá Mở Cửa T+1 (Open Price)**.
   - Khi lệnh MUA gặp mở cửa kịch trần (`CEILING_LOCKED` $\pm 7\%$ HOSE): Gắn cờ `fillable_at_open = False`, loại khỏi thống kê khớp lệnh Open và ghi nhận thêm biến thể vào lệnh ở **Giá Đóng Cửa T+1**.
3. **Idempotent Hook `WATCHLIST_ADDED`:**  
   Khóa sự kiện theo **đợt theo dõi: `(symbol, entry_date)`** thông qua hàm `is_watchlist_stint_event_emitted()`. Mỗi đợt chỉ phát đúng 1 sự kiện duy nhất, bền vững qua các lần restart trên Render.
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

## 6. Hạn Chế Đã Biết & Telemetry Thụ Động (Known Limitations)

1. **Danh Sách Đa Cổng Vi Phạm (`gates_failed`):**  
   Được thu thập đầy đủ dưới dạng danh sách chẩn đoán thụ động (`["GATE_MOS", "GATE_RR", "GATE_KELLY", "GATE_TRAP"]`) trong `record_payload["facts"]`, phục vụ phân tích nguyên nhân gốc rễ mà không làm thay đổi luồng quyết định chính.
2. **Nguồn Dữ Liệu Thực Tế (`input_source`):**  
   Ghi nhận nguồn dữ liệu thực sự giải quyết từ tầng hạ tầng (`TCBS_REST`, `KBS_SNAPSHOT`, `LIVE`), thay vì nhãn tĩnh.
3. **Lịch Giao Dịch Vượt Năm 2027:**  
   Tập hợp `VN_HOLIDAYS_ALL` đã tích hợp sẵn lịch nghỉ lễ năm 2027 (Tết Đinh Mùi, Giỗ Tổ 2027, 30/4-1/5, Quốc khánh) để đảm bảo cửa sổ đo lường 60 phiên xuyên năm không bị ngắt quãng.
