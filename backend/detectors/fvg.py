# backend/detectors/fvg.py
from typing import List, Dict, Any

def detect_fvg(candles: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    """
    Identify Fair Value Gaps (FVG):
    - Check consecutive candles where body gap exists between candle A and B (no overlap).
    - Return mid-price and type (BULL/BEAR) with index and strength.
    """
    signals=[]
    n = len(candles)
    # require at least 3 candles for reliable FVG detection
    for i in range(1, n-1):
        a = candles[i-1]
        b = candles[i]
        # bodies:
        a_low = min(a["open"], a["close"])
        a_high = max(a["open"], a["close"])
        b_low = min(b["open"], b["close"])
        b_high = max(b["open"], b["close"])
        # If b body entirely above a body -> bullish gap
        if b_low > a_high + 1e-9:
            mid = (a_high + b_low) / 2.0
            strength = round((b_low - a_high), 6)
            signals.append({"type":"FVG_BULL","index":i,"price":mid,"strength":strength,"desc":"Bull FVG"})
        # If b body entirely below a body -> bearish gap
        elif b_high < a_low - 1e-9:
            mid = (a_low + b_high) / 2.0
            strength = round((a_low - b_high), 6)
            signals.append({"type":"FVG_BEAR","index":i,"price":mid,"strength":strength,"desc":"Bear FVG"})
    return signals
