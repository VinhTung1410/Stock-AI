# Out-Of-Sample (OOS) Frozen Strategy & Governance Protocol

**Ngày bắt đầu OOS (Clean Baseline Date):** 13/10/2026  
**Logic Version:** `v15.0_frozen_20261013`  
**Model Version:** `v15.0_post_fix`  
**Parameter Registry SHA256:** `c67cf805d685ea3e9353fb56c4f004419503199e6a24bf8dcba105d44f8736a3`  
**Quant Valuation Logic SHA256:** `46a08826dbff8381c7621a800e0f0f1ee6fe755a8ac44af45d47801004f0ad79`  

---

## 1. Nguyên Tắc Đóng Băng Tuyệt Đối (Logic & Parameter Freeze)

1. **Khóa logic định giá & quy tắc ra quyết định:**  
   Từ ngày **13/10/2026**, toàn bộ công thức định giá (P/B chu kỳ, P/E trung vị, DCF, Graham-Buffett), tham số chiết khấu, ngưỡng rào cản Margin of Safety (MoS), và các cổng kiểm định (Data Gate, Risk Trap, Tech Confirmation, Conviction Score) được **đóng băng 100%**.  
   *Mọi can thiệp vào logic định giá hoặc tham số sẽ hủy hiệu lực mốc Out-Of-Sample và buộc phải reset chu kỳ đo lường từ đầu.*

2. **Chỉ sửa đổi Metadata (Metadata-Only Patches):**  
   Mọi bản vá mã nguồn trong thời gian đóng băng chỉ được phép sửa lỗi định danh nhãn hoặc trường quan sát thụ động (passive inspection). Trước khi commit, bắt buộc phải vượt qua bài kiểm tra `tests/test_golden_zero_diff_replay.py` với kết quả **0 khác biệt (Zero Diffs)** trên toàn bộ các mã cổ phiếu đối chứng.

3. **Tách biệt Logic Version và Git SHA:**  
   - `logic_version = "v15.0_frozen_20261013"`: Cố định xuyên suốt chu kỳ OOS.  
   - `git_sha`: Ghi nhận commit thực tế của bản vá metadata để phục vụ truy vết.

---

## 2. Quy Ước Bản Ghi Chuẩn & Giá Vào Lệnh (Execution Price Convention)

1. **Bản ghi chuẩn (Canonical Golden Record):**  
   - Mỗi ngày giao dịch chỉ lưu **1 bản ghi đại diện duy nhất** cho mỗi mã `(symbol, date)`: lấy lần quét EOD sau **15:00 ICT** (khi phiên ATC 14:45 đã kết thúc và giá đóng cửa chính thức đã xác lập).  
   - Đánh dấu cờ `is_canonical = True`.  
   - Loại bỏ toàn bộ các bản ghi thử nghiệm ngầm `is_shadow == True`.

2. **Quy ước Giá vào lệnh (Execution Price):**  
   - Tín hiệu kết thúc phiên T+0 (13/10/2026) chỉ có thể được nhà đầu tư hành động vào phiên tiếp theo. Do đó, **giá vào lệnh cơ sở là Giá Mở Cửa T+1 (Open Price 14/10/2026)**.  
   - Tỷ suất sinh lời kỳ hạn $T+k$ (Forward Return) được tính chuẩn xác:
     $$\text{Forward Return}_{T+k} = \frac{\text{Close}_{T+k} - \text{Open}_{T+1}}{\text{Open}_{T+1}} \times 100\%$$
   - **Mốc T+1:** Phiên 14/10/2026 (biến động trong ngày từ Open 14/10 tới Close 14/10).  
   - **Mốc T+5:** Phiên 20/10/2026 (sau 5 phiên giao dịch thực tế: 14, 15, 16, 19, 20/10).

---

## 3. Cấu Trúc Thuần Tập & Kiểm Soát Thiên Vị Ngành (Stratified Cohorts)

Tập dữ liệu chuẩn ngày 13/10/2026 gồm **N = 55 mã duy nhất**:
- **Nhóm REJECT:** 39 mã  
- **Nhóm WATCH:** 16 mã (9 Ngân hàng, 4 BĐS, 3 Bluechip/Khác)

Do tỷ trọng ngành của nhóm WATCH tập trung cao vào Ngân hàng và BĐS, việc so sánh gộp thô (raw comparison) sẽ bị chi phối bởi beta ngành thay vì alpha của hệ thống. Do đó, kiểm toán hiệu suất sẽ thực hiện phân tầng:

| Tầng Phân Tích | Nhóm Đối Chứng 1 | Nhóm Đối Chứng 2 | Chuẩn So Sánh (Benchmark) |
|---|---|---|---|
| **Toàn Thị Trường (Overall)** | WATCH (16 mã) | REJECT (39 mã) | VN-Index |
| **Nhóm Ngân Hàng (Bank Stratum)** | Bank WATCH (9 mã: ACB, BID, CTG, HDB, MBB, SHB, SSB, TPB, VIB) | Bank REJECT (3 mã: STB, VPB, TCB) | VN-Index & VN-FinLead |
| **Nhóm Bất Động Sản (Real Estate Stratum)** | BĐS WATCH (4 mã: DIG, DXG, KDH, NLG) | BĐS REJECT (NVL, PDR, VHM, VRE, SZC) | VN-Index & VN-RealEstate |

---

## 4. Kiểm Toán Alpha Attribution & Kích Thước Mẫu Hợp Lệ

Theo quy chuẩn [alpha_attribution.py](file:///c:/Users/Window/Desktop/Stock%20-%20learning/alpha_attribution.py):
1. **Lọc sạch dữ liệu đối chứng:**  
   - Loại trừ hoàn toàn các mã lỗi kỹ thuật dữ liệu (`DATA_ERROR`, `TECH_FETCH`, thiếu dữ liệu BCTC nghiêm trọng) khỏi nhóm đối chứng REJECT định lượng.  
   - Chỉ giữ các mã REJECT do vi phạm rủi ro kỹ thuật (`RISK_TRAP`) hoặc định giá kém hấp dẫn.
2. **Kích thước mẫu trưởng thành:**  
   - Đếm số phiên quan sát trưởng thành (`n_matured`) độc lập cho từng mốc T+1, T+5, T+20.  
   - **Quy tắc 60 phiên:** Mọi kết quả dưới 60 phiên sạch ($N < 60$) chỉ được coi là **Thống kê mô tả (Descriptive Statistics)**. Tuyệt đối không điều chỉnh tham số hoặc kết luận alpha chiến lược khi chưa đạt đủ 60 phiên.
3. **Ước lượng sai số thống kê:**  
   - Áp dụng thuật toán **Clustered Bootstrap theo ngày giao dịch** (resampling theo từng cụm phiên giao dịch) để bảo toàn tương quan chéo giữa các cổ phiếu trong cùng phiên.

---

## 5. Giám Sát MoS Ngoại Lai Thụ Động (Passive Outlier Monitoring)

Để theo dõi các trường hợp MoS cực trị (DGC +62.75%, SHB +60.13%) mà không can thiệp thay đổi giá trị định giá:
- Bổ sung trường quan sát thụ động `fv_price_ratio = fair_value / current_price`.
- Gắn cờ cảnh báo `mos_review_flag = True` nếu `fv_price_ratio < 0.5` hoặc `fv_price_ratio > 2.0`.
- Các cờ này chỉ phục vụ báo cáo kiểm toán, hoàn toàn không can thiệp vào logic ra quyết định.
