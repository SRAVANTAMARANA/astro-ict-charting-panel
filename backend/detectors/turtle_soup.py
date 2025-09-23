# backend/detectors/turtle_soup.py
from typing import List, Dict, Any

def detect_turtle_soup(candles: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    """
    Turtle Soup-like false breakout detection:
    - Look for a candle making new recent high then closing back below the last swing high -> false breakout SELL
    - And vice versa for BUY
    """
    signals=[]
    n=len(candles)
    if n < 6:
        return signals
    # define recent swing high/low from 3 bars before
    for i in range(5, n):
        window = candles[i-5:i]  # previous 5 candles
        highs = [c["high"] for c in window]
        lows = [c["low"] for c in window]
        swing_high = max(highs)
        swing_low = min(lows)
        c = candles[i]
        # false breakout up
        if c["high"] > swing_high and c["close"] < swing_high:
            signals.append({"type":"TURTLE_SOUP_SELL","index":i,"price":c["high"],"desc":"False breakout above swing high"})
        # false breakout down
        if c["low"] < swing_low and c["close"] > swing_low:
            signals.append({"type":"TURTLE_SOUP_BUY","index":i,"price":c["low"],"desc":"False breakout below swing low"})
    return signals
