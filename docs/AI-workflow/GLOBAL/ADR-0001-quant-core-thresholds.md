# 🏛️ ARCHITECTURE DECISION RECORD: ADR-0001
# KHÓA CỐ ĐỊNH CÁC NGƯỠNG ĐỊNH LƯỢNG QUANT CORE (QUANT CORE THRESHOLDS LOCK)

- **Trạng thái:** `ACCEPTED` (Đã phê duyệt và đóng băng)
- **Ngày ban hành:** 2026-09-26
- **Tác giả:** Finance Lead & Senior Quant
- **Phạm vi:** `quant_engine.py`, `ai_analyst.py`, `backtest_engine.py`, `data_gate.py`

---

## 1. Bối cảnh (Context)
Trong phát triển hệ thống định lượng (Quantitative Trading System), rủi ro lớn nhất làm sai lệch kết quả kiểm định lịch sử (Backtest) là **Data Snooping (Khai thác trộm dữ liệu)** và **Overfitting (Khớp quá mức)**. 
Nếu các tham số đầu vào được tinh chỉnh sau khi đã nhìn thấy đường cong vốn (Equity Curve) của một mã cổ phiếu cụ thể, toàn bộ các chỉ số Sharpe, Win Rate, Expectancy sẽ bị thổi phồng nhân tạo và hoàn toàn mất giá trị dự báo trong giao dịch thực tế (Out-of-sample forward trading).

Để ngăn chặn triệt để hành vi nắn tham số tùy tiện, toàn bộ các ngưỡng kích hoạt của chiến lược **Quant Core Strategy** phải được chốt cứng (Frozen) và lưu trữ thành văn bản kiến trúc chính thức trước khi tiến hành backtest hoặc phát tín hiệu thực tế.

---

## 2. Quyết định (Decision)

Đóng băng vĩnh viễn bộ thông số của chiến lược **Quant Core Strategy** theo bảng chuẩn mực:

| Tham số (Parameter) | Giá trị Khóa (Locked Value) | Cơ sở Lý thuyết & Nguồn gốc Thực nghiệm |
|---|---|---|
| **F-Score tối thiểu** | $\ge 6$ / 9 | Nghiên cứu của GS. Joseph Piotroski (2000): Nhóm F-Score $\ge 6$ chứng thực sức khỏe tài chính vượt trội, loại bỏ doanh nghiệp "xào nấu" sổ sách. |
| **Biên an toàn (MoS)** | $\ge 15\%$ | Nguyên lý Đầu tư Giá trị Graham & Dodd: Đảm bảo mức chiết khấu an toàn giữa thị giá và Giá trị Nội tại (Fair Value). |
| **Altman Z-Score** | $> 1.80$ | Mô hình GS. Edward Altman (1968): Ranh giới phân định doanh nghiệp nằm ngoài vùng rủi ro kiệt quệ tài chính / phá sản trong 2 năm tới. |
| **RSI(14) trần (Entry)** | $< 70$ | Ngăn chặn hành vi FOMO đu đỉnh ngắn hạn trong vùng quá mua; chỉ giải ngân ở vùng tích lũy hoặc chân sóng. |
| **Conviction Score** | $\ge 55$ / 100 | Ngưỡng điểm tối thiểu tích hợp 5 trụ cột (Vĩ mô, Cơ bản, Định lượng, Dòng tiền, Tin tức) trước khi xem xét mở vị thế. |
| **Liquidity ADV20** | $\ge 10 \times \text{OrderSize}$ | Đảm bảo tính thanh khoản thực tế, không gây trượt giá thị trường quá mức khi giải ngân. |
| **Sector Exposure Cap**| $\le 25\%$ | Giới hạn rủi ro hệ thống ngành; không phân bổ quá 1/4 danh mục vào cùng một nhóm ngành (SECTOR_MAP). |

---

## 3. Hệ quả & Ràng buộc Thực thi (Consequences & Enforcement)

1. **Tuyệt đối không điều chỉnh ad-hoc:** Nghiêm cấm mọi sửa đổi tham số trực tiếp trong code chỉ để làm đẹp một deal backtest đơn lẻ.
2. **Quy trình thay đổi (Change Request):** Nếu muốn cập nhật bất kỳ ngưỡng nào trong tương lai, bắt buộc phải:
   - Thu thập tối thiểu 100 observations thực tế có kiểm chứng từ `signal_lifecycle`.
   - Có bài phân tích thống kê Out-of-sample chứng minh sự suy giảm hiệu quả của ngưỡng cũ.
   - Ban hành ADR mới (ví dụ: `ADR-0002`) và được Finance Lead cùng Client ký duyệt.
3. **Tuân thủ kiểm thử:** Bổ sung unit test kiểm tra tính toàn vẹn của các hằng số này trong bộ test tự động.
