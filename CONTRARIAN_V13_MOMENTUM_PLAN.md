# CONTRARIAN_V13 — RSI14 Residual Momentum (Exploratory → OOS Confirmation Attempt)

## 0. Trạng thái
- Status: **DRAFT — chưa freeze**
- Lý do chưa freeze: xem mục 10 (blockers)

## 1. Bối cảnh & nguồn gốc giả thuyết
- V12 (DD60 contrarian): không tìm thấy bằng chứng đủ mạnh. Mean IC = -0.007, t_NW = -0.32.
  Khoảng tin cậy 95% xấp xỉ [-0.05, +0.04] nên nhãn đúng là "không đủ power để kết luận,
  nghiêng về không có hiệu ứng ≥ 0.03", không phải "đã bác bỏ".
- RSI14 nổi lên trong V12 (IC ≈ +0.044, t_NW ≈ 2.74 ở đoạn D+1→D+20) khi đã chạy
  ~9 phép thử (3 feature × 3 đoạn return). Đây là **exploratory finding**, chọn sau khi nhìn dữ liệu.
- Hệ quả: V13 Discovery = **post-selection re-estimation with controls**, KHÔNG phải confirmation.
  Chỉ OOS mới được gọi là confirmation attempt.

## 2. Câu hỏi nghiên cứu (một câu)
RSI14 có còn dự báo lợi suất tradable 20 ngày sau khi kiểm soát đồng thời beta, ngành và
ADV hay không?

## 3. Dữ liệu
- Panel: 56 mã (đã dedup từ 117 file), file `data/v12_panel_data.csv`
- Hash SHA-256: `e818e5cbdd5fca7eaf6167a0172a094521b33383ab169d559e4bde830c1c27aa`
  (re-freeze và ghi lý do vào specification log nếu panel thay đổi sau bước blockers)
- Giá: bằng chứng mạnh là đã điều chỉnh ngược (phép thử biên độ, mục audit V12); không phải "tuyệt đối".
- Universe: mid/large cap chọn theo hiện tại → **survivorship-biased**, thiên lệch THUẬN chiều
  với momentum. Gắn nhãn này trên mọi bảng kết quả. OOS dùng cùng universe nên không sửa được.
- Discovery: 2018–2023. Semi-holdout: 2024–2026 (V11 đã dùng dữ liệu cổ phiếu giai đoạn này,
  nhưng chưa nhìn momentum).
- Purge: loại 20 phiên giao dịch cuối của Discovery trước mọi thống kê.
- Min-N: mỗi ngày cần N ≥ 30 mã hợp lệ; ngày không đủ bị loại, báo cáo số ngày bị loại và
  số mã hợp lệ theo năm.

## 4. Biến & định nghĩa lợi suất
Feature (duy nhất): RSI14 tại Close(D), chuẩn hóa rank về [-0.5, +0.5] theo ngày.

Lợi suất:
- R_overnight      = Open(D+1) / Close(D) - 1
- R_first_session  = Close(D+1) / Open(D+1) - 1
- R_post_D1        = Close(D+20) / Close(D+1) - 1
- R_info           = Close(D+20) / Close(D) - 1         (information horizon)
- **R_tradable     = Close(D+20) / Open(D+1) - 1        (PRIMARY TARGET)**

Controls (đồng thời, tại ngày D, chỉ dùng dữ liệu ≤ D):
- Beta: trailing 60 phiên so với VNIndex, chuẩn hóa rank/z-score
- Industry: 3 nhóm (Bank / Real Estate & Securities / Other), nhãn `static_nonPIT`
- ADV: `adv_20d`, một control duy nhất cho size/liquidity, nhãn "approximate"
  (cần xác nhận volume có được điều chỉnh theo chia thưởng; nếu không, báo cáo mô hình có/không ADV)

Biến phụ thuộc winsorize 1%/99% theo ngày (hoặc dùng rank) [TBD: chọn một].

## 5. Phương pháp chính
Fama–MacBeth, mỗi ngày D:

R_tradable,i = α_D + λ_RSI,D · Rank(RSI_i) + b_D · Beta_i + γ_D · Industry_i + δ_D · Rank(ADV_i) + ε_i

- Chuỗi λ_RSI,D → t_NW với Newey–West lag ≥ 20.
- Controls chạy **đồng thời**, không residualize tuần tự.
- Mô hình bỏ từng control = decomposition diagnostics, KHÔNG phải cơ hội chọn specification.
- Thống kê phụ (không dùng để quyết định): Rank IC residual, quintile spread, IC theo năm, % ngày dương.
- Đơn vị chính: λ_RSI (chênh lệch lợi suất 20 ngày giữa RSI cao nhất và thấp nhất sau controls).
- Báo cáo: Corr(RSI, Beta), Corr(RSI, DD60), Corr(RSI, ADV), Corr(RSI, Rev5).

## 6. Decomposition (bắt buộc báo cáo)
λ_RSI trên R_overnight, R_first_session, R_post_D1, R_info, R_tradable.
Diễn giải: nếu RSI chỉ dự báo overnight/first-session mà không dự báo R_tradable
→ kết luận "không chứng minh được continuation sau execution point", không phải alpha giao dịch được.

## 7. Tiêu chí quyết định (viết trước khi chạy)

