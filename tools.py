# tools invoked programmatically by agents
# each tool is a plain function that accepts data and returns a structured dict

import statistics
from typing import Any

# tool 1: Metric Aggregation

def aggregate_metrics(metrics: dict, baselines: dict) -> dict:

    # compute latest value, mean, delta-from-baseline, and trend direction for every metric series

    results = {}
    for name, series in metrics.items():
        values = [p["value"] for p in series]
        latest = values[-1]
        mean = round(statistics.mean(values), 3)
        baseline = baselines.get(name)
        delta_pct = round((latest - baseline) / baseline * 100, 2) if baseline else None

        # trend: compare last-3 avg vs first-3 avg
        trend_dir = "stable"
        if len(values) >= 6:
            early = statistics.mean(values[:3])
            recent = statistics.mean(values[-3:])
            if recent > early * 1.03:
                trend_dir = "increasing"
            elif recent < early * 0.97:
                trend_dir = "decreasing"

        results[name] = {
            "latest": latest,
            "mean": mean,
            "baseline": baseline,
            "delta_pct": delta_pct,
            "trend": trend_dir,
        }
    return results

# tool 2: Anomaly Detection

def detect_anomalies(metrics: dict, baselines: dict, threshold_pct: float = 15.0) -> list[dict]:

    # flag metrics whose latest value deviates from baseline by more than threshold_pct
    # also flags metrics with accelerating degradation (last delta > 2x previous delta)

    anomalies = []

    # higher = worse for these metrics
    higher_is_worse = {"crash_rate_pct", "api_latency_p95_ms", "support_ticket_volume", "daily_cancellations"}

    for name, series in metrics.items():
        values = [p["value"] for p in series]
        baseline = baselines.get(name)
        if baseline is None:
            continue

        latest = values[-1]
        delta_pct = (latest - baseline) / baseline * 100

        is_bad = (
            (name in higher_is_worse and delta_pct > threshold_pct) or
            (name not in higher_is_worse and delta_pct < -threshold_pct)
        )

        severity = "low"
        abs_delta = abs(delta_pct)
        if abs_delta >= 40:
            severity = "critical"
        elif abs_delta >= 25:
            severity = "high"
        elif abs_delta >= threshold_pct:
            severity = "medium"

        if is_bad:
            anomalies.append({
                "metric": name,
                "baseline": baseline,
                "latest": latest,
                "delta_pct": round(delta_pct, 2),
                "severity": severity,
            })

    anomalies.sort(key=lambda x: abs(x["delta_pct"]), reverse=True)
    return anomalies

# tool 3: Sentiment Summary

def summarise_sentiment(feedback: list[dict]) -> dict:

    # Count sentiment labels, extract top repeated themes from negative feedback
    # and compute a sentiment score (0-100, higher = more positive)

    counts = {"positive": 0, "neutral": 0, "negative": 0}
    negative_texts = []

    for entry in feedback:
        label = entry.get("sentiment", "neutral")
        counts[label] = counts.get(label, 0) + 1
        if label == "negative":
            negative_texts.append(entry["text"].lower())

    total = sum(counts.values())
    score = round((counts["positive"] * 100 + counts["neutral"] * 50) / total, 1) if total else 50

    # simple keyword theme extraction from negative feedback
    theme_keywords = {
        "crash / stability": ["crash", "crashing", "crashed", "freeze", "froze"],
        "performance / latency": ["slow", "latency", "loading", "takes forever", "seconds"],
        "payment failures": ["payment", "charged", "declined", "failed", "order"],
        "poor recommendations": ["random", "irrelevant", "already bought", "out of stock", "off"],
        "support overload": ["support", "no reply", "no response", "queue", "automated"],
        "churn signal": ["cancelled", "uninstalled", "going back", "reinstall"],
    }

    themes = {}
    for theme, keywords in theme_keywords.items():
        count = sum(1 for t in negative_texts if any(k in t for k in keywords))
        if count > 0:
            themes[theme] = count

    themes = dict(sorted(themes.items(), key=lambda x: x[1], reverse=True))

    return {
        "counts": counts,
        "total": total,
        "sentiment_score": score,
        "negative_themes": themes,
    }

# tool 4: Trend Comparison

def compare_trends(metrics: dict, window: int = 3) -> dict:

    # for each metric, compute the rate of change over the last 'window' days
    # and classify momentum as accelerating, steady, or decelerating degradation

    results = {}
    for name, series in metrics.items():
        values = [p["value"] for p in series]
        if len(values) < window + 1:
            continue

        recent_deltas = [values[i] - values[i - 1] for i in range(-window, 0)]
        avg_delta = statistics.mean(recent_deltas)
        momentum = "stable"

        if len(recent_deltas) >= 2:
            if abs(recent_deltas[-1]) > abs(recent_deltas[0]) * 1.2:
                momentum = "accelerating"
            elif abs(recent_deltas[-1]) < abs(recent_deltas[0]) * 0.8:
                momentum = "decelerating"
            else:
                momentum = "steady"

        results[name] = {
            "avg_daily_delta": round(avg_delta, 4),
            "momentum": momentum,
            "direction": "worsening" if (
                (name in {"crash_rate_pct", "api_latency_p95_ms", "support_ticket_volume", "daily_cancellations"} and avg_delta > 0) or
                (name not in {"crash_rate_pct", "api_latency_p95_ms", "support_ticket_volume", "daily_cancellations"} and avg_delta < 0)
            ) else "improving",
        }
    return results
