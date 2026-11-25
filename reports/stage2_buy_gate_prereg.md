# Pre-Registration Giai đoạn 2: Thử nghiệm Shadow Cổng `BUY` & Bộ lọc Regime (v2.0)

**Lịch sử Phiên bản Khóa:**
* **v1.0 (`2026-11-12`):** Bản khởi thảo trước khi đóng sổ Giai đoạn 1 (được lưu nguyên trạng trong lịch sử git tại tag `pre-reg-v1.1-20261112` / commit `bde3793` và `00690d3`).
* **v2.0 (`2026-11-25` — Bản khóa hiện hành trước Phiên 31):** Cập nhật chính thức sau khi quan sát kết quả đóng sổ 30 phiên Giai đoạn 1 (`2026-10-14 → 2026-11-25`, ghi nhận vào `data/snooping_counter.json` mục `S9_STAGE2_V2_DESIGN`, counter `#95`). Bổ sung nhánh phản thực tế `Counterfactual Pass-6-Gates`, logging `raw score` toàn bộ 55 mã, `Rank IC` (toàn rổ & nội ngành), đối chứng kép, ngưỡng tối thiểu `>= 15` ngày có tín hiệu và quy cách Logger Bảng 1 / Bảng 2.

**Trạng thái hiện tại:** **CHƯA KÍCH HOẠT** — Phiên 30 của Giai đoạn 1 đã chốt vào ngày `2026-11-25` (do `24/11` nghỉ lễ); 5 cohort hậu kiểm `18/11 → 25/11` đáo hạn `T+5` đầu tháng 12/`2026-12-02`. **Ngày $T_0$ đầu tiên dự kiến của Giai đoạn 2 (Phiên 31): `2026-11-26`** *(nếu phiên `26/11` chưa kịp chạy logger trước giờ mở cửa `T+1`, ngày $T_0$ đầu tiên tự động lùi sang phiên giao dịch kế tiếp — tuyệt đối không backfill đưa vào mẫu chính thức)*.  
**Mục tiêu nghiên cứu:** Phân tách độc lập giữa *(1) năng lực chọn cổ phiếu của 6 cổng nội tại trong Downtrend* (qua `Counterfactual Pass-6-Gates` & `Raw Score` 55 mã) và *(2) tác động của việc nới lỏng có kiểm soát cổng `GATE_MACRO_REGIME`* (`Arm A, B, C`), đồng thời kiểm soát rủi ro sụt giảm (`Drawdown`).

---

## 1. Công bố Giả thuyết Khám phá Sau Xem Dữ liệu (Post-Hoc Disclosure)

