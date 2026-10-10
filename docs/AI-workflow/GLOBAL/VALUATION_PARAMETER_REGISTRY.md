# SỔ ĐĂNG KÝ THAM SỐ ĐỊNH GIÁ (VALUATION PARAMETER REGISTRY)

> **Mã văn bản:** REG-PARAM-001  
> **Trạng thái:** ACTIVE & PROGRAMMATICALLY VERIFIED  
> **Kỳ dữ liệu cơ sở:** BCTC Q2/2026 (Audit period 2026-Q2)  
> **Cơ chế xác thực:** Tự động tạo bởi `scripts/generate_parameter_registry.py` trực tiếp từ hàm thực thi `calculate_fair_value_and_mos` trong `quant_valuation.py`. Tuyệt đối không tính tay.

---

## 1. Danh mục Tham số Cốt lõi & Phân tích Độ nhạy $\pm 20\%$

### 1.1. Nhánh Ngân hàng (Bank Archetype - Justified P/B Model)
Mô hình định giá:
$$\text{Target P/B} = \max\left(0.90, \min\left(2.20, \frac{\text{ROE} - g}{\text{CoE} - g}\right)\right)$$

Chuẩn đối chiếu (Benchmark CTG: ROE = $21.05\%$, CoE = $13.0\%$, $g = 5.5\% \implies \text{Base Target P/B} = 2.073\text{x}$):

*Lưu ý cấu trúc:* Mẫu số $(\text{CoE} - g) = 13.0\% - 5.5\% = 7.5\%$ tương đối hẹp vì giả định $g = 5.5\%$ cao hơn lãi suất phi rủi ro $R_f = 4.5\%$. Đây là nguyên nhân toán học khiến Target P/B cực kỳ nhạy cảm với biến động của CoE.

| Mã tham số | Tên tham số | Giá trị cơ sở | Nguồn gốc dữ liệu | Tài liệu nguồn & Ngày | Độ nhạy $\pm 20\%$ | Tác động tới Target P/B (CTG) | Mức độ mong manh |
|---|---|---|---|---|---|---|---|
| `BANK_COE` | Chi phí vốn chủ sở hữu (Cost of Equity) | **13.0%** | CAPM VN: $R_f = 4.5\%$ (TPCP 10Y) + $\beta = 1.1$ + ERP = $7.7\%$ | BCTC Q2/2026 & Lãi suất KBNN (2026-07-30) | $10.4\% \leftrightarrow 15.6\%$ | CoE giảm về $10.4\% \implies$ **+53.1%** (3.17x)<br>CoE tăng lên $15.6\% \implies$ **-25.7%** (1.54x) | **RẤT CAO (Fragile)** |
| `BANK_G` | Tăng trưởng dài hạn ($g$) | **5.5%** | GDP thực dài hạn VN ($6.0\%$) trừ lạm phát cơ sở | Mục tiêu Quốc hội khóa XV (2026-05-15) | $4.4\% \leftrightarrow 6.6\%$ | $g = 4.4\% \implies$ **-6.6%** (1.94x)<br>$g = 6.6\% \implies$ **+8.9%** (2.26x) | **TRUNG BÌNH** |
| `BANK_PB_FLOOR` | Sàn kẹp P/B (Clamp Floor) | **0.90x** | Lịch sử định giá khủng hoảng ngân hàng VN | Lịch sử P/B 2012-2024 (2026-01-15) | $0.72\text{x} \leftrightarrow 1.08\text{x}$ | Khóa cứng Target P/B khi ROE $< 12.25\%$. Điển hình STB ROE TTM $4.99\% \implies \text{raw} = -0.07\text{x} \implies$ khóa tại $0.90\text{x}$ | **FAIL-SAFE (MoS $\le -125\%$)** |
| `BANK_PB_CEIL` | Trần kẹp P/B (Clamp Ceiling) | **2.20x** | Trần P/B chu kỳ đỉnh của VCB/ACB | Đỉnh P/B lịch sử VCB (2026-01-15) | $1.76\text{x} \leftrightarrow 2.64\text{x}$ | Ngăn định giá bong bóng cho bank ROE $> 22\%$ | **BẢO VỆ CHU KỲ** |

---

### 1.2. Nhánh Cổ phiếu Chu kỳ (Cyclical Archetype - Normalized P/E Model)
Mô hình định giá:
$$\text{Fair Value} = \text{Normalized EPS}_{5Y} \times \text{Mid-Cycle P/E} \times (1 - \text{Discounts})$$