**Discovery gate (PASS khi thỏa TẤT CẢ):**
1. λ_RSI (R_tradable, đủ controls) > 0
2. t_NW ≥ 2.5 (ngưỡng bảo thủ để bù data-snooping trước đó; KHÔNG gọi là Holm-Bonferroni)
3. Cùng dấu ở ≥ 5/6 năm
4. Continuation: λ(R_tradable) ≥ 50% λ(R_info), cùng estimator và cùng controls
5. Không do một vài quan sát cực đoan (kiểm tra winsorize/leave-out)
- Effect floor 0.02 (đơn vị IC): chỉ BÁO CÁO, ghi rõ là post-hoc, không phải ngưỡng đã được xác nhận độc lập.

**Vùng xám:** nếu 1.5 ≤ t_NW < 2.5 → inconclusive. (Dừng không giao dịch, nhưng có thể mở OOS để quan sát thêm với cảnh báo đỏ).
**FAIL / dừng:** không đạt gate và không thuộc vùng xám → V13 đóng, không mở OOS.

**OOS 2024–2026 (chạy MỘT lần, sau freeze):**
| Kết quả | Điều kiện | Kết luận |
|---|---|---|
| Strong confirmation | cùng dấu, t ≥ 2.0, λ_OOS ≥ 50% λ_Disc | |
| Confirmation | cùng dấu, 1.645 ≤ t < 2.0, λ_OOS ≥ 50% λ_Disc | |
| Inconclusive | cùng dấu nhưng dưới ngưỡng | không coi là thất bại |
| Failure | đổi dấu rõ rệt | non-generalization |

Lưu ý: ngay cả PASS ở OOS cũng chỉ nghĩa "nhất quán với momentum trên universe large-cap sống sót".

## 8. Kiểm tra pipeline trước khi chạy
- Placebo: hoán vị RSI trong từng ngày, chạy lại TOÀN BỘ Fama–MacBeth ≥ 200 lần.
  Yêu cầu: t_NW ~ N(0,1), tỷ lệ |t|>2 ≈ 5%.
- Kiểm tra leakage: tính lại feature từ dữ liệu cắt tại D cho vài ngày mẫu, so khớp.
- Kiểm tra volume/ADV có điều chỉnh theo chia thưởng không.

## 9. Prediction log (ghi TRƯỚC khi chạy)
- Dự đoán định tính: hiệu ứng RSI sẽ giảm đáng kể sau controls đồng thời; thất bại đạt gate là kết quả bình thường.
- Dự đoán định lượng: λ_RSI sau controls nhỏ hơn raw ít nhất ~45%; xác suất tôi cho rằng t_NW ≥ 2.5 là 35%.
  (Ghi con số bằng tay, không sửa sau khi thấy kết quả.)

## 10. Blockers trước khi freeze
1. **Giải thích 4,150 ngày giao dịch:** ĐÃ GIẢI QUYẾT. Số ngày thực tế là 2,343 ngày (từ 03/04/2017 đến 07/10/2026). Dữ liệu hoàn toàn khớp ~250 ngày/năm x 56 mã (khoảng ~13,900 dòng/năm). 
2. Đổi toàn bộ ngưỡng sang đơn vị λ: Đã định nghĩa λ trong phương trình Fama-MacBeth.
3. Xác nhận volume/ADV: `ADV_20d` là xấp xỉ thô (raw volume * adj_close), chấp nhận méo lịch sử do đây là Cross-sectional Rank theo ngày.
4. Chạy placebo toàn pipeline: Đã code script `v13_fama_macbeth.py --placebo` chuẩn bị chạy.
5. Điền các mục [TBD], ghi prediction, re-freeze hash nếu panel đổi: Đã điền Prediction. Hash không đổi.

## 11. Ràng buộc nghiên cứu
- Cấm thêm feature trong V13: RSI7/RSI21, Rev5, DD variants… Nếu RSI14 fail → V13 kết thúc.
- Feature khác chỉ được mở ở V14 với câu hỏi nghiên cứu mới.
- Mọi biến thể đã chạy phải ghi vào `CONTRARIAN_V13_SPECIFICATION_LOG.md` (kể cả bị bỏ).
- Không quay lại chỉnh feature/threshold sau khi mở OOS.
- Chi phí giao dịch, turnover, portfolio construction: CHỈ làm nếu có confirmation ở OOS.

## 12. Thứ tự thực hiện
Giải quyết 4,150 ngày → panel integrity & purge/min-N → xác nhận ADV → chốt [TBD] →
placebo → prediction log → freeze (hash) → chạy Discovery một lần → (nếu đạt) OOS một lần →
pooled 2018–2026 estimate.

## 13. Outcome (Post-Execution)
V13: OOS inconclusive. Không có bằng chứng về momentum tradable của RSI14 sau controls trên universe 56 mã (λ = 0.0047, t = 0.62, CI rộng chứa cả 0 và giá trị Discovery). Power OOS không đủ để xác nhận hiệu ứng cỡ Discovery. 
Theo quy tắc đã ghi, V13 đóng. Không triển khai, không tinh chỉnh feature trên V13. 
Pooled estimate 2018–2026 (nếu có tính) chỉ còn giá trị mô tả, không phải bằng chứng do OOS đã thất bại trong việc xác nhận.

Bài học rút ra từ V11-V13: Với universe bị giới hạn ở 56 mã sống sót, statistical power quá yếu để có thể xác nhận các hiệu ứng nhỏ (cỡ 0.01–0.02) trên một tập OOS ngắn. Bất kỳ V14 nào trong tương lai chỉ đáng mở nếu có sự thay đổi về mặt Dữ liệu (Universe mở rộng >= 150-200 mã, có PIT liquidity, bao gồm cả mã hủy niêm yết) và phải tính toán Minimum Detectable Effect (MDE) trước khi chạy.