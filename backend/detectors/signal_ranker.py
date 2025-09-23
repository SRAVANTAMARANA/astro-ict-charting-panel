# backend/detectors/signal_ranker.py
from typing import List, Dict, Any

# Simple static priority mapping. Lower number => higher priority
PRIORITY = {
    "LIQ_SWEEP_HIGH": 1,
    "LIQ_SWEEP_LOW": 1,
    "TURTLE_SOUP_SELL": 2,
    "TURTLE_SOUP_BUY": 2,
    "FVG_BULL": 3,
    "FVG_BEAR": 3,
    "MS_UPTREND": 4,
    "MS_DOWNTREND": 4,
    "MS_NO_CLEAR": 10
}

def rank_signals(signals: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    for s in signals:
        s["priority"] = PRIORITY.get(s.get("type",""), 100)
    # sort by priority ascending
    return sorted(signals, key=lambda x: x.get("priority", 100))