*Nguyên tắc định giá chu kỳ:* Bội số đưa vào tính Fair Value là **Bội số chu kỳ thận trọng** (Trough / Conservative Multiple). Bội số trung vị 4 quý gần nhất của GVR ($18.12\text{x}$) là do lợi nhuận đang ở đáy chu kỳ làm phình to P/E (trough-earnings expansion), tuyệt đối không dùng để nhân trực tiếp vào Fair Value.

| Mã cổ phiếu | Bội số Mid-Cycle đưa vào FV | P/E Trung vị 4 quý (KBS) | Kỳ dữ liệu | Độ nhạy $\pm 20\%$ | Tác động Fair Value | Ghi chú & Nguồn gốc |
|---|---|---|---|---|---|---|
| **Mặc định** | **8.5x** | - | 2026-Q2 | $6.8\text{x} \leftrightarrow 10.2\text{x}$ | $\pm 20.0\%$ | Khung thận trọng cơ sở |
| **GVR** | **8.5x** | **18.12x** (17.15 - 26.10x) | BCTC Q2/2026 | $6.8\text{x} \leftrightarrow 10.2\text{x}$ | $\pm 20.0\%$ | Giữ nguyên FV đáy chu kỳ $13.73\text{k}$; MoS $\le -139\%$ phản ánh đúng thị giá cao hơn FV trong downtrend |
| **HPG** | **9.5x** | **13.05x** (11.98 - 13.49x) | BCTC Q2/2026 | $7.6\text{x} \leftrightarrow 11.4\text{x}$ | $\pm 20.0\%$ | Phản ánh Dung Quất 2 vào vận hành |
| **HSG** | **8.0x** | **14.32x** (13.41 - 25.71x) | BCTC Q3/2026 | $6.4\text{x} \leftrightarrow 9.6\text{x}$ | $\pm 20.0\%$ | Biên lợi nhuận phụ thuộc HRC |
| **DCM** | **8.5x** | **10.77x** (8.95 - 12.66x) | BCTC Q2/2026 | $6.8\text{x} \leftrightarrow 10.2\text{x}$ | $\pm 20.0\%$ | Hết khấu hao nhà máy đạm Cà Mau |
| **DPM** | **8.5x** | **11.62x** (10.03 - 25.44x) | BCTC Q2/2026 | $6.8\text{x} \leftrightarrow 10.2\text{x}$ | $\pm 20.0\%$ | Phụ thuộc chu kỳ giá khí đầu vào |

---

### 1.3. Nhánh Cổ phiếu Tăng trưởng (Growth / Compounder Archetype)
Mô hình định giá chi tiết:
$$\text{FV}_{\text{internal}} = 0.5 \times (\text{Forward EPS} \times \text{Median P/E}) + 0.5 \times \text{SOTP}$$
$$\text{FV}_{\text{final}} = 0.6 \times \text{FV}_{\text{internal}} + 0.4 \times (\text{Consensus} \times 0.85)$$
Đơn giản hóa:
$$\text{FV}_{\text{final}} = 0.30 \times (\text{Forward EPS} \times \text{Median P/E}) + 0.30 \times \text{SOTP} + 0.34 \times \text{Consensus}$$

#### Bảng Tham số Cốt lõi của FPT:
- **Base EPS (TTM):** $5.99$ kVND (Nguồn: BCTC Hợp nhất Q2/2026 công bố ngày 2026-07-28)
- **Giả định tăng trưởng $g$:** $15.0\%$ (Giả định phân tích nội bộ: mức chiết khấu thận trọng từ kế hoạch LNTT $+18.2\%$ theo Nghị quyết ĐHCĐ thường niên 2026 số 01/2026/NQ-ĐHĐCĐ-FPT)
- **Target Median P/E:** $19.5\text{x}$ (Trung vị P/E 5 năm lịch sử FPT giai đoạn 2021-2026)
- **SOTP Fair Value:** $115.0$ kVND (Khối Công nghệ 75k + Viễn thông 30k + Giáo dục/Đầu tư 10k)
- **Consensus Target:** $88.0$ kVND (Đồng thuận báo cáo cập nhật sau Q2 của SSI, Vietcap, HSC ngày 2026-08-20, độ tuổi 51 ngày $< 90$ ngày)
- **Consensus Haircut Discount:** $0.85$ (Chiết khấu rủi ro thị trường và độ trễ báo cáo phân tích)
- **Tỷ trọng trộn mô hình:** $60\%$ Mô hình nội bộ / $40\%$ Consensus CTCK

