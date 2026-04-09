# War Room AI

A multi-agent system that simulates a cross-functional war room during a product launch. Agents analyse a mock dashboard (metrics + user feedback) and produce a structured launch decision: **Proceed / Pause / Roll Back**.

## Architecture

```
main.py
  └── orchestrator.py <- coordinates agents, makes final decision
        ├── data_analyst_agent <- tools: aggregate_metrics, detect_anomalies, compare_trends
        ├── pm_agent <- evaluates go/no-go success criteria
        ├── marketing_agent <- tool: summarise_sentiment, builds comms plan
        └── risk_agent <- builds risk register, challenges assumptions
```

### Agent Responsibilities

| Agent | Responsibility |
|---|---|
| **DataAnalyst** | quantitative analysis - aggregates metrics, detects anomalies, compares trends |
| **PM** | defines and evaluates go/no-go success criteria against analyst findings |
| **Marketing** | sentiment analysis of user feedback, internal/external comms plan |
| **Risk/Critic** | challenges assumptions, builds risk register with mitigations |
| **Orchestrator** | coordinates workflow, synthesises all outputs, produces final JSON decision |

### Tools (called programmatically by agents)

| Tool | Called By | Purpose |
|---|---|---|
| `aggregate_metrics` | DataAnalyst | latest value, mean, delta-from-baseline, trend direction per metric |
| `detect_anomalies` | DataAnalyst | flags metrics deviating >15% from baseline with severity rating |
| `compare_trends` | DataAnalyst | rate of change + momentum (accelerating/steady/decelerating) |
| `summarise_sentiment` | Marketing | sentiment counts, score, and top negative themes from feedback |

## LLM Backend

The system uses **[Ollama](https://ollama.com)** - a free, local LLM runner. It works **without Ollama** too: every agent has a rule-based fallback that activates automatically if Ollama is unreachable.

## Setup

### 1. Clone / navigate to the project

```bash
cd warRoomAI
```

### 2. Create and activate the virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables (optional)

```bash
cp .env.example .env
# edit .env if you want to use a specific Ollama model
```

### 5. (Optional) Set up Ollama for LLM-enhanced analysis

```bash
# install Ollama from https://ollama.com/download
# then pull a model:
ollama pull llama3.2
# or
ollama pull mistral
# or
ollama pull gemma3
```

> **Without Ollama**: The system runs fully with rule-based logic. All tools, agent coordination, and structured output work identically - only the natural-language reasoning text is replaced with deterministic summaries.

## Running

```bash
# Basic run (output saved to war_room_output.json)
python main.py

# Custom output path
python main.py --output results/launch_decision.json
```

## Example Output

```
============================================================
  DECISION : Pause
  CONFIDENCE: 27/100
  RISKS     : 5 identified
  ACTIONS   : 8 items
  OUTPUT    : /path/to/war_room_output.json
============================================================
```

The full structured output (`war_room_output.json`) contains:

```json
{
  "decision": "Pause",
  "rationale": {
    "summary": "...",
    "metric_references": ["crash_rate_pct: +425.0% vs baseline [critical]", "..."],
    "feedback_summary": { "sentiment_score": 34.3, "top_themes": ["crash / stability", "..."] },
    "criteria_passed": "1/4"
  },
  "risk_register": [
    { "risk": "...", "likelihood": "High", "impact": "Critical", "mitigation": "..." }
  ],
  "action_plan_24_48h": [
    { "priority": 1, "action": "...", "owner": "Engineering", "window": "0–4 hours" }
  ],
  "communication_plan": {
    "internal": ["..."],
    "external": ["..."]
  },
  "confidence": {
    "score": 27,
    "confidence_boosters": ["Crash rate resolved below 1%", "..."]
  }
}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Model to use (must be pulled via `ollama pull`) |

## Project Structure

```
warRoomAI/
├── venv/                    
├── data/
│   ├── metrics.json         # 10-day time series for 10 metrics
│   ├── feedback.json        # 35 user feedback entries
│   └── release_notes.md     # Feature description + known issues
├── tools.py                 # 4 tools: aggregate, anomaly, sentiment, trends
├── agents.py                # 4 agents: DataAnalyst, PM, Marketing, Risk
├── orchestrator.py          # Workflow coordinator + final decision logic
├── llm.py                   # Ollama client with rule-based fallback
├── main.py                  # Entry point
├── requirements.txt
├── .env.example
├── .gitignore
├── war_room_output.json
└── README.md
```
