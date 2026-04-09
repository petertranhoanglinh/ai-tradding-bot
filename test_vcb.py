from vnstock import Quote, Vnstock, Listing
import pandas as pd

symbol = 'VCB'
src = 'vci'

print(f"--- Inspecting Quote for source: {src} ---")
try:
    q = Quote(symbol=symbol, source=src)
    print(f"Quote attributes: {dir(q)}")
    
    # Try different ways to get price board
    if hasattr(q, 'trading'):
        print(f"q.trading attributes: {dir(q.trading)}")
    
    # Try direct methods if trading is missing
    for method in ['price_board', 'board', 'realtime', 'quote']:
        if hasattr(q, method):
            print(f"Found method: q.{method}")
            try:
                res = getattr(q, method)()
                print(f"Result from {method}: {type(res)}")
                if isinstance(res, pd.DataFrame): print(res.head(1).to_dict())
            except Exception as e:
                print(f"Error calling {method}: {e}")

except Exception as e:
    print(f"Quote Init Error: {e}")

print(f"\n--- Inspecting Vnstock Object ---")
try:
    vn = Vnstock()
    print(f"Vnstock methods: {dir(vn)}")
    stock = vn.stock(symbol=symbol, source=src)
    print(f"vn.stock attributes: {dir(stock)}")
except Exception as e:
    print(f"Vnstock Error: {e}")
