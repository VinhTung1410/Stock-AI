"""Dispatcher module for Stock-AI (v6.1 Institutional Decoupling).

Separates the presentation and alerting layer from the analytical core engine.
Handles formatting and dispatching of SignalEvents, Decision batches, and
Evidence-based Kill Switch alerts to Discord and other notification channels.
"""

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from discord_alerts import send_discord_dm, send_discord_webhook, send_trade_signal_alert

LOGGER = logging.getLogger(__name__)

# Constants to satisfy SonarCloud S1192
ACTION_BUY = "MUA"
ACTION_WATCH = "THEO DÕI"
ACTION_REJECT = "TỪ CHỐI"
SOURCE_DISPATCHER = "Stock-AI Dispatcher"


@dataclass
class SignalEvent:
    """Represents an immutable trade decision event produced by the analysis engine."""

    symbol: str
    action: str  # BUY / MUA, WATCH, REJECT, SELL, HOLD
    current_price: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    trigger_reason: str = ""
    conviction_score: float = 0.0
    mos_pct: float = 0.0
    f_score: int = 0
    decision_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    analyst_context_used: bool = False
    regime_conflict: bool = False
    context_source_file: Optional[str] = None
    context_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert SignalEvent to standard dictionary."""
        return asdict(self)


def dispatch_signal_event(event: SignalEvent) -> bool:
    """Dispatch a single SignalEvent to Discord DM/Webhook if action is BUY.

    Args:
        event: SignalEvent to be sent.

    Returns:
        True if successfully dispatched or skipped, False if dispatch failed.
    """
    if not event or not event.symbol:
        LOGGER.warning("Empty SignalEvent passed to dispatcher; skipped.")
        return False

    action_norm = str(event.action).upper()
    if "MUA" not in action_norm and "BUY" not in action_norm:
        LOGGER.debug("SignalEvent action '%s' is not BUY; skipping Discord alert.", event.action)
        return True

    try:
        reason_txt = event.trigger_reason or (
            f"[{SOURCE_DISPATCHER}] Conviction: {event.conviction_score:.1f} | "
            f"MoS: {event.mos_pct:+.1f}% | F-Score: {event.f_score}/9"
        )
        quant_metrics = {
            "mos_pct": event.mos_pct,
            "f_score": event.f_score,
        }
        success = send_trade_signal_alert(
            symbol=event.symbol,
            action=ACTION_BUY,
            current_price=event.current_price,
            trigger_reason=reason_txt,
            target_price=event.target_price,
            stop_loss=event.stop_loss,
            conviction_score=event.conviction_score,
            quant_metrics=quant_metrics,
        )
        if success:
            LOGGER.info("Successfully dispatched SignalEvent for %s to Discord.", event.symbol)
        else:
            LOGGER.warning("Failed to dispatch SignalEvent for %s to Discord.", event.symbol)
        return bool(success)
    except Exception:
        LOGGER.exception("Exception occurred while dispatching SignalEvent for %s", event.symbol)
        return False


def dispatch_decision_batch(decisions: List[Dict[str, Any]], session: str = "NOON") -> bool:
    """Dispatch a summary of BUY, WATCH, REJECT decisions to Discord webhook.

    Args:
        decisions: List of decision record dictionaries.
        session: Session label ('ATO', 'NOON', 'ATC').

    Returns:
        True if dispatched or empty, False on error.
    """
    if not decisions:
        LOGGER.info("No decisions to dispatch in batch for session %s.", session)
        return True

    try:
        buy_list = [d["symbol"] for d in decisions if d.get("decision") == "BUY"]
        watch_list = [d["symbol"] for d in decisions if d.get("decision") == "WATCH"]
        reject_list = [d["symbol"] for d in decisions if d.get("decision") == "REJECT"]

        desc = (
            f"**Phiên:** {session} | **Tổng số mã phân tích:** {len(decisions)}\n"
            f"🟢 **BUY ({len(buy_list)}):** {', '.join(buy_list) if buy_list else 'Không có'}\n"
            f"🟡 **WATCH ({len(watch_list)}):** {', '.join(watch_list) if watch_list else 'Không có'}\n"
            f"🔴 **REJECT ({len(reject_list)}):** {', '.join(reject_list) if reject_list else 'Không có'}"
        )

        embed = {
            "title": f"📋 NHẬT KÝ QUYẾT ĐỊNH UNIVERSE - PHIÊN {session}",
            "description": desc,
            "color": 0x3498DB,
            "footer": {"text": f"{SOURCE_DISPATCHER} • v6.1 Evidence Engine"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        send_discord_webhook(embeds=[embed])
        send_discord_dm(embeds=[embed])
        LOGGER.info("Dispatched decision batch summary for %d symbols.", len(decisions))
        return True
    except Exception:
        LOGGER.exception("Error dispatching decision batch summary")
        return False


def dispatch_kill_switch_alert(kill_switch_data: Dict[str, Any]) -> bool:
    """Dispatch an emergency alert when the Evidence-Based Kill Switch triggers.

    Args:
        kill_switch_data: Output dictionary from check_evidence_kill_switch().

    Returns:
        True if successfully sent, False otherwise.
    """
    if not kill_switch_data or not kill_switch_data.get("is_triggered"):
        return True

    try:
        expectancy = kill_switch_data.get("expectancy_r", 0.0)
        reduction = kill_switch_data.get("size_reduction_pct", 50.0)
        reason = kill_switch_data.get("reason", "Expectancy R < 0")

        embed = {
            "title": "🚨 EVIDENCE-BASED KILL SWITCH ĐÃ KÍCH HOẠT",
            "description": (
                f"**Cảnh báo Rủi ro Danh mục:**\n"
                f"- **Lý do:** {reason}\n"
                f"- **Expectancy R (20 lệnh gần nhất):** `{expectancy:+.2f}R`\n"
                f"- **Hành động:** Tự động cắt giảm **{reduction:.0f}%** quy mô vị thế mở mới!\n"
                f"- **Khuyến nghị:** Rà soát lại điều kiện thị trường hoặc chuyển về Cash Mode."
            ),
            "color": 0xE74C3C,
            "footer": {"text": f"{SOURCE_DISPATCHER} • Risk Defense Gate"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        send_discord_webhook(embeds=[embed])
        send_discord_dm(embeds=[embed])
        LOGGER.warning("Dispatched Evidence Kill Switch alert to Discord!")
        return True
    except Exception:
        LOGGER.exception("Error dispatching Kill Switch alert")
        return False
