from datetime import datetime

def getNameDateFile(timeframe: str):
    now = datetime.now().strftime("%Y%m%d")
    return f"./data/eurusd_{timeframe}_{now}.csv"
