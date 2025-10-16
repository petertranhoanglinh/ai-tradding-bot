from fastapi import FastAPI
import MetaTrader5 as mt5
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
import time

app = FastAPI()

@app.get("/")
def home():
    return {"message": "✅ AI Trading Bot API running..."}

@app.get("/train")
def retrain_model():
    symbol = "EURUSDm"
    timeframe = mt5.TIMEFRAME_H1
    n = 8760  # ~1 năm dữ liệu (H1 = 1h)

    # --- Kết nối MT5 ---
    if not mt5.initialize():
        return {"error": f"Không kết nối được MT5: {mt5.last_error()}"}

    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
    mt5.shutdown()

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    # --- Feature engineering ---
    df["MA10"] = df["close"].rolling(10).mean()
    df["RSI"] = df["close"].diff().rolling(14).mean()  # đơn giản hoá RSI

    df["label"] = (df["close"].shift(-3) > df["close"]).astype(int)
    df = df.dropna()

    features = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume", "MA10", "RSI"]
    X = df[features]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42)
    model.fit(X_train, y_train)

    acc = accuracy_score(y_test, model.predict(X_test))
    joblib.dump(model, "model/model.pkl")

    return {"message": "✅ Model retrained successfully", "accuracy": round(acc, 4), "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}


@app.get("/predict")
def predict(symbol: str = "EURUSDm", timeframe: str = "H1", num_bars: int = 1):
    # --- 1. Kết nối MT5 ---
    if not mt5.initialize():
        return {"error": f"❌ Không thể khởi tạo MT5: {mt5.last_error()}"}

    # --- 2. Chuyển timeframe string sang mã timeframe của MT5 ---
    timeframe_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1
    }

    if timeframe not in timeframe_map:
        mt5.shutdown()
        return {"error": "❌ Timeframe không hợp lệ (dùng M1, M5, M15, M30, H1, H4, D1)"}
    tf = timeframe_map[timeframe]
    # --- 3. Lấy dữ liệu ---
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, num_bars)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        return {"error": "❌ Không lấy được dữ liệu từ MT5."}

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    features = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
    X_new = df[features]

    # --- 4. Load model ---
    try:
        model = joblib.load("./model/model.pkl")
    except Exception as e:
        return {"error": f"❌ Không thể mở model: {e}"}

    # --- 5. Dự đoán ---
    pred = model.predict(X_new)[-1]
    last_close = df["close"].iloc[-1]

    result = {
        "symbol": symbol,
        "timeframe": timeframe,
        "last_close": float(last_close),
        "prediction": "BUY" if pred == 1 else "SELL",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    return result