> [!WARNING] Cảnh báo Phương pháp luận & Đếm Thử nghiệm (Snooping Counter #95)
> * **Nguồn gốc giả thuyết:** Thiết kế v1.0 (`12/11`) dựa trên 22 phiên đầu và thiết kế v2.0 (`25/11`) được điều chỉnh sau khi đã quan sát đủ **30 phiên giao dịch** (`14/10/2026 → 25/11/2026`) của Giai đoạn 1 (đã ghi nhận thêm `S8`, `S9` vào [snooping_counter.json](file:///c:/Users/Window/Desktop/Stock%20-%20learning/data/snooping_counter.json), đưa tổng số lên **95**).
> * **Thừa nhận chịu ảnh hưởng dữ liệu đối với Chỉ tiêu Chính v2.0:** Việc chuyển trọng tâm chỉ tiêu chính sang nhánh `Counterfactual Pass-6-Gates` trong bản v2.0 là quyết định **chịu ảnh hưởng trực tiếp từ dữ liệu 30 phiên** (sau khi biết `VN-Index` đang ở `-5.35%` dưới `MA200` khiến `Arm A` và `Arm C` nhiều khả năng cho `0` lệnh). Kể từ sau thời điểm commit/tag bản v2.0 trước phiên `2026-11-26`, **`Counterfactual Pass-6-Gates` được giữ làm chỉ tiêu quyết định duy nhất — nghiêm cấm bổ sung hoặc thay đổi chỉ tiêu quyết định nào khác**.
> * **Tính chất trong mẫu (In-Sample):** Mọi dữ liệu lịch sử hoặc backfill giai đoạn `14/10/2026 → 25/11/2026` chỉ được gắn nhãn **`EXPLORATORY_IN_SAMPLE`**, tuyệt đối **không tính vào bằng chứng kiểm định Giai đoạn 2**.
> * **Ranh giới sạch:** Mọi kết luận Giai đoạn 2 chỉ tính trên dữ liệu mới phát sinh hoàn toàn từ ngày $T_0$ đầu tiên của Giai đoạn 2 (**đề xuất `2026-11-26`**, hoặc phiên kế tiếp nếu bỏ lỡ `26/11`) trở đi.

---

## 2. Định nghĩa Mã nguồn Tường minh của `SHADOW_BUY` & Luồng `Raw Score`

Một bản ghi chỉ được gán nhãn `pass_6_internal_gates = True` (`SHADOW_BUY` nội tại) khi thỏa mãn **toàn bộ 6 tầng cổng nội tại** trong kiến trúc 7 cổng sản xuất; cổng `GATE_MACRO_REGIME` được tách riêng theo từng nhánh:

```
[KIẾN TRÚC 7 CỔNG KIỂM SOÁT]
1. GATE_DATA_HEALTH: Dữ liệu giá/khối lượng/BCTC hợp lệ, không stale (Data Gate Pass)
2. GATE_FINANCIAL_HEALTH: Điểm tài chính đạt chuẩn, không cảnh báo nợ/dòng tiền
3. GATE_VALUATION_MOS: Biên an toàn định giá MoS >= 15.0%
4. GATE_TECHNICAL_MOMENTUM: Động lượng kỹ thuật đồng thuận:
   - Giá P >= MA100
   - Giá P >= MA20
   - Chỉ số RSI(14) >= 45.0
   - Khối lượng V >= 1.0 * MA20_Volume
5. GATE_QUANT_CONVICTION: Điểm định lượng Conviction >= 70 / 100
6. GATE_PM_VETO: Không vướng bẫy rủi ro (Bull Trap, Falling Knife, Veto)
---------------------------------------------------------------------------------
7. GATE_MACRO_REGIME: Cổng vĩ mô được đánh giá riêng theo Arm 0 / A / B / C hoặc bỏ qua ở nhánh Phản thực tế
```

### Chi tiết các Nhánh Thử nghiệm

| Nhánh | Định nghĩa điều kiện kích hoạt tại $T_0$ | Quy mô vị thế giả định | Phạm vi kết luận hợp lệ |
| :--- | :--- | :--- | :--- |
| **Arm 0 (Baseline)** | Theo logic đóng băng `v15.0`: `UPTREND` chuẩn (`VN-Index >= MA200`, `Slope(MA200) >= -0.5%`). | `0%` khi `DOWNTREND`; `100%` trần khi `UPTREND` | Nhánh đối chứng giữ `100% Cash (0.00%)` trong `DOWNTREND`. |
| **Arm A (MA200 Buffer)** | `vs MA200 >= -2.0%` **VÀ** `VN-Index > MA20` **VÀ** `Slope(MA20) > 0` tối thiểu `2` phiên liên tiếp (kèm 6 cổng nội tại). | Tối đa `50%` ngân sách (nửa Kelly) | Kiểm định nới cổng Macro sát `MA200`. |
| **Arm B (Hysteresis + Vol)** | `classify_regime_ma200_hysteresis` (`reentry_pct = +1.0%`, `confirmation_sessions = 2`, `vol_surge_mult = 1.3`) từ `regime_classifier.py` (kèm 6 cổng nội tại). | `75%–100%` ngân sách | Kiểm định hàm giảm whipsaw quanh `MA200`. |
| **Arm C (Breadth Floor)** | `vs MA200 >= -3.0%` **VÀ** tỷ lệ mã trên `MA20 >= 40%` tối thiểu `2` phiên liên tiếp (kèm 6 cổng nội tại). | Tối đa `50%` ngân sách | Kiểm định độ rộng thị trường dưới `MA200`. |
| **Counterfactual Pass-6-Gates** | Bỏ qua hoàn toàn `GATE_MACRO_REGIME`; kích hoạt mọi mã thỏa mãn `pass_6_internal_gates = True`, **kể cả khi cổng Macro đóng**. | Giả lập `Open_T+1 → Close_T+h` | **Chỉ đo năng lực chọn mã trong Downtrend**, **KHÔNG** đo việc nới cổng Macro (xem ràng buộc bên dưới). |

> **Giới hạn diễn giải bắt buộc đối với `Counterfactual Pass-6-Gates`:**
> Vì nhánh này bỏ qua hoàn toàn cổng vĩ mô, nó chỉ kiểm định hiệu quả chọn cổ phiếu trong pha suy thoái chứ không kiểm định quy tắc mở cổng Macro. Nếu `Counterfactual Pass-6-Gates` đạt chỉ tiêu chính, kết luận đúng chỉ là: *"các mã qua 6 cổng nội tại có lãi ròng dương trong Downtrend"*. **Kết quả đó chưa đủ căn cứ để tự động mở cổng `BUY` khi `VN-Index` đang cách `-5%` dưới `MA200`** — việc mở cổng vĩ mô vẫn đòi hỏi kiểm định qua `Arm A/B/C` hoặc pha chuyển tiếp riêng.

---

## 3. Thực tế Mẫu Khám phá 22–30 Phiên (Baseline Mô tả — In-Sample)

* Trên `22` phiên đầu (`14/10–12/11`, `93` bản ghi `conviction >= 70`): `43` lượt thỏa mãn 6 cổng nội tại (chặn bởi Macro) thu hẹp sau cooldown 5 phiên còn `16` tín hiệu (`14/16` Ngân hàng, `2/16` BĐS dân dụng) với `Exec T+5 = +0.02%` (`-0.38%` sau phí); `50` lượt còn lại trượt kỹ thuật ($P < MA100$ hoặc $RSI < 45$).
* Trên trọn `30` phiên Giai đoạn 1 (`14/10–25/11`): `BUY = 0` cả `30/30` phiên; `25` cohort `T+5` (`14/10–17/11`) cho verdict `FAIL / INCONCLUSIVE` (`W−R` 5 chuỗi = `+0.28%`, `WATCH` sau phí `-0.72%`); `VN-Index` kết phiên `25/11` ở `-5.35%` dưới `MA200`.
* Nếu trong 60 phiên Giai đoạn 2 `VN-Index` vẫn nằm dưới `-2% / -3%`, `Arm A` và `Arm C` nhiều khả năng cho `0` lệnh (`INSUFFICIENT_SAMPLE` do cổng Macro đóng). Khi đó, **bộ log `raw score` 55 mã + dòng `Counterfactual Pass-6-Gates`** là sản phẩm khoa học trung tâm của Giai đoạn 2.

---

## 4. Quy mô Mẫu, Số Ngày Tối thiểu & Quy tắc Độc lập

* **Đồng hồ Thời gian Độc lập:** Bắt đầu đếm $T=1$ từ **ngày $T_0$ đầu tiên của Giai đoạn 2 (đề xuất `2026-11-26`)**, tách biệt hoàn toàn với đồng hồ 30/60 phiên của Giai đoạn 1.
* **Cỡ mẫu tối thiểu (khóa kép cả số lệnh lẫn số ngày có tín hiệu):**
  * Tối thiểu **`20` tín hiệu độc lập** (theo cooldown `5` phiên mỗi mã) đã đáo hạn `T+5` và `T+10`, **VÀ**
  * Tối thiểu **`>= 15` ngày $T_0$ phát sinh tín hiệu** đã đáo hạn `T+5` (vì với ~30 ngày và khối `L=5` chỉ có ~6 khối, quá ít ngày có tín hiệu sẽ làm bootstrap suy biến và các lệnh Ngân hàng cùng ngày tương quan mạnh).
* **Đơn vị khối Bootstrap:** Mọi suy diễn thống kê (`Moving-Block Bootstrap`, `L=5`) bắt buộc dùng **ngày giao dịch $T_0$** làm đơn vị khối (block unit) nhằm xử lý tương quan chéo cùng phiên của nhóm Ngân hàng.
* **Gia hạn & Trạng thái `INSUFFICIENT_SAMPLE`:** Chạy tối thiểu `30` phiên mới; nếu chưa đạt ngưỡng mẫu có thể gia hạn tối đa tới `60` phiên (`MIN_SHADOW_SESSIONS = 60`). Nếu sau `60` phiên vẫn `< 20` tín hiệu độc lập **HOẶC** `< 15` ngày có tín hiệu (hoặc cổng Macro không mở), nhánh đó nhận kết luận chính thức **`INSUFFICIENT_SAMPLE`** — là kết quả hợp lệ, **tuyệt đối không hạ ngưỡng**.
* **Cảnh báo Chế độ Thị trường & Quy tắc Chuyển tiếp Pha Tăng (`UPTREND`):**
  * Nếu toàn kỳ Giai đoạn 2 vẫn nằm trong `DOWNTREND`, mọi kết luận chỉ có giá trị **có điều kiện (`Downtrend-Only Conditional`)**.
  * **Nếu thị trường chuyển sang `UPTREND` trong lúc đang chạy (`VN-Index >= MA200`, `Slope(MA200) >= -0.5%`):** `Arm 0` (sản xuất) sẽ bắt đầu giải ngân theo quy tắc đóng băng. Toàn bộ các nhánh `SHADOW` và `raw score` vẫn tiếp tục được ghi nhận và tính toán liên tục, nhưng kết quả bắt buộc phải **bóc tách báo cáo có điều kiện riêng theo từng pha (`DOWNTREND` vs `UPTREND`)**, không gộp chung thành một con số hỗn hợp duy nhất.

---

## 5. Báo cáo Kép & Kiểm soát Tập trung Ngành

1. **Đối chứng Kép & Đối chứng Cùng Ngành Bắt buộc (`Dual & Within-Sector Control` — cùng Cohort $T_0$):**
   Mỗi cohort $T_0$ có tín hiệu `SHADOW_BUY` / `Counterfactual Pass-6-Gates` phải đối chiếu song song với các rổ trong đúng ngày $T_0$ đó:
   * **`Universe (55 mã)`** (`SHADOW − Universe`)
   * **`WATCH-không-qua-cổng` toàn rổ** (`SHADOW − WATCH_Failed_Internal`)
   * **Đối chứng Cùng Ngành (`Within-Sector Control` — Bắt buộc):** Vì `WATCH_Failed_Internal` chứa tỷ trọng lớn nhóm BĐS dân dụng còn `SHADOW` chủ yếu là Ngân hàng, phải báo cáo bản đối chứng sạch trong **cùng ngành**: **`SHADOW (Ngân hàng) − WATCH_Failed_Internal (Ngân hàng)`** (và tương tự cho Phi ngân hàng nếu có mẫu) để không bị nhiễu so sánh chéo Ngân hàng vs BĐS.
2. **Hiệu chỉnh Ngành / Thị trường (`Market & Sector Adjusted`):** Báo cáo thêm lợi suất vượt **trung bình ngành cùng ngày** (`Excess vs Same-Day Sector Mean`) và **trung bình Universe cùng ngày** (`Excess vs Same-Day Universe`) nhằm tách riêng yếu tố beta.
3. **Chẩn đoán `Ex-Banking` (chỉ mô tả):** Do tín hiệu ngoài Ngân hàng trong Downtrend rất khan hiếm, nhánh `Ex-Banking` chỉ mang tính chẩn đoán mô tả, **không dùng làm tiêu chí đỗ/trượt định lượng**.
4. **Ràng buộc Phân loại Tốt nghiệp (Sector Independence):**
   * **`GRADUATED_SYSTEM_WIDE`:** Không ngành đơn lẻ nào chiếm `> 60%` số tín hiệu độc lập.
   * **`GRADUATED_BANKING_SPECIFIC`:** Nếu Ngân hàng chiếm `> 60%` và nhánh đạt đủ ngưỡng định lượng (Chỉ tiêu chính Net $T+5 > 0\%$ với Block CI low $> 0\%$, Net $T+10 > 0\%$, Net Hit Rate $\ge 50\%$, Max Drawdown mô tả $\le -5.0\%$), chỉ công nhận có điều kiện riêng cho Ngân hàng và **cấm mở rộng sang ngành khác** cho tới khi tích lũy đủ $\ge 10$ tín hiệu phi ngân hàng độc lập.

---

## 6. Chỉ số Đánh giá, `Rank IC` & Chống `Threshold Mining`

### Chỉ tiêu Chính Duy nhất (Single Primary Metric — Chống Đa kiểm định)
* **Primary Metric:** **`Net Excess Return` ở kỳ hạn `T+5` (`Open_T+1 → Close_T+5` trừ `0.40%` phí)** của duy nhất nhánh **`Counterfactual Pass-6-Gates`** (với điều kiện đạt đủ `>= 15` ngày $T_0$ có tín hiệu và `>= 20` tín hiệu độc lập), kiểm định bằng **`Moving-Block Bootstrap (L=5)` theo ngày $T_0$**:
  * Yêu cầu: `Mean(Net Exec T+5) > 0.00%` **VÀ** `Block 95% CI_low > 0.00%`.
* **Phạm vi loại trừ nghiêm ngặt:** Toàn bộ các nhánh Macro (`Arm A`, `Arm B`, `Arm C`) và kỳ hạn khác (`T+10`) **nằm hoàn toàn ngoài quyết định chính** (chỉ là chẩn đoán mô tả/phụ trợ, không có điều kiện đủ mẫu riêng để chia tách hay thay thế quyết định chính; nếu trích dẫn thành phát hiện mới phải hiệu chỉnh Holm-Bonferroni).

### Chỉ tiêu Liên tục (`Rank IC` Toàn rổ & Nội ngành) + Chống `Threshold Mining`
1. **`Spearman Rank IC` toàn rổ & theo ngành (`Sector-Neutral`):**
   * Tính hệ số tương quan thứ hạng Spearman hàng ngày tại $T_0$ giữa **`conviction`** (và riêng **`mos_pct`**) với `Exec T+5` (phụ trợ `T+10`) trên **toàn bộ 55 mã**.
   * Bắt buộc báo cáo song song **`Sector-Neutral Rank IC`** (tính tương quan thứ hạng trong nội bộ từng nhóm ngành, đặc biệt nội bộ 10 mã Ngân hàng và nhóm Phi ngân hàng) để loại bỏ nhiễu xếp hạng liên ngành.
   * **Vai trò quyết định & Cách đọc:** `Rank IC` đóng vai trò **chỉ tiêu chẩn đoán phụ trợ (Diagnostic Evidence — không ghi đè Primary Metric)**. Được công nhận là có bằng chứng năng lực xếp hạng tích cực khi và chỉ khi **`Mean Daily Rank IC > 0.00` VÀ cận dưới `95% Block Bootstrap CI (L=5 theo ngày T0) > 0.00`** trên cả chuỗi **`Sector-Neutral Rank IC`**. Nếu trượt điều kiện này trong khi `Counterfactual Pass-6-Gates` dương, ghi nhận kết quả phụ thuộc vào ngưỡng cắt nhị phân chứ chưa chứng minh được tính đơn điệu toàn rổ.
2. **Quy tắc Chống `Threshold Mining`:**
   * Giữ cố định toàn bộ ngưỡng (`conviction >= 70`, `MoS >= 15%`, `RSI >= 45`). Nếu dùng kho `raw score` 55 mã để tìm ngưỡng tối ưu mới, **bắt buộc chia mẫu theo thời gian**: tập khám phá ban đầu và tập kiểm định ngoài mẫu hoàn toàn mới trên các phiên sau.

### Định nghĩa `Max Drawdown` (Chỉ tiêu Mô tả)
* Tính trên chuỗi NAV giả lập của **danh mục đều trọng số theo cohort ngày** (giữ 5 phiên, mỗi ngày $T_0$ kích hoạt cấp tối đa `1/5` vốn chia đều cho các mã kích hoạt trong ngày; ngày không có tín hiệu giữ `0%`). Coi ngưỡng `-5.0%` là **chỉ tiêu mô tả/cảnh báo rủi ro** cho tới khi đủ số cụm ngày độc lập.

---

## 7. Quy cách Kỹ thuật Logger `Raw Score` Giai đoạn 2 (Bước 4 — Chỉ Cài Sau Khi Rà Soát Xong)

### Nguyên tắc Vận hành & Chống Look-Ahead
1. **Neo theo lịch giao dịch thực:** Chỉ chạy vào ngày giao dịch thực sự có khớp lệnh EOD hợp lệ; **từ chối chạy vào ngày nghỉ lễ / cuối tuần**.
2. **Dấu thời gian chống nhìn trước (`No Look-Ahead`):** Chỉ đọc dữ liệu tính đến `Close_T0`, ghi nhận trường `logged_at` (ISO timestamp **trước giờ mở cửa `T+1`**) làm bằng chứng không biết kết quả tương lai.
3. **Append-only, Toàn vẹn `rows == 55` & Schema Version:**
   * Ghi tách biệt hoàn toàn khỏi `canonical_forward_returns_*.csv`, đánh dấu `schema_version = "2.0.0"` ở cả hai bảng.
   * **Kiểm tra `rows == 55` trước khi ghi:** Trước mỗi lần ghi/append Bảng 1, bắt buộc assert **`len(rows) == 55`**; nếu khác `55`, **dừng ngay và báo lỗi**, tuyệt đối không ghi dở dữ liệu.
   * Chạy lại cùng một ngày giao dịch phải **idempotent** (không nhân đôi dòng), xuất mã băm `SHA256` và commit sau mỗi phiên.
4. **Nối lợi suất tương lai tách rời:** Logger tại $T_0$ **không** chứa cột lợi suất tương lai; các giá trị `exec_t1..t20` được ghép nối sau bởi một job hậu kiểm độc lập khi các kỳ hạn đáo hạn.
5. **Quy ước giá & Kiểm thử hồi quy Logger:**
   * Ghi rõ giá là giá điều chỉnh hay chưa điều chỉnh (`price_adjusted`), nhất quán với bảng canonical.
   * Bộ test hồi quy cho logger (trước khi chạy chính thức) bắt buộc phủ tối thiểu: *(a) ngày sau nghỉ lễ*, *(b) ngày có mã tạm ngừng giao dịch / thiếu dữ liệu (`missing_reason`)*, và *(c) chạy lại cùng ngày (`idempotent`, không nhân đôi dòng)*.
6. **Gắn nhãn Backfill:** Nếu chạy backfill dữ liệu `2026-10-14 → 2026-11-25`, bắt buộc gắn nhãn `sample_role = EXPLORATORY_IN_SAMPLE` và tuyệt đối tách khỏi mẫu Giai đoạn 2 (`sample_role = STAGE2_PROSPECTIVE`).

### Bảng 1: Chi tiết Theo Mã (`55` dòng mỗi ngày giao dịch, không bỏ dòng thiếu dữ liệu)
* **Định danh & Phiên bản:** `schema_version`, `date_t0`, `entry_date_t1`, `symbol`, `sector`, `logic_version`, `commit`, `logged_at`, `price_adjusted`, `sample_role`.
* **Quyết định sản xuất:** `decision`, `watch_reason` *(nguyên văn)*, `rejection_gate`.
* **Điểm thô & Chỉ báo $T_0$:** `conviction`, `mos_pct`, `rsi_14`, `close`, `ma20`, `ma100`, `volume`, `ma20_volume`, `pct_vs_ma20`, `pct_vs_ma100`, `vol_vs_ma20`.
* **Cổng kiểm soát `1..6`:** cờ đỗ/trượt tường minh cho từng cổng (bao gồm `gate_data_health`, `gate_financial_health`, `gate_mos`, `gate_tech_momentum`, `gate_conviction`, `gate_pm_veto`, cùng các cờ chi tiết `flag_bull_trap`, `flag_falling_knife`, `flag_veto`) và cờ tổng hợp `pass_6_internal_gates`.
* **Phân nhóm đối chứng:** `group ∈ {SHADOW, WATCH_FAILED_INTERNAL, REJECT}`.
* **Xử lý thiếu dữ liệu:** Luôn ghi đủ cả `55` dòng (kể cả mã tạm ngừng giao dịch / thiếu chỉ báo) kèm cột `missing_reason`, tuyệt đối không bỏ qua âm thầm.

### Bảng 2: Trạng thái Thị trường Theo Ngày (`1` dòng mỗi ngày giao dịch)
* **Định danh & Chỉ số VN-Index:** `schema_version`, `date_t0`, `vn_close`, `vn_ma20`, `vn_ma200`, `vn_vs_ma200_pct`, `slope_ma20`, `slope_ma200`.
* **Độ rộng thị trường:** `breadth_pct_above_ma20` (tỷ lệ mã trong Universe 55 mã đóng cửa trên `MA20`).
* **Trạng thái các nhánh Macro:** cờ mở cổng tại $T_0$ (`arm_a_open`, `arm_b_open`, `arm_c_open`) và bộ đếm số phiên xác nhận liên tiếp (`arm_a_streak`, `arm_b_streak`, `arm_c_streak`) được ghi nguyên giá trị thời gian thực, không tính lại hồi tố.
* **Kiểm tra toàn vẹn:** `is_trading_day`, `universe_hash`, `logged_at`.
