-- Cập nhật bảng decision_records để phục vụ truy vết AI (Audit Trail) cho Version 6.4

-- 1. Thêm cột prompt_version để lưu phiên bản prompt được dùng tại thời điểm phân tích
ALTER TABLE decision_records
ADD COLUMN IF NOT EXISTS prompt_version VARCHAR(50);

-- 2. Thêm cột model_version để theo dõi version của LLM (VD: gemini-1.5-pro-002)
ALTER TABLE decision_records
ADD COLUMN IF NOT EXISTS model_version VARCHAR(50);

-- 3. Thêm cột raw_response để lưu trữ toàn bộ văn bản trả về chưa qua xử lý của LLM,
--    giúp đối chiếu (Audit) và phát hiện ảo giác (Hallucination)
ALTER TABLE decision_records
ADD COLUMN IF NOT EXISTS raw_response TEXT;

-- Bổ sung index để tăng tốc độ truy vấn theo model_version nếu cần
CREATE INDEX IF NOT EXISTS idx_decision_records_model_version ON decision_records(model_version);
