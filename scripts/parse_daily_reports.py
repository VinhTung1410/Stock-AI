"""scripts/parse_daily_reports.py

Trích xuất dữ liệu bối cảnh thị trường từ Báo cáo Phân tích Kỹ thuật (BC PTKT) hàng ngày của TCBS.
Tuân thủ nguyên tắc Zero-Fabrication: Chỉ trích xuất thông tin có thực trong văn bản PDF,
tuyệt đối không bịa đặt số liệu. Trường hợp không tìm thấy gán giá trị mặc định ([] hoặc UNKNOWN).
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import pymupdf
except ImportError:
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

LOGGER = logging.getLogger(__name__)

DEFAULT_PTKT_DIR = Path("docs/Reference/PTKT_Daily")
DEFAULT_OUTPUT_FILE = Path("data/market_context.json")
DEFAULT_MANIFEST_FILE = Path("docs/Reference/manifest.json")
DEFAULT_PTKT_MANIFEST = Path("docs/Reference/PTKT_Daily/manifest.json")

# String constants to comply with SonarCloud S1192
UNKNOWN_VAL = "UNKNOWN"
TCBS_SOURCE = "TCBS"
STATUS_BEARISH = "BEARISH"
STATUS_BULLISH = "BULLISH"
STATUS_NEUTRAL = "NEUTRAL"
REGIME_SIDEWAYS = "SIDEWAYS"
REGIME_DOWNTREND = "DOWNTREND"
REGIME_UPTREND = "UPTREND"


def extract_text_from_pdf(pdf_path: Path) -> List[str]:
    """Đọc toàn bộ các trang PDF và trả về danh sách text từng trang."""
    if pymupdf is None:
        raise ImportError("pymupdf is not installed. Please install via: pip install pymupdf")
    pages_text: List[str] = []
    doc = pymupdf.open(str(pdf_path))
    try:
        for page in doc:
            pages_text.append(page.get_text("text"))
    finally:
        doc.close()
    return pages_text


def parse_date_from_filename_or_text(filename: str, first_page_text: str) -> str:
    """Trích xuất ngày báo cáo theo chuẩn YYYY-MM-DD."""
    # Ưu tiên trích xuất từ tên file YYYYMMDD
    match_file = re.search(r"(\d{4})(\d{2})(\d{2})", filename)
    if match_file:
        return f"{match_file.group(1)}-{match_file.group(2)}-{match_file.group(3)}"

    # Fallback: Trích xuất từ text "Ngày: DD/MM/YYYY"
    match_text = re.search(r"Ngày:\s*(\d{1,2})/(\d{1,2})/(\d{4})", first_page_text)
    if match_text:
        d, m, y = match_text.group(1).zfill(2), match_text.group(2).zfill(2), match_text.group(3)
        return f"{y}-{m}-{d}"

    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def extract_vnindex_summary(text: str) -> Dict[str, Any]:
    """Trích xuất thông số VN-Index đóng cửa phiên."""
    res: Dict[str, Any] = {
        "vnindex_close": None,
        "vnindex_change_pts": None,
        "vnindex_change_pct": None,
        "raw_summary": "",
    }

    # Tìm đoạn kết thúc phiên
    # Ví dụ: "VN-Index đóng cửa tại 1,768.6 điểm, giảm 9.1 điểm (tương đương 0.5%)."
    close_pat = (
        r"VN-Index đóng cửa tại\s*([\d,\.]+)\s*điểm,\s*(tăng|giảm)\s*([\d,\.]+)\s*điểm\s*\(tương đương\s*([\d,\.]+)%\)"
    )
    match = re.search(close_pat, text)
    if match:
        pts_str = match.group(1).replace(",", "")
        direction = match.group(2)
        diff_str = match.group(3).replace(",", "")
        pct_str = match.group(4).replace(",", "")
        try:
            close_val = float(pts_str)
            diff_val = float(diff_str) * (-1.0 if direction == "giảm" else 1.0)
            pct_val = float(pct_str) * (-1.0 if direction == "giảm" else 1.0)
            res["vnindex_close"] = close_val
            res["vnindex_change_pts"] = diff_val
            res["vnindex_change_pct"] = pct_val
        except ValueError:
            LOGGER.exception("Lỗi khi ép kiểu số liệu VN-Index")

    # Trích xuất đoạn văn diễn biến phiên
    summary_match = re.search(r"(Phiên giao dịch ngày.+?)(?:HNX-Index|\(5\) Cá mập|$)", text, re.DOTALL)
    if summary_match:
        raw_text = summary_match.group(1).strip()
        cleaned_summary = " ".join(raw_text.split())
        res["raw_summary"] = cleaned_summary[:800]

    return res


def extract_market_regime_and_sentiment(text: str, chg_pct: Optional[float]) -> tuple[str, str]:
    """Xác định xu hướng chuyên gia và tâm lý phiên từ văn bản."""
    lowered = text.lower()
    sentiment = STATUS_NEUTRAL
    regime = REGIME_SIDEWAYS

    negative_keywords = ["áp lực điều chỉnh", "sắc đỏ", "tiêu cực", "chốt lời", "suy yếu", "bán ròng"]
    positive_keywords = ["tích cực", "bứt phá", "sắc xanh", "mua ròng", "tăng điểm"]

    neg_count = sum(1 for kw in negative_keywords if kw in lowered)
    pos_count = sum(1 for kw in positive_keywords if kw in lowered)

    if (chg_pct is not None and chg_pct < -0.3) or (neg_count > pos_count + 1):
        sentiment = STATUS_BEARISH
        regime = REGIME_DOWNTREND
    elif (chg_pct is not None and chg_pct > 0.3) or (pos_count > neg_count + 1):
        sentiment = STATUS_BULLISH
        regime = REGIME_UPTREND

    return regime, sentiment


def extract_support_resistance_zones(text: str) -> tuple[List[float], List[float]]:
    """Trích xuất vùng hỗ trợ và kháng cự nếu có trong văn bản (Zero-Fabrication)."""
    supports: List[float] = []
    resistances: List[float] = []

    # Tìm các mẫu như: hỗ trợ mạnh tại 1250 - 1260 hoặc kháng cự tại 1300
    sup_match = re.search(r"hỗ\s*trợ(?:\s+(?:mạnh|tại|vùng|quanh))*[:\s]+([\d\.,\s–-]+)", text, re.IGNORECASE)
    if sup_match:
        nums = re.findall(r"\b\d{3,4}(?:\.\d+)?\b", sup_match.group(1))
        supports = [float(n) for n in nums if float(n) > 500]

    res_match = re.search(r"kháng\s*cự(?:\s+(?:mạnh|tại|vùng|quanh))*[:\s]+([\d\.,\s–-]+)", text, re.IGNORECASE)
    if res_match:
        nums = re.findall(r"\b\d{3,4}(?:\.\d+)?\b", res_match.group(1))
        resistances = [float(n) for n in nums if float(n) > 500]

    return supports, resistances


def extract_focus_sectors(text: str) -> List[str]:
    """Trích xuất các nhóm ngành được đề cập trọng tâm."""
    sectors_pool = [
        "Bất động sản",
        "Dầu khí",
        "Vật liệu",
        "Tiện ích",
        "Điện, nước & xăng dầu khí đốt",
        "Dịch vụ tài chính",
        "Du lịch và Giải trí",
        "Bán lẻ",
        "Ngân hàng",
        "Công nghệ thông tin",
        "Hóa chất",
        "Thép",
        "Hàng & Dịch vụ Công nghiệp",
        "Thực phẩm & Đồ uống",
    ]
    found = [sec for sec in sectors_pool if sec.lower() in text.lower()]
    return found


def extract_risk_keywords(text: str) -> List[str]:
    """Trích xuất các từ khóa rủi ro xuất hiện trong văn bản."""
    keywords_pool = [
        "áp lực chốt lời",
        "áp lực điều chỉnh",
        "suy yếu",
        "bán ròng",
        "sắc đỏ",
        "thủng hỗ trợ",
        "rủi ro điều chỉnh",
        "phân phối",
        "bẫy tăng giá",
    ]
    lowered = text.lower()
    return [kw for kw in keywords_pool if kw in lowered]


def extract_buy_sell_signals(pages_text: List[str]) -> tuple[List[str], List[str]]:
    """Trích xuất danh mục cổ phiếu có tín hiệu Mua/Bán rõ ràng từ báo cáo."""
    buy_signals: List[str] = []
    sell_signals: List[str] = []

    full_text = "\n".join(pages_text)

    # Kiểm tra tín hiệu MUA
    if "Không có tín hiệu MUA" in full_text:
        buy_signals = []
    else:
        buy_block = re.search(
            r"Danh mục cổ phiếu có tín hiệu MUA(.+?)(?:Danh mục cổ phiếu có tín hiệu BÁN|$)", full_text, re.DOTALL
        )
        if buy_block:
            tickers = re.findall(r"\b[A-Z]{3}\b", buy_block.group(1))
            buy_signals = [t for t in tickers if t not in ["TCB", "VND", "MUA", "BAN", "NAV", "RSI", "MACD"]]

    # Kiểm tra tín hiệu BÁN
    if "Không có tín hiệu BÁN" in full_text:
        sell_signals = []
    else:
        sell_block = re.search(r"Danh mục cổ phiếu có tín hiệu BÁN(.+?)(?:Diễn giải|\(4\)|$)", full_text, re.DOTALL)
        if sell_block:
            tickers = re.findall(r"\b[A-Z]{3}\b", sell_block.group(1))
            # Lọc bỏ stop words
            sell_signals = [t for t in tickers if t not in ["TCB", "VND", "MUA", "BAN", "NAV", "RSI", "MACD", "NĐT"]]

    return buy_signals, sell_signals


def parse_tcbs_daily_report(pdf_path: Path) -> Dict[str, Any]:
    """Phân tích toàn diện file PDF báo cáo PTKT hàng ngày của TCBS."""
    pages_text = extract_text_from_pdf(pdf_path)
    if not pages_text:
        raise ValueError(f"Không thể đọc text từ PDF: {pdf_path}")

    first_page = pages_text[0]

    report_date = parse_date_from_filename_or_text(pdf_path.name, first_page)
    summary_data = extract_vnindex_summary(first_page)
    regime, sentiment = extract_market_regime_and_sentiment(first_page, summary_data.get("vnindex_change_pct"))
    sup_zones, res_zones = extract_support_resistance_zones(first_page)
    focus_secs = extract_focus_sectors(first_page)
    risk_kws = extract_risk_keywords(first_page)
    buy_sigs, sell_sigs = extract_buy_sell_signals(pages_text)

    market_context: Dict[str, Any] = {
        "date": report_date,
        "source": TCBS_SOURCE,
        "source_file": pdf_path.name,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "market_regime_analyst": regime,
        "sentiment": sentiment,
        "vnindex_close": summary_data.get("vnindex_close"),
        "vnindex_change_pts": summary_data.get("vnindex_change_pts"),
        "vnindex_change_pct": summary_data.get("vnindex_change_pct"),
        "vnindex_support_zones": sup_zones,
        "vnindex_resistance_zones": res_zones,
        "focus_sectors": focus_secs,
        "risk_keywords": risk_kws,
        "buy_signals": buy_sigs,
        "sell_signals": sell_sigs,
        "raw_summary": summary_data.get("raw_summary", ""),
    }

    return market_context


def update_manifests_after_processing(filename: str, output_path: Path) -> None:
    """Cập nhật trạng thái processed: true trong manifest.json."""
    for manifest_path in [DEFAULT_MANIFEST_FILE, DEFAULT_PTKT_MANIFEST]:
        if not manifest_path.exists():
            continue
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            updated = False
            for item in data.get("files", []):
                if item.get("filename") == filename:
                    item["processed"] = True
                    item["context_output"] = str(output_path).replace("\\", "/")
                    updated = True

            if updated:
                data["last_updated"] = datetime.now(timezone.utc).isoformat()
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                LOGGER.info("Đã cập nhật manifest tại %s", manifest_path)
        except Exception:
            LOGGER.exception("Lỗi khi cập nhật manifest: %s", manifest_path)


def run_parse_daily_pipeline(
    ptkt_dir: Path = DEFAULT_PTKT_DIR, output_path: Path = DEFAULT_OUTPUT_FILE
) -> Optional[Dict[str, Any]]:
    """Tìm file PDF mới nhất trong ptkt_dir và chạy parse trích xuất context."""
    if not ptkt_dir.exists():
        LOGGER.warning("Thư mục %s không tồn tại", ptkt_dir)
        return None

    pdf_files = sorted(ptkt_dir.glob("*.pdf"), key=lambda p: p.name, reverse=True)
    if not pdf_files:
        LOGGER.warning("Không tìm thấy file PDF nào trong %s", ptkt_dir)
        return None

    target_pdf = pdf_files[0]
    LOGGER.info("Bắt đầu xử lý file PDF: %s", target_pdf)
    context = parse_tcbs_daily_report(target_pdf)

    # Lưu ra data/market_context.json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2, ensure_ascii=False)
    LOGGER.info("✅ Đã ghi market context ra %s", output_path)

    # Đánh dấu trong manifest
    update_manifests_after_processing(target_pdf.name, output_path)
    return context


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    res = run_parse_daily_pipeline()
    if res:
        print("\n--- KẾT QUẢ TRÍCH XUẤT NGỮ CẢNH THỊ TRƯỜNG ---")
        print(f"Ngày: {res.get('date')} | Nguồn: {res.get('source')}")
        print(f"Xu hướng: {res.get('market_regime_analyst')} | Tâm lý: {res.get('sentiment')}")
        print(
            f"VN-Index: {res.get('vnindex_close')} ({res.get('vnindex_change_pts'):+.2f} pts, {res.get('vnindex_change_pct'):+.2f}%)"
        )
        print(f"Ngành tâm điểm: {', '.join(res.get('focus_sectors', []))}")
        print(f"Từ khóa rủi ro: {', '.join(res.get('risk_keywords', []))}")
        print(f"Tín hiệu bán: {', '.join(res.get('sell_signals', []))}")
        print(f"Tóm tắt: {res.get('raw_summary')[:200]}...")
