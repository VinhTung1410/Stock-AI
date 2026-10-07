# CONTRARIAN_V14 — Data Feasibility → Power → PIT Universe → Alpha

## 0. Trạng thái
DRAFT. Chưa viết code discovery. V13 đã đóng (OOS inconclusive: λ=0.0047, t=0.62).

## 1. Câu hỏi nghiên cứu
Trong universe cổ phiếu giao dịch được và point-in-time (PIT), các đặc trưng cross-sectional có dự báo
excess return 20 phiên sau khi kiểm soát beta, ngành, size/thanh khoản không?
V14 KHÔNG phải "RSI phiên bản mới": mục tiêu là đổi môi trường dữ liệu để trả lời được câu hỏi về alpha.

## 2. Nguyên tắc
Không mở alpha research cho đến khi chứng minh được: (1) dữ liệu tồn tại, (2) universe xây được PIT,
(3) thiết kế đủ power phát hiện effect có ý nghĩa kinh tế.

## 3. Các Gate (theo thứ tự)
- Gate 0 — Data feasibility & cost: ma trận nguồn → trường dữ liệu → PIT? → coverage → chi phí → thời gian → fallback.
  Cần: adjusted OHLC, volume, mã đã hủy niêm yết, ngày niêm yết/hủy, lịch sử ngành, shares/market cap,
  fundamentals + ngày công bố, đình chỉ/cảnh báo.
  Thiếu fundamentals PIT → bỏ Value/Quality. Thiếu delisted/listing date → block PIT V14.
  Không có nguồn đạt chuẩn trong ngân sách → STOP, kết luận "không đủ dữ liệu PIT".
  Không gọi dữ liệu thiếu là PIT.
- Gate 0B — Historical audit: giải quyết blocker số ngày (4,150 vs ~2,343 kỳ vọng): earliest/latest date,
  unique dates, mã/ngày, số dòng, dòng trùng. Nếu có dữ liệu tin cậy 2010–2014: khóa làm mẫu xác nhận phụ
  TRƯỚC khi nhìn kết quả (thị trường khác cơ cấu, không tương đương OOS hiện đại). Không đủ tin cậy → bỏ.
- Gate 1 — MDE/power: mô phỏng MDE = f(N, T, tương quan thời gian, tương quan chéo/ngành, chồng lấn 20D,
  missingness, dispersion thực). Chưa dùng feature nào. Bảng sơ bộ (chỉ sanity check): N=56 → MDE ~0.035;
  N=200 → ~0.020. Nút thắt là số kỳ độc lập T, không chỉ số mã.
- Gate 2 — Economic floor: tính ngưỡng alpha tối thiểu sau phí, thuế, slippage, bid/ask, turnover.
  Điều kiện: Effect > max(MDE, EconomicFloor). Nếu MDE > floor → STOP.
- Gate 3 — PIT tradable universe: tại ngày D: đang niêm yết và giao dịch, không đình chỉ, không vi phạm quy tắc
  cảnh báo đã định, ADV60 chỉ dùng dữ liệu ≤ D, giữ top K theo ADV60. K ∈ {150, 200, 300} chọn từ Gate 1,
  không chọn theo kết quả alpha. Trạng thái tường minh: eligible / suspended / delisted / missing / not-yet-listed
  (không dropna ngầm).
- Gate 4 — Test budget (freeze trước discovery): 6 families / ~21 features:
  Momentum (1M,3M,6M,12M), Reversal (1D,5D,20D), Risk (Vol20,Vol60,Beta60,DD60),
  Liquidity (ADV20,ADV60,turnover), Value (E/P,B/P,FCF/P), Quality (ROE,ROA,margin,leverage).
  Con số chính xác chốt trước. Không thêm feature sau khi mở discovery.
- Gate 5 — Multiple testing: Discovery dùng BH/FDR → candidate set → specification lock →
  Forward/OOS dùng Holm/FWER. Ghi trước khi nhìn kết quả.
- Gate 6/7 — Horizon & rebalance: primary 20 phiên (là research horizon, không phải chân lý kinh tế);
  5D/60D chỉ là secondary đã đăng ký trước. Rebalance mỗi 20 phiên: xếp hạng → top quintile → giữ 20 phiên.
- Gate 8 — Long-only economics: primary = top quintile − universe (hoặc VW universe). Long-short chỉ là diagnostic.
  Báo cáo gross/net, turnover, chi phí, hit rate, max DD, Sharpe, exposure, capacity.
- Gate 9/10 — Forward validation: expanding-window discovery → FREEZE → locked forward.
  2024–2026 gắn nhãn `contaminated_forward` (V11 đã dùng). Bằng chứng sạch chỉ có 2 nguồn:
  (A) dữ liệu trước 2015 nếu audit chứng minh có và khóa trước discovery;
  (B) forward live: ghi tín hiệu từ ngày freeze T0, chờ 20 phiên, ghi kết quả, không sửa model.
- Gate 11 — Thống kê: Fama–MacBeth đồng thời với beta + size + industry + liquidity; Newey–West (lag ≥ 20)
  là primary; robustness: kết quả không chồng lấn 20D và block bootstrap (L ≥ 20). Bootstrap không tạo thêm thông tin
  độc lập; T hiệu dụng cho MDE tính riêng.

## 4. Tiêu chí candidate (Discovery)
Đúng dấu; vượt max(MDE, EconomicFloor); qua BH; ổn định theo năm; không do outlier; không biến mất sau controls.

## 5. Tiêu chí OOS/forward
Cùng dấu; effect ≥ 50% Discovery; t ≥ 1.645 (strong: t ≥ 2.0); qua Holm trên candidate set.

## 6. Prediction log (viết trước khi chạy)
Sau khi giảm survivorship và tăng breadth, các hiệu ứng thấy ở V12–V13 sẽ giảm về độ lớn. Chỉ effect vượt MDE
và sống sót multiple-testing mới là candidate. Nếu tất cả fail, V14 vẫn PASS về phương pháp.
[TBD: thêm xác suất/số dự đoán cụ thể]

## 7. Diễn giải kết quả
Nếu fail: "Trong universe giao dịch được, giai đoạn, horizon và tập feature đã kiểm định, không phát hiện
hiệu ứng ≥ MDE sau khi kiểm soát các exposure đã định trước." KHÔNG kết luận "VN không có cross-sectional alpha".

## 8. Thứ tự hành động (chưa viết V14_DISCOVERY.py)
1. Data-source matrix (Gate 0).
2. Historical audit (Gate 0B).
3. MDE simulation trên cấu trúc tương quan thật của panel.
4. Từ MDE: chọn K, horizon, rebalance, economic floor.
5. Freeze specification + hash → mở Discovery.
