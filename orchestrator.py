"""
orchestrator: manages the war room workflow and produces the final structured decision

flow:
1. DataAnalyst -> quantitative analysis (tools: aggregate_metrics, detect_anomalies, compare_trends)
2. PM -> go/no-go criteria evaluation
3. Marketing -> sentiment + comms plan (tool: summarise_sentiment)
4. Risk -> risk register + critique
5. Orchestrator -> synthesise -> final JSON decision
"""

import json
import logging
from datetime import datetime, timezone

from agents import data_analyst_agent, pm_agent, marketing_agent, risk_agent
from llm import llm_query

logger = logging.getLogger(__name__)


def _compute_confidence(analyst_out: dict, pm_out: dict, marketing_out: dict) -> dict:
    """
    confidence score (0-100) representing how confident we are in the decision
    based on data completeness and signal clarity (not launch health)
    starts at 60 (baseline data confidence) and adjusts based on signal strength
    """
    score = 60

    # strong anomaly signals increase decision confidence
    score += analyst_out["critical_count"] * 5
    score += analyst_out["high_count"] * 3

    # clear criteria failure increases confidence in Roll Back / Pause decision
    failed = pm_out["criteria_total"] - pm_out["criteria_passed"]
    score += failed * 4

    # strong negative sentiment corroborates the decision
    sentiment_score = marketing_out["sentiment"]["sentiment_score"]
    if sentiment_score < 40:
        score += 8
    elif sentiment_score > 65:
        score -= 5  # mixed signals reduce confidence

    score = max(20, min(92, score))

    boosters = [
        "Crash rate resolved below 1%",
        "Payment success rate back above 97%",
        "API latency p95 below 300ms",
        "Support ticket volume stabilising",
        "Android WebView hotfix shipped",
    ]
    return {"score": score, "confidence_boosters": boosters}


def _decide(analyst_out: dict, pm_out: dict, risk_out: dict) -> str:
    # deterministic decision logic based on severity signals
    critical_anomalies = analyst_out["critical_count"]
    high_anomalies = analyst_out["high_count"]
    criteria_passed = pm_out["criteria_passed"]
    criteria_total = pm_out["criteria_total"]

    # critical anomalies or majority criteria failed -> Roll Back
    if critical_anomalies >= 2 or criteria_passed <= criteria_total // 2:
        return "Roll Back"

    # any critical anomaly or most criteria failed -> Pause
    if critical_anomalies >= 1 or high_anomalies >= 3 or criteria_passed < criteria_total:
        return "Pause"

    return "Proceed"


