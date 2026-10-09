# -*- coding: utf-8 -*-
"""Unit tests for TASK-0084: AI Analyst Veto-Only Governance (Phase 28 - v15.0)."""

from ai_analyst import (
    AI_ACTION_PASS,
    AI_ACTION_REDUCE_SIZING,
    AI_ACTION_VETO,
    STATE_ATTRACTIVE,
    STATE_AVOID,
    STATE_INSUFFICIENT_DATA,
    STATE_RISK_ELEVATED,
    STATE_STRONG_OPPORTUNITY,
    STATE_WAIT_BETTER_ENTRY,
    STATE_WATCHLIST,
    arbitrate_pm_decision,
    resolve_ai_veto_action,
)


def test_resolve_ai_veto_action_when_can_buy_false():
    """AC-01: When Quant Gate can_buy is False, AI action is VETO with 0.0 sizing."""
    action, factor = resolve_ai_veto_action(
        final_decision=STATE_STRONG_OPPORTUNITY,
        is_overridden=True,
        can_buy=False,
    )
    assert action == AI_ACTION_VETO
    assert factor == 0.0


def test_resolve_ai_veto_action_pass():
    """AC-02: When can_buy is True and decision is STRONG_OPPORTUNITY, action is PASS with 1.0 sizing."""
    action, factor = resolve_ai_veto_action(
        final_decision=STATE_STRONG_OPPORTUNITY,
        is_overridden=False,
        can_buy=True,
    )
    assert action == AI_ACTION_PASS
    assert factor == 1.0

    action_att, factor_att = resolve_ai_veto_action(
        final_decision=STATE_ATTRACTIVE,
        is_overridden=False,
        can_buy=True,
    )
    assert action_att == AI_ACTION_PASS
    assert factor_att == 1.0


def test_resolve_ai_veto_action_reduce_sizing():
    """AC-03: When moderate risk is detected (WAIT_BETTER_ENTRY or RISK_ELEVATED),

    action is REDUCE_SIZING with 0.5 sizing.
    """
    action_wait, factor_wait = resolve_ai_veto_action(
        final_decision=STATE_WAIT_BETTER_ENTRY,
        is_overridden=False,
        can_buy=True,
    )
    assert action_wait == AI_ACTION_REDUCE_SIZING
    assert factor_wait == 0.5

    action_risk, factor_risk = resolve_ai_veto_action(
        final_decision=STATE_RISK_ELEVATED,
        is_overridden=False,
        can_buy=True,
    )
    assert action_risk == AI_ACTION_REDUCE_SIZING
    assert factor_risk == 0.5


def test_resolve_ai_veto_action_avoid_or_insufficient_data():
    """When decision is AVOID or INSUFFICIENT_DATA, action is VETO with 0.0 sizing."""
    action_avoid, factor_avoid = resolve_ai_veto_action(
        final_decision=STATE_AVOID,
        is_overridden=False,
        can_buy=True,
    )
    assert action_avoid == AI_ACTION_VETO
    assert factor_avoid == 0.0

    action_insuf, factor_insuf = resolve_ai_veto_action(
        final_decision=STATE_INSUFFICIENT_DATA,
        is_overridden=True,
        can_buy=True,
    )
    assert action_insuf == AI_ACTION_VETO
    assert factor_insuf == 0.0


def test_arbitrate_pm_decision_veto_only_blocks_buy_promotion():
    """AC-01: arbitrate_pm_decision overrides BUY proposal down to WATCHLIST when can_buy is False."""
    final, overridden, reason = arbitrate_pm_decision(
        raw_decision=STATE_STRONG_OPPORTUNITY,
        can_buy=False,
    )
    assert final == STATE_WATCHLIST
    assert overridden is True
    assert "Veto-Only" in reason
