# backend/detectors/liquidity.py
from typing import List, Dict, Any

def detect_liquidity(candles: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    """
    Detect liquidity sweeps: large wick that takes out previous extreme then closes inside.
    """
    signals=[]
    n=len(candles)
    if n < 4:
        return signals
    for i in range(2, n):
        prev = candles[i-2]
        last = candles[i-1]
        # sweep above: wick high > prev.high but close < prev.high (failed breakout)
        if last["high"] > prev["high"] and last["close"] < prev["high"]:
            signals.append({"type":"LIQ_SWEEP_HIGH","index":i-1,"price": last["high"], "desc":"Liquidity sweep above previous high"})
        # sweep below: wick low < prev.low but close > prev.low
        if last["low"] < prev["low"] and last["close"] > prev["low"]:
            signals.append({"type":"LIQ_SWEEP_LOW","index":i-1,"price": last["low"], "desc":"Liquidity sweep below previous low"})
    return signals
