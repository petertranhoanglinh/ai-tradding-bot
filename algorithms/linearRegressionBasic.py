import numpy as np
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

# Dữ liệu
x = np.array([30 , 45, 60, 80, 100, 120]).reshape(-1, 1) # phải là dữ liệu 2d
y = np.array([480,  630, 780, 1020, 1200, 1440])

# Mô hình hồi quy
model = LinearRegression()
model.fit(x, y)

# Hệ số
b0 = model.intercept_
b1 = model.coef_[0]
r2 = model.score(x, y)

# Dự đoán giá nhà 90 m²
predict_90 = model.predict([[90]])

print(f"Phương trình hồi quy: y = {b0:.2f} + {b1:.2f}x")
print(f"Hệ số xác định R² = {r2:.3f}")
print(f"Giá dự đoán cho 90 m²: {predict_90[0]:.2f} triệu đồng")

# Vẽ biểu đồ
plt.scatter(x, y, color='blue', label='Dữ liệu thực')
plt.plot(x, model.predict(x), color='red', label='Đường hồi quy')
plt.xlabel('Diện tích (m²)')
plt.ylabel('Giá nhà (triệu đồng)')
plt.legend()
plt.show()
