import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_engine import _fetch_history_with_fallback

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CACHE_FILE = "data/history_ohlcv_55.json"

SYMBOLS = [
    'ACB', 'ANV', 'BID', 'CSV', 'CTG', 'DCM', 'DGC', 'DIG', 'DPM', 'DXG',
    'FMC', 'FPT', 'GAS', 'GIL', 'GMD', 'GVR', 'HAH', 'HDB', 'HPG', 'HSG',
    'IDC', 'KBC', 'KDH', 'MBB', 'MSH', 'MSN', 'MWG', 'NKG', 'NLG', 'NVL',
    'PDR', 'PLX', 'POW', 'PVD', 'PVT', 'SAB', 'SHB', 'SSB', 'SSI', 'STB',
    'STK', 'SZC', 'TCB', 'TNG', 'TPB', 'VGC', 'VHC', 'VHM', 'VIB', 'VIC',
    'VND', 'VNM', 'VPB', 'VRE', 'VTP'
]

def build_cache():
    history_data = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                history_data = json.load(f)
            logging.info("Loaded %d existing symbols from %s", len(history_data), CACHE_FILE)
        except Exception:
            history_data = {}

    to_fetch = [s for s in SYMBOLS if s not in history_data or len(history_data[s]) < 20]
    logging.info("Need to fetch history for %d symbols...", len(to_fetch))

    for idx, sym in enumerate(to_fetch):
        logging.info("[%d/%d] Fetching %s...", idx + 1, len(to_fetch), sym)
        try:
            df = _fetch_history_with_fallback(sym, start_date="2026-08-01", end_date="2026-10-23")
            if df is not None and not df.empty and "time" in df.columns and "close" in df.columns:
                df["date_str"] = df["time"].astype(str).str[:10]
                records = []
                for _, r in df.sort_values("date_str").drop_duplicates(subset=["date_str"]).iterrows():
                    c = float(r.get("close", 0.0))
                    v = float(r.get("volume", 0.0))
                    records.append({
                        "date": str(r["date_str"]),
                        "open": float(r.get("open", c)),
                        "high": float(r.get("high", c)),
                        "low": float(r.get("low", c)),
                        "close": c,
                        "volume": v,
                        "val_bil": round((v * c) / 1e6, 4)
                    })
                history_data[sym] = records
                logging.info("  -> Saved %d bars for %s", len(records), sym)
            else:
                logging.warning("  -> Empty history for %s", sym)
        except Exception as e:
            logging.exception("  -> Error fetching %s: %s", sym, e)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    logging.info("Saved cache to %s (%d symbols)", CACHE_FILE, len(history_data))

if __name__ == "__main__":
    build_cache()
