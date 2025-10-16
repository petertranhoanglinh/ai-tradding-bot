import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib
import MetaTrader5 as mt5
from utils.common import getNameDateFile
df = pd.read_csv(getNameDateFile(timeframe=mt5.TIMEFRAME_M5))
if df["time"].dtype != "object":
    df["time"] = pd.to_datetime(df["time"], unit="s")

df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
df = df.dropna()
features = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
X = df[features]
y = df["target"]
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, shuffle=False
)
model = RandomForestClassifier(
    n_estimators=200, max_depth=8, random_state=42
)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print(f"🎯 Độ chính xác: {acc:.2%}")
joblib.dump(model, "./model/model.pkl")
print("✅ Mô hình đã được lưu tại model.pkl")
