import pandas as pd
import io

# Load dữ liệu từ nội dung file csv được cung cấp
# Do dữ liệu cung cấp dạng text trong prompt, tôi sẽ giả lập việc đọc file
# Trong môi trường thực tế, dòng này sẽ là pd.read_csv('filename.csv')

# Giả lập dữ liệu để xử lý (Dựa trên cấu trúc file bạn gửi)
# Tôi sẽ đọc file thật được upload trong môi trường sandbox
input_file = 'Danh-muc-Phuong-xa_moi.xlsx - 1.DM Phường xã mới .csv'

try:
    df = pd.read_csv(input_file, encoding='utf-8')
except:
    # Fallback nếu encoding lỗi
    df = pd.read_csv(input_file, encoding='latin1') # hoặc cp1258 tùy file VN

# Làm sạch tên cột (bỏ khoảng trắng thừa)
df.columns = [c.strip() for c in df.columns]

# --- XỬ LÝ CẤP 1: TỈNH/THÀNH PHỐ ---
df_level1 = df[['Mã tỉnh (TMS)', 'Tên tỉnh/TP mới']].drop_duplicates()
df_level1 = df_level1.rename(columns={'Mã tỉnh (TMS)': 'Area_CD', 'Tên tỉnh/TP mới': 'Area_Name'})
df_level1['Lv'] = 1
df_level1['P_CD'] = None # Cấp tỉnh không có cha trong bảng này (hoặc có thể để null)

# --- XỬ LÝ CẤP 2: QUẬN/HUYỆN ---
df_level2 = df[['Mã Quận huyện TMS (cũ) CQT đã rà soát', 'Tên Quận huyện TMS (cũ)', 'Mã tỉnh (TMS)']].drop_duplicates()
df_level2 = df_level2.rename(columns={
    'Mã Quận huyện TMS (cũ) CQT đã rà soát': 'Area_CD', 
    'Tên Quận huyện TMS (cũ)': 'Area_Name',
    'Mã tỉnh (TMS)': 'P_CD'
})
df_level2['Lv'] = 2

# --- XỬ LÝ CẤP 3: PHƯỜNG/XÃ ---
df_level3 = df[['Mã phường/xã mới', 'Tên Phường/Xã mới', 'Mã Quận huyện TMS (cũ) CQT đã rà soát']].drop_duplicates()
df_level3 = df_level3.rename(columns={
    'Mã phường/xã mới': 'Area_CD', 
    'Tên Phường/Xã mới': 'Area_Name',
    'Mã Quận huyện TMS (cũ) CQT đã rà soát': 'P_CD'
})
df_level3['Lv'] = 3

# --- GỘP DỮ LIỆU ---
final_df = pd.concat([df_level1, df_level2, df_level3], ignore_index=True)

# --- THÊM CÁC CỘT MẶC ĐỊNH THEO TABLE ORACLE ---
final_df['CTR_CD'] = 'VN'
final_df['Tax_Rate'] = 0
final_df['Deli_Rate'] = 0
final_df['Use_YN'] = 'Y'
final_df['Remark'] = None
final_df['Ref_Cnt'] = 0
final_df['Ref_Cnt_Act'] = 0
final_df['Ref_Cnt_Term'] = 0
final_df['Ref_Last_Date'] = None
final_df['Ref_Date'] = None
# Work_Date và Work_User thường để DB tự handle default hoặc nhập lúc import
final_df['Work_User'] = 'master' 

# --- SẮP XẾP CỘT ĐÚNG THỨ TỰ CREATE TABLE ---
column_order = [
    'CTR_CD', 'Area_CD', 'Area_Name', 'Lv', 'P_CD', 
    'Tax_Rate', 'Deli_Rate', 'Use_YN', 'Remark',
    'Ref_Cnt', 'Ref_Cnt_Act', 'Ref_Cnt_Term', 'Ref_Last_Date', 'Ref_Date',
    'Work_User'
]

# Lọc và sắp xếp lại
final_output = final_df[column_order]

# Chuyển đổi kiểu dữ liệu Area_CD và P_CD sang chuỗi để tránh Excel hiểu nhầm là số
final_output['Area_CD'] = final_output['Area_CD'].astype(str)
final_output['P_CD'] = final_output['P_CD'].fillna('').astype(str)

# Xuất ra Excel
output_filename = 'Import_Country_Area_Vietnam.xlsx'
final_output.to_excel(output_filename, index=False)

print(f"File created: {output_filename}")