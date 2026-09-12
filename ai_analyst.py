import os
import json
import logging
from dotenv import load_dotenv
from google import genai
from data_engine import load_portfolio, evaluate_portfolio, fetch_macro_news

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.6-flash"  # Model tối ưu tốc độ, context và free tier của Gemini


def get_ai_client():
    if not GEMINI_API_KEY:
        raise ValueError("Chưa cấu hình GEMINI_API_KEY trong file .env!")
    return genai.Client(api_key=GEMINI_API_KEY)


def generate_portfolio_analysis(portfolio_df, news_items, custom_question: str = None) -> str:
    """
    Tạo báo cáo phân tích toàn diện kết hợp Danh mục, Chỉ báo Kỹ thuật và Tin tức Vĩ mô.
    """
    client = get_ai_client()

    portfolio_str = portfolio_df.to_string(index=False)
    news_str = "\n".join([f"- [{n['keyword'].upper()}] {n['title']}" for n in news_items[:6]])

    prompt = f"""Bạn là Chuyên gia Trưởng Ban Chiến lược Đầu tư Chứng khoán với hơn 15 năm kinh nghiệm thực chiến tại thị trường Việt Nam (HSX, HNX).
Dưới đây là dữ liệu giao dịch và trạng thái danh mục thực tế của Nhà đầu tư:

=== BẢNG TRẠNG THÁI DANH MỤC HIỆN TẠI ===
{portfolio_str}

=== TIN TỨC VĨ MÔ & NGÀNH NỔI BẬT TRONG 24H QUA ===
{news_str}

Nhiệm vụ của bạn:
1. **Đánh giá sức khỏe danh mục:** Nhận xét từng mã (BSR, MSB, SSI). Phân loại mã nào đang giữ nhịp tốt, mã nào rủi ro gãy nền cần lưu ý giá vốn.
2. **Tác động Tin vĩ mô & Ngành:** Tin tức về giá dầu, lãi suất, tỷ giá đang hỗ trợ hay tạo áp lực lên từng mã trong danh mục?
3. **Kịch bản hành động cụ thể (Rõ ràng từng mốc):**
   - **T+ (Ngắn hạn):** Điểm chốt lời ngắn hạn (Take Profit) và điểm quản trị rủi ro/cắt lỗ (Stop Loss) cụ thể theo giá thị trường.
   - **Trung hạn (3 - 6 tháng):** Chiến lược cơ cấu, gia tăng tỷ trọng hay hạ bớt.
4. **Ngành/Cổ phiếu tiềm năng:** Gợi ý ngắn gọn 1 nhóm ngành đang có dòng tiền hoặc hưởng lợi vĩ mô để chuẩn bị đón sóng.

Yêu cầu định dạng đặc biệt cho Discord & Web:
- TUYỆT ĐỐI KHÔNG DÙNG BẢNG MARKDOWN (| Cột | Cột |) vì Discord không hỗ trợ hiển thị bảng và sẽ bị vỡ nát trên điện thoại.
- TUYỆT ĐỐI KHÔNG DÙNG DẤU `###`. Thay bằng tiêu đề in đậm rõ ràng (Ví dụ: `**I. ĐÁNH GIÁ SỨC KHỎE DANH MỤC**`).
- Dùng bullet point dạng `• ` hoặc `> ` kèm emoji để tạo giao diện trực quan, sang trọng.
- Chia rõ ràng 4 mục lớn:
  **I. ĐÁNH GIÁ SỨC KHỎE DANH MỤC**
  **II. TÁC ĐỘNG VĨ MÔ & DÒNG TIỀN**
  **III. KỊCH BẢN & CHIẾN LƯỢC HÀNH ĐỘNG**
  **IV. CỔ PHIẾU / NGÀNH ĐÓN SÓNG TIỀM NĂNG**
"""

    if custom_question:
        prompt += f"\n\n[CÂU HỎI BỔ SUNG CỦA NHÀ ĐẦU TƯ]: {custom_question}\nHãy trả lời chi tiết trọng tâm câu hỏi này."

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text


if __name__ == "__main__":
    print("=== KIỂM TRA PHÂN TÍCH VỚI GEMINI ===")
    portfolio = load_portfolio()
    df_eval = evaluate_portfolio(portfolio)
    news = fetch_macro_news()
    
    print("Đang gửi dữ liệu đến Gemini...")
    analysis = generate_portfolio_analysis(df_eval, news)
    print("\n--- BÁO CÁO PHÂN TÍCH TỪ GEMINI ---")
    print(analysis)
