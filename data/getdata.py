import MetaTrader5 as mt5
import pandas as pd
from utils.common import getNameDateFile
# --- Khởi động kết nối ---
if not mt5.initialize():
    print("Initialize failed")
    mt5.shutdown()
symbol = "EURUSDm"
timeframe = mt5.TIMEFRAME_M5  # M5 = nến 5 phút
n = 20000  # số nến muốn lấy
# --- Lấy dữ liệu ---
rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
# --- Chuyển sang DataFrame ---
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df.to_csv(getNameDateFile(timeframe=timeframe), index=False)
print(df.head())
mt5.shutdown()
