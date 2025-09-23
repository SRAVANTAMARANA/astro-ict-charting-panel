# backend/detectors/market_structure.py
from typing import List, Dict, Any

def detect_market_structure(candles: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    """
    Basic market structure detection:
    - looks at last N swing closes to classify uptrend/downtrend/sideways
    - returns MS_UPTREND / MS_DOWNTREND with price and description
    """
    signals=[]
    n = len(candles)
    if n < 5:
        return signals
    # look at last three swing closes (simple method)
    closes = [candles[-i]["close"] for i in range(1,5)]
    # closes: [last, prev, prev2, prev3]
    if closes[3] < closes[2] < closes[1] < closes[0]:
        signals.append({"type":"MS_UPTREND","price":closes[0],"desc":"Higher highs and higher lows (uptrend)"})
    elif closes[3] > closes[2] > closes[1] > closes[0]:
        signals.append({"type":"MS_DOWNTREND","price":closes[0],"desc":"Lower highs and lower lows (downtrend)"})
    else:
        signals.append({"type":"MS_NO_CLEAR","price":closes[0],"desc":"No clear market structure (range/sideways)"})
    return signals
