import MetaTrader5 as mt5
import pandas as pd
import joblib

if not mt5.initialize():
    print("❌ Không thể khởi tạo MT5:", mt5.last_error())
    quit()
symbol = "EURUSDm"  
timeframe = mt5.TIMEFRAME_H1  
num_bars = 1  
rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_bars)
if rates is None or len(rates) == 0:
    print("❌ Không lấy được dữ liệu MT5.")
    mt5.shutdown()
    quit()
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s")
features = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
X_new = df[features]
model = joblib.load("./model/model.pkl")
pred = model.predict(X_new)[0]
last_close = df["close"].iloc[-1]
if pred == 1:
    print(f"👉 AI dự đoán: GIÁ TĂNG (BUY) | Close hiện tại: {last_close}")
else:
    print(f"👉 AI dự đoán: GIÁ GIẢM (SELL) | Close hiện tại: {last_close}")
mt5.shutdown()
