# Research Finding: CONTRARIAN V1.0 BASELINE (FROZEN)

## 1. Overview & Final Verdict
- **Hypothesis**: Sử dụng chiến lược bắt đáy (Contrarian) dựa trên các tín hiệu kỹ thuật kết hợp với Regime Gate (MA200) để bảo vệ vốn và tạo Alpha.
- **Status**: `CLOSED / FROZEN`
- **Verdict**: 🔴 `FAIL RESEARCH`

Tất cả các thành phần cấu thành nên V10 đều không vượt qua được bài kiểm định định lượng ngặt nghèo (Episode Study & Portfolio Walk-forward):

| Thành phần | Kết luận |
|------------|----------|
| **Fundamental filters** | Chưa chứng minh được Alpha. |
| **MoS (Margin of Safety)** | Chưa chứng minh được độ tin cậy của Fair-value (đặc biệt trong giai đoạn hoảng loạn). |
| **Panic Score** | Chưa chứng minh được sức mạnh dự báo (Predictive power). |
| **Price Confirmation** | Chưa chứng minh được lợi thế về thời điểm (Timing edge) — việc đợi nến xanh xác nhận thậm chí làm giảm lợi suất so với bắt ngẫu nhiên. |
| **MA200 Regime** | 🔴 **FAILED HYPOTHESIS**: MA200 không có khả năng nhận diện Risk Regime kịp thời (độ trễ quá lớn). |
| **Regime Gate** | 🔴 **FAILED ENFORCEMENT**: Việc áp dụng MA200 làm Regime Gate không giúp giảm Max Drawdown trong khủng hoảng flash-crash, ngược lại còn làm lỡ nhịp hồi chữ V. |
| **Cash Mode** | Không thể dùng Regime Gate (MA200) để kích hoạt Cash Mode nhằm chứng minh Alpha cho Contrarian. |
| **V10 OVERALL** | 🔴 **FAIL RESEARCH** |

## 2. Bài học rút ra (Negative Evidence)

### 2.1. Sự sụp đổ của Tầng Tiền Đề (Gate 0)
Quy trình logic của chiến lược là: `Market Regime` → `Contrarian eligibility` → `Panic detection` → `Entry`.
Tuy nhiên, **Gate 0 (Market Regime bằng MA200)** đã thất bại hoàn toàn trong việc phân biệt trạng thái thị trường đúng cách. Vì tầng đầu tiên đã sai/bị nhiễu, mọi thống kê phía sau (Tỉ lệ thắng của Panic Buy, Lợi suất của Cash Mode) đều mang rủi ro bị nhiễu nặng và không đáng tin cậy. 

*Hệ quả:* **Không được phép suy luận rằng "Regime Gate làm giảm drawdown" nếu bản thân định nghĩa Regime (MA200) đã thất bại.**

### 2.2. Rủi ro bất đồng bộ Tài liệu và Code (Discrepancy)
Quá trình audit V10 đã phát hiện sự bất đồng bộ nghiêm trọng giữa thiết kế và thực thi:
- **ADR-031** quy định: Downtrend yêu cầu MoS ≥ 30%.
- **Code thực thi** (`CONTRARIAN_MIN_MOS_PCT`): Lại set ở mức 15% (Deep là 20%).
Điều này cho thấy dữ liệu trong lịch sử kiểm thử không tuân thủ nghiêm ngặt thiết kế hệ thống, nhấn mạnh tầm quan trọng của việc đóng băng (freeze) và audit code chặt chẽ thay vì tuning thông số mù quáng.

### 2.3. Cạm bẫy Parameter Mining
Việc cố gắng "sửa" V10 bằng cách tinh chỉnh các ngưỡng (Threshold Tuning) như: *RSI 30 → 32, MoS 20 → 25, MA200 → MA150* là hành vi **Parameter Mining / Curve Fitting**. Nó không giải quyết được bản chất vấn đề và sẽ dẫn đến Overfitting trên dữ liệu quá khứ. 
Do đó, V10 chính thức bị đóng băng (FROZEN) và chỉ được dùng làm bằng chứng phủ định (Negative Evidence).

## 3. Định hướng cho V11 (Next Generation)

V11 sẽ loại bỏ hoàn toàn các giả định tùy ý (như Panic Score, RSI, MA200) và quay lại giải quyết câu hỏi nghiên cứu cốt lõi nhất:

> *"Có tồn tại một observable market state (trạng thái thị trường quan sát được) có thể giúp Contrarian Engine phân biệt được khi nào bắt đáy có lợi thế và khi nào chỉ đang bắt dao rơi hay không?"*

### Phương pháp tiếp cận V11:
1. **Bắt đầu lại từ Gate 0**: Xây dựng một **Market State Classifier** độc lập (Ví dụ phân cụm: `NORMAL`, `STRESS`, `PANIC`, `RECOVERY`).
2. **Đánh giá lợi suất kỳ vọng (Forward Return)**: Thay vì thiết kế lệnh Buy/Sell trước, V11 sẽ kiểm định xem bản thân từng Market State có chứa đựng thông tin về lợi suất tương lai hay không.
   - Đo lường tại các mốc `T+1`, `T+5`, `T+20`, `T+60`.
   - Các metric: Forward Return, MAE (Maximum Adverse Excursion), MFE (Maximum Favorable Excursion), Win Rate.
3. **Loại bỏ nếu không có Alpha**: Nếu State Classifier không chứng minh được sự khác biệt có ý nghĩa thống kê về Forward Return, Gate 0 đó sẽ lập tức bị loại bỏ.