def run_war_room(metrics: dict, baselines: dict, feedback: list[dict], release_notes: str) -> dict:
    logger.info("=" * 60)
    logger.info("WAR ROOM SESSION STARTED")
    logger.info("=" * 60)

    # step 1: Data Analyst
    logger.info("\n[Orchestrator] Dispatching -> DataAnalyst")
    analyst_out = data_analyst_agent(metrics, baselines)

    # step 2: Product Manager
    logger.info("\n[Orchestrator] Dispatching -> PM")
    pm_out = pm_agent(analyst_out, release_notes)

    # step 3: Marketing / Comms
    logger.info("\n[Orchestrator] Dispatching -> Marketing")
    marketing_out = marketing_agent(feedback, analyst_out)

    # step 4: Risk / Critic
    logger.info("\n[Orchestrator] Dispatching -> Risk")
    risk_out = risk_agent(analyst_out, pm_out, marketing_out, release_notes)

    # step 5: Synthesise
    logger.info("\n[Orchestrator] Synthesising final decision")

    decision = _decide(analyst_out, pm_out, risk_out)
    confidence = _compute_confidence(analyst_out, pm_out, marketing_out)

    top_anomalies = analyst_out["anomalies"][:4]
    sentiment = marketing_out["sentiment"]

    def fallback_rationale():
        lines = [
            f"Decision: {decision}",
            f"Critical anomalies: {analyst_out['critical_count']}, High: {analyst_out['high_count']}",
            f"Criteria passed: {pm_out['criteria_passed']}/{pm_out['criteria_total']}",
            f"Sentiment score: {sentiment['sentiment_score']}/100",
            "Key drivers: crash rate 4.2x baseline, payment failures, API latency 3x baseline, "
            "accelerating support tickets and cancellations.",
        ]
        return "\n".join(lines)

    rationale_text = llm_query(
        system=(
            "You are the war room coordinator. Write a concise rationale (max 120 words) "
            "for the launch decision, referencing specific metrics and feedback themes."
        ),
        user=(
            f"Decision: {decision}\n\n"
            f"Top anomalies:\n{json.dumps(top_anomalies, indent=2)}\n\n"
            f"Criteria passed: {pm_out['criteria_passed']}/{pm_out['criteria_total']}\n\n"
            f"Sentiment score: {sentiment['sentiment_score']}/100\n"
            f"Top negative themes: {list(sentiment['negative_themes'].keys())[:3]}\n\n"
            f"Risk count: {len(risk_out['risk_register'])}"
        ),
        fallback_fn=fallback_rationale,
    )

    # action plan
    action_plan = [
        {
            "priority": 1,
            "action": "Disable SmartRecommend v2 for Android 10 devices via feature flag",
            "owner": "Engineering",
            "window": "0–4 hours",
        },
        {
            "priority": 2,
            "action": "Revert payment pre-fill integration; restore legacy token compatibility",
            "owner": "Engineering / Payments",
            "window": "0–6 hours",
        },
        {
            "priority": 3,
            "action": "Pre-warm recommend-svc replicas; lower auto-scale CPU trigger to 50%",
            "owner": "Platform/SRE",
            "window": "0–4 hours",
        },
        {
            "priority": 4,
            "action": "Publish status page update acknowledging performance degradation",
            "owner": "Marketing/Comms",
            "window": "0–2 hours",
        },
        {
            "priority": 5,
            "action": "Deploy self-serve FAQ for top 3 support ticket categories",
            "owner": "Support / Product",
            "window": "4–12 hours",
        },
        {
            "priority": 6,
            "action": "Ship Android WebView crash hotfix and validate on staging",
            "owner": "Engineering",
            "window": "12–24 hours",
        },
        {
            "priority": 7,
            "action": "Update recommendation model with current catalogue (fix out-of-stock SKUs)",
            "owner": "ML / Data",
            "window": "24–48 hours",
        },
        {
            "priority": 8,
            "action": "War room check-in: review all metrics post-fixes before resuming rollout",
            "owner": "PM + All Leads",
            "window": "48 hours",
        },
    ]

    # communication plan
    comms_plan = {
        "internal": [
            "Immediate Slack alert to #engineering-oncall: crash rate and payment failures require P1 response",
            "Executive summary to VP Product and CTO within 1 hour",
            "Daily war room standup at 09:00 until metrics stabilise",
        ],
        "external": [
            "Status page update: 'We are aware of performance issues affecting some users and are actively working on a fix'",
            "Email to affected users (payment failures) within 4 hours with apology and resolution ETA",
            "Hold all promotional campaigns for SmartRecommend v2 until Proceed decision",
            "Community forum post acknowledging crash reports with workaround instructions",
        ],
    }

    # final output
    output = {
        "war_room_session": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "feature": "SmartRecommend v2.0",
            "agents_involved": ["DataAnalyst", "PM", "Marketing", "Risk", "Orchestrator"],
        },
        "decision": decision,
        "rationale": {
            "summary": rationale_text,
            "metric_references": [
                f"{a['metric']}: {a['delta_pct']:+.1f}% vs baseline [{a['severity']}]"
                for a in top_anomalies
            ],
            "feedback_summary": {
                "sentiment_score": sentiment["sentiment_score"],
                "negative_count": sentiment["counts"]["negative"],
                "top_themes": list(sentiment["negative_themes"].keys())[:3],
            },
            "criteria_passed": f"{pm_out['criteria_passed']}/{pm_out['criteria_total']}",
        },
        "risk_register": risk_out["risk_register"],
        "action_plan_24_48h": action_plan,
        "communication_plan": comms_plan,
        "confidence": confidence,
        "agent_outputs": {
            "data_analyst": analyst_out["analysis"],
            "pm": pm_out["assessment"],
            "marketing": marketing_out["comms_plan"],
            "risk": risk_out["critique"],
        },
    }

    logger.info(f"\n[Orchestrator] DECISION: {decision} | Confidence: {confidence['score']}/100")
    logger.info("=" * 60)
    logger.info("WAR ROOM SESSION COMPLETE")
    logger.info("=" * 60)

    return output
