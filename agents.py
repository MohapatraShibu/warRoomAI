"""
war room agents - each agent has a clear responsibility boundary
agents call tools explicitly and use the LLM to reason over tool outputs
"""

import json
import logging
from tools import aggregate_metrics, detect_anomalies, summarise_sentiment, compare_trends
from llm import llm_query

logger = logging.getLogger(__name__)

# shared helper

def _log_tool_call(agent: str, tool: str, result_summary: str):
    logger.info(f"[{agent}] TOOL CALL -> {tool} | {result_summary}")

# agent 1: Data Analyst

def data_analyst_agent(metrics: dict, baselines: dict) -> dict:
    logger.info("[DataAnalyst] Starting analysis")

    # tool calls
    agg = aggregate_metrics(metrics, baselines)
    _log_tool_call("DataAnalyst", "aggregate_metrics",
                   f"{len(agg)} metrics aggregated")

    anomalies = detect_anomalies(metrics, baselines)
    _log_tool_call("DataAnalyst", "detect_anomalies",
                   f"{len(anomalies)} anomalies detected: {[a['metric'] for a in anomalies]}")

    trends = compare_trends(metrics)
    _log_tool_call("DataAnalyst", "compare_trends",
                   f"worsening metrics: {[k for k,v in trends.items() if v['direction']=='worsening']}")

    critical = [a for a in anomalies if a["severity"] == "critical"]
    high = [a for a in anomalies if a["severity"] == "high"]

    def fallback():
        lines = ["Rule-based metric analysis:"]
        for a in anomalies:
            lines.append(f"  - {a['metric']}: {a['delta_pct']:+.1f}% vs baseline [{a['severity']}]")
        worsening = [k for k, v in trends.items() if v["direction"] == "worsening" and v["momentum"] == "accelerating"]
        if worsening:
            lines.append(f"Accelerating degradation in: {', '.join(worsening)}")
        lines.append(f"Critical anomalies: {len(critical)}, High: {len(high)}")
        return "\n".join(lines)

    analysis = llm_query(
        system=(
            "You are a senior data analyst in a product war room. "
            "Analyse the provided metric aggregations, anomalies, and trends. "
            "Be concise. Highlight the most critical signals. Max 150 words."
        ),
        user=(
            f"Aggregated metrics:\n{json.dumps(agg, indent=2)}\n\n"
            f"Anomalies:\n{json.dumps(anomalies, indent=2)}\n\n"
            f"Trends:\n{json.dumps(trends, indent=2)}"
        ),
        fallback_fn=fallback,
    )

    logger.info(f"[DataAnalyst] Analysis complete")
    return {
        "agent": "DataAnalyst",
        "aggregated_metrics": agg,
        "anomalies": anomalies,
        "trends": trends,
        "analysis": analysis,
        "critical_count": len(critical),
        "high_count": len(high),
    }

# agent 2: Product Manager

def pm_agent(analyst_output: dict, release_notes: str) -> dict:
    logger.info("[PM] Evaluating go/no-go criteria")

    anomalies = analyst_output["anomalies"]
    critical = [a for a in anomalies if a["severity"] == "critical"]
    high = [a for a in anomalies if a["severity"] == "high"]

    # rule-based success criteria evaluation
    criteria = {
        "crash_rate_below_1pct": next(
            (a["latest"] < 1.0 for a in [{"latest": analyst_output["aggregated_metrics"].get("crash_rate_pct", {}).get("latest", 99)}]), False
        ),
        "payment_success_above_97pct": analyst_output["aggregated_metrics"].get("payment_success_rate_pct", {}).get("latest", 0) >= 97.0,
        "no_critical_anomalies": len(critical) == 0,
        "support_tickets_stable": analyst_output["trends"].get("support_ticket_volume", {}).get("direction") != "worsening",
    }

    passed = sum(criteria.values())
    total_criteria = len(criteria)

    def fallback():
        status = "FAIL" if passed < total_criteria - 1 else "MARGINAL"
        lines = [f"Go/No-Go Assessment: {status}"]
        for k, v in criteria.items():
            lines.append(f"  {'✓' if v else '✗'} {k}")
        lines.append(f"Critical issues: {len(critical)}, High issues: {len(high)}")
        lines.append("Recommendation: Pause rollout pending crash rate and payment fixes.")
        return "\n".join(lines)

    assessment = llm_query(
        system=(
            "You are a Product Manager in a war room. Evaluate go/no-go criteria against "
            "the analyst findings and release notes. State clearly whether success criteria "
            "are met. Max 150 words."
        ),
        user=(
            f"Success criteria evaluation:\n{json.dumps(criteria, indent=2)}\n\n"
            f"Analyst findings:\n{analyst_output['analysis']}\n\n"
            f"Release notes:\n{release_notes}"
        ),
        fallback_fn=fallback,
    )

    logger.info(f"[PM] Criteria passed: {passed}/{total_criteria}")
    return {
        "agent": "PM",
        "success_criteria": criteria,
        "criteria_passed": passed,
        "criteria_total": total_criteria,
        "assessment": assessment,
    }

# agent 3: Marketing / Comms

