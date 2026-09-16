import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def generate_smart_parking_data(num_records=10000, seed=42):
    """
    Sinh dữ liệu mô phỏng cho hệ thống Bãi đỗ xe thông minh.
    """
    np.random.seed(seed)
    
    # 1. Khởi tạo danh sách sinh viên (giả lập 2000 sinh viên thường xuyên gửi xe)
    student_ids = [f"SV{str(i).zfill(4)}" for i in range(1, 2001)]
    
    # 2. Cài đặt các nhãn hành vi (Target Variable) và xác suất
    behaviors = ['Early_Return', 'Full_Day', 'Overnight', 'Long_Term']
    behavior_probs = [0.35, 0.50, 0.10, 0.05] # Đa số là đỗ cả ngày hoặc về sớm
    
    # Giả lập 1 học kỳ (Ví dụ: Từ 01/09/2023 đến 31/12/2023)
    start_date = datetime(2023, 9, 1)
    end_date = datetime(2023, 12, 31)
    days_between = (end_date - start_date).days
    
    data = []
    
    print(f"Đang sinh {num_records} dòng dữ liệu...")
    
    for _ in range(num_records):
        student = np.random.choice(student_ids)
        behavior = np.random.choice(behaviors, p=behavior_probs)
        
        # Chọn ngày ngẫu nhiên
        random_days = np.random.randint(0, days_between)
        current_date = start_date + timedelta(days=random_days)
        
        # Bỏ qua phần lớn Chủ Nhật (rất ít sinh viên đi học)
        if current_date.weekday() == 6 and np.random.rand() > 0.1:
            current_date -= timedelta(days=1)
            
        # 3. Tạo Giờ Vào (Entry Time) dùng Phân phối chuẩn (Normal Distribution)
        # Sinh viên thường vào lúc 6:45-7:30 (ca sáng) hoặc 12:30-13:15 (ca chiều)
        is_morning = np.random.choice([True, False], p=[0.65, 0.35])
        
        if is_morning:
            # Trung bình 7:00 (7.0), độ lệch chuẩn 0.5 giờ (30 phút)
            entry_hour_float = np.random.normal(loc=7.0, scale=0.5)
        else:
            # Trung bình 12:45 (12.75), độ lệch chuẩn 0.5 giờ (30 phút)
            entry_hour_float = np.random.normal(loc=12.75, scale=0.5)
            
        # Ép giờ vào trong khoảng thực tế của bãi xe (5h30 sáng đến 18h tối)
        entry_hour_float = np.clip(entry_hour_float, 5.5, 18.0)
        
        entry_time = current_date + timedelta(hours=int(entry_hour_float), 
                                              minutes=int((entry_hour_float % 1) * 60))
        
        # 4. Tính toán Giờ Ra (Exit Time) logic theo Nhãn Hành Vi
        if behavior == 'Early_Return':
            # Đỗ từ 1 đến 3.5 tiếng (Sinh viên học 1-2 ca)
            duration_hours = np.random.uniform(1.0, 3.5)
        elif behavior == 'Full_Day':
            # Đỗ từ 4 đến 9 tiếng (Học cả ngày hoặc kẹt trên thư viện)
            duration_hours = np.random.uniform(4.0, 9.0)
        elif behavior == 'Overnight':
            # Đỗ qua đêm: 12 đến 24 tiếng
            duration_hours = np.random.uniform(12.0, 24.0)
        else: # Long_Term
            # Đỗ nhiều ngày: 24 đến 72 tiếng (1-3 ngày - có thể đi thực tập hoặc về quê)
            duration_hours = np.random.uniform(24.0, 72.0)
            
        exit_time = entry_time + timedelta(hours=duration_hours)
        duration_minutes = int(duration_hours * 60)
        
        # 5. Các feature giả lập thực tế khác
        # Xe máy chiếm đa số tuyệt đối so với ô tô tại Việt Nam
        vehicle_type = np.random.choice(['Motorbike', 'Car'], p=[0.98, 0.02])
        # Khu vực đỗ xe yêu thích (A, B thường gần cổng/nhà xe chính)
        usual_zone = np.random.choice(['Zone_A', 'Zone_B', 'Zone_C', 'Zone_D'], p=[0.4, 0.3, 0.2, 0.1])
        # Cờ tuần thi (Tháng 12 thường là tháng thi)
        is_exam_week = 1 if current_date.month == 12 and current_date.day > 10 else 0
        
        data.append({
            'student_id': student,
            'vehicle_type': vehicle_type,
            'entry_time': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': exit_time.strftime('%Y-%m-%d %H:%M:%S'),
            'day_of_week': entry_time.strftime('%A'),
            'duration_minutes': duration_minutes,
            'usual_zone': usual_zone,
            'is_exam_week': is_exam_week,
            'parking_behavior': behavior
        })
        
    # Tạo DataFrame và sắp xếp theo trình tự thời gian
    df = pd.DataFrame(data)
    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    df = df.sort_values(by='entry_time').reset_index(drop=True)
    
    return df

if __name__ == "__main__":
    # Đảm bảo thư mục tồn tại
    output_dir = '../../data/raw'
    os.makedirs(output_dir, exist_ok=True)
    
    # Sinh dữ liệu
    df_parking = generate_smart_parking_data(num_records=15000)
    
    # Lưu ra CSV
    output_path = os.path.join(output_dir, 'parking_data_raw.csv')
    df_parking.to_csv(output_path, index=False)
    print(f"✅ Đã lưu file dữ liệu thành công tại: {output_path}")
    print(f"📊 Kích thước dữ liệu: {df_parking.shape}")
    print(df_parking.head())