#### Ma trận Phân tích Độ nhạy Tham số FPT (Sinh tự động từ Code bằng `calculate_fair_value_and_mos`):

1. **Độ nhạy Tăng trưởng EPS ($g$):**
| Giả định Tăng trưởng $g$ | Fair Value (kVND) | Lệch so với Cơ sở (15%) |
|---|---|---|
| **0%** | 99.47 | -5.01% |
| **5%** | 101.22 | -3.34% |
| **10%** | 102.97 | -1.67% |
| **15%** | 104.72 | +0.00% |
| **20%** | 106.49 | +1.69% |
| **25%** | 108.24 | +3.36% |

*Kết luận độ nhạy $g$:* Mỗi bước $+5\%$ tăng trưởng LNST chỉ làm Fair Value thay đổi **$\approx 1.65\%$** (không phải $2.8\%$ hay $8\%$), vì P/E chỉ chiếm $30\%$ trọng số trong giá trị cuối cùng.

2. **Độ nhạy các Tham số Trọng yếu Chi phối (Dominant Drivers):**
| Tham số | Giá trị cơ sở | Trọng số thực tế trong FV | Shock $\pm 20\%$ | Fair Value thay đổi | Tác động định giá |
|---|---|---|---|---|---|
| **SOTP Value** | **115.0 kVND** | **30.0%** ($34.50$k) | $92.0\text{k} \leftrightarrow 138.0\text{k}$ | **-6.6%** (97.82k) $\leftrightarrow$ **+6.6%** (111.63k) | **Cực lớn (Chi phối trực tiếp)** |
| **Consensus Target** | **88.0 kVND** | **34.0%** ($29.92$k) | $70.4\text{k} \leftrightarrow 105.6\text{k}$ | **-5.7%** (98.74k) $\leftrightarrow$ **+5.7%** (110.71k) | **Lớn nhất trong các mỏ neo** |
| **Target P/E** | **19.5x** | **30.0%** ($40.30$k) | $15.6\text{x} \leftrightarrow 23.4\text{x}$ | **-7.7%** (96.66k) $\leftrightarrow$ **+7.7%** (112.79k) | **Đồng tỷ trọng với SOTP** |
| **Tăng trưởng $g$** | **15.0%** | Gián tiếp qua EPS | $12.0\% \leftrightarrow 18.0\%$ | **$-1.0\%$** $\leftrightarrow$ **$+1.0\%$** | **Thấp nhất (Thứ yếu)** |

> **Cảnh báo PM:** $61.5\%$ giá trị Fair Value của FPT ($64.42$ kVND / $104.72$ kVND) được neo bởi SOTP ($115$k) và Consensus CTCK ($88$k). Giả định tăng trưởng $g$ là tham số ít nhạy cảm nhất.

---

## 2. Bảng Xếp hạng Độ Mong manh Thực tế (Empirical Fragility Ranking)

Dựa trên kết quả chạy mô hình định lượng độ nhạy $\pm 20\%$, thứ tự từ **Mong manh nhất** đến **Vững chắc nhất**:

```
[MONG MANH NHẤT]
  1. Nhánh Ngân hàng: Chi phí vốn CoE (Biến động Target P/B từ -25.7% đến +53.1% khi CoE lệch ±20%)
  2. Nhánh Chu kỳ: Bội số Mid-Cycle P/E (FV nhạy cảm 1:1; dữ liệu chu kỳ thường thiếu chuẩn hóa)
  3. Nhánh Compounder: Mỏ neo SOTP & Consensus CTCK (Chi phối > 61% Fair Value, khó kiểm chứng từ BCTC)
  4. Nhánh Compounder: Tăng trưởng LNST g (Biến động thấp nhất: ±20% của g chỉ làm đổi FV ±1.0%)
[VỮNG CHẮC NHẤT]
```

### Nguyên tắc Ứng xử Định lượng:
1. **Xử lý khoảng cách Consensus (`consensus_gap_pct`):** Khi chênh lệch giữa mô hình nội bộ và consensus CTCK $> 15\%$, ghi nhận `consensus_gap_pct` và bắt buộc hạ độ tự tin xuống `MEDIUM`.
2. **Kẹp sàn Bank:** Với cổ phiếu ngân hàng chạm sàn Target P/B $0.90\text{x}$ (như STB), ghi nhận rõ ràng `MoS <= -125%` và đánh dấu `target_pb_clamped = True`.