def marketing_agent(feedback_data: list[dict], analyst_output: dict) -> dict:
    logger.info("[Marketing] Analysing user sentiment and comms posture")

    # tool call
    sentiment = summarise_sentiment(feedback_data)
    _log_tool_call("Marketing", "summarise_sentiment",
                   f"score={sentiment['sentiment_score']}, "
                   f"neg={sentiment['counts']['negative']}, "
                   f"pos={sentiment['counts']['positive']}, "
                   f"top_theme={list(sentiment['negative_themes'].keys())[:1]}")

    def fallback():
        themes = sentiment["negative_themes"]
        top = list(themes.items())[:3]
        lines = [
            f"Sentiment score: {sentiment['sentiment_score']}/100 (negative-leaning)",
            f"Negative: {sentiment['counts']['negative']}, Positive: {sentiment['counts']['positive']}, Neutral: {sentiment['counts']['neutral']}",
            "Top negative themes: " + ", ".join(f"{t} ({c})" for t, c in top),
            "Comms posture: Proactive acknowledgement required. Do NOT promote feature externally.",
            "Internal: Escalate to engineering immediately. External: Status page update + email to affected users.",
        ]
        return "\n".join(lines)

    comms_plan = llm_query(
        system=(
            "You are a Marketing/Comms lead in a product war room. Based on user sentiment "
            "and metric signals, recommend internal and external communication actions. "
            "Be specific and concise. Max 150 words."
        ),
        user=(
            f"Sentiment analysis:\n{json.dumps(sentiment, indent=2)}\n\n"
            f"Key metric anomalies:\n{json.dumps(analyst_output['anomalies'][:5], indent=2)}"
        ),
        fallback_fn=fallback,
    )

    logger.info("[Marketing] Comms plan ready")
    return {
        "agent": "Marketing",
        "sentiment": sentiment,
        "comms_plan": comms_plan,
    }

# agent 4: Risk / Critic

def risk_agent(analyst_output: dict, pm_output: dict, marketing_output: dict, release_notes: str) -> dict:
    logger.info("[Risk] Challenging assumptions and building risk register")

    anomalies = analyst_output["anomalies"]
    trends = analyst_output["trends"]

    # build risk register from known issues + anomalies
    risk_register = []

    crash_metric = analyst_output["aggregated_metrics"].get("crash_rate_pct", {})
    if crash_metric.get("latest", 0) > 1.0:
        risk_register.append({
            "risk": "Crash rate 4.2x above baseline (Android WebView known issue)",
            "likelihood": "High",
            "impact": "High",
            "mitigation": "Hotfix for Android WebView crash; feature-flag disable for affected devices",
        })

    payment_metric = analyst_output["aggregated_metrics"].get("payment_success_rate_pct", {})
    if payment_metric.get("latest", 100) < 97.0:
        risk_register.append({
            "risk": "Payment success rate declining — revenue leakage risk",
            "likelihood": "High",
            "impact": "Critical",
            "mitigation": "Revert payment pre-fill integration; patch legacy token handling",
        })

    latency_metric = analyst_output["aggregated_metrics"].get("api_latency_p95_ms", {})
    if latency_metric.get("delta_pct", 0) > 50:
        risk_register.append({
            "risk": "API latency p95 at 640ms (3x baseline) — auto-scaling lag unresolved",
            "likelihood": "High",
            "impact": "High",
            "mitigation": "Pre-warm recommend-svc replicas; lower auto-scale trigger to 50% CPU",
        })

    ticket_trend = trends.get("support_ticket_volume", {})
    if ticket_trend.get("direction") == "worsening" and ticket_trend.get("momentum") == "accelerating":
        risk_register.append({
            "risk": "Support ticket volume accelerating — team capacity risk",
            "likelihood": "High",
            "impact": "Medium",
            "mitigation": "Deploy FAQ/self-serve for top issues; add temporary support capacity",
        })

    churn_metric = analyst_output["aggregated_metrics"].get("daily_cancellations", {})
    if churn_metric.get("delta_pct", 0) > 50:
        risk_register.append({
            "risk": "Daily cancellations 3.5x baseline — retention crisis if unaddressed",
            "likelihood": "Medium",
            "impact": "High",
            "mitigation": "Pause full rollout; offer affected users service credit",
        })

    def fallback():
        lines = ["Risk assessment: ROLL BACK or PAUSE strongly recommended."]
        lines.append(f"{len(risk_register)} risks identified:")
        for r in risk_register:
            lines.append(f"  [{r['likelihood']}/{r['impact']}] {r['risk']}")
        lines.append("Key assumption challenged: 'Canary looked fine' — canary was only 10% traffic; issues emerged at scale.")
        return "\n".join(lines)

    critique = llm_query(
        system=(
            "You are a Risk/Critic agent in a war room. Challenge assumptions, identify gaps "
            "in the analysis, and stress-test the proposed decision. Be direct. Max 150 words."
        ),
        user=(
            f"Risk register:\n{json.dumps(risk_register, indent=2)}\n\n"
            f"PM assessment:\n{pm_output['assessment']}\n\n"
            f"Criteria passed: {pm_output['criteria_passed']}/{pm_output['criteria_total']}\n\n"
            f"Sentiment score: {marketing_output['sentiment']['sentiment_score']}/100\n\n"
            f"Release notes known issues:\n{release_notes}"
        ),
        fallback_fn=fallback,
    )

    logger.info(f"[Risk] Risk register built: {len(risk_register)} risks")
    return {
        "agent": "Risk",
        "risk_register": risk_register,
        "critique": critique,
    }
