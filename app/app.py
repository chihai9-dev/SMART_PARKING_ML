from flask import Flask, render_template, request, jsonify
import pandas as pd
import joblib
from datetime import datetime
import os

app = Flask(__name__)

# ==========================================
# 1. LOAD MÔ HÌNH ML KHI KHỞI ĐỘNG SERVER
# ==========================================
# Lấy đường dẫn gốc của project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, '../models')

clf_model = joblib.load(os.path.join(MODEL_DIR, 'classification/best_classification_model.pkl'))
reg_model = joblib.load(os.path.join(MODEL_DIR, 'regression/best_regression_model.pkl'))
demand_model = joblib.load(os.path.join(MODEL_DIR, 'demand/best_demand_model.pkl'))

# ==========================================
# 2. CÁC ROUTES GIAO DIỆN CƠ BẢN
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# ==========================================
# 3. API DỰ ĐOÁN (AI PREDICTION ENGINE)
# ==========================================
@app.route('/api/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        
        # Trích xuất dữ liệu từ Frontend gửi lên
        student_id = data.get('student_id', 'Unknown')
        entry_time_str = data.get('entry_time')
        vehicle = data.get('vehicle', 'Motorbike')
        usual_zone = data.get('usual_zone', 'Zone_A')
        rolling_avg = float(data.get('rolling_avg', 200))
        hist_overnight = int(data.get('hist_overnight', 0))
        
        entry_time = pd.to_datetime(entry_time_str)
        
        # --- BƯỚC 1: DỰ ĐOÁN NHU CẦU ---
        demand_features = pd.DataFrame([{
            'hour': entry_time.hour,
            'day_of_week': entry_time.weekday(),
            'is_weekend': 1 if entry_time.weekday() >= 5 else 0,
            'is_morning': 1 if entry_time.hour < 12 else 0,
            'is_exam_week': 0
        }])[demand_model.feature_names_in_]
        
        current_demand = int(demand_model.predict(demand_features)[0])
        
        # --- BƯỚC 2: PHÂN LOẠI & HỒI QUY ---
        clf_features = pd.DataFrame([{
            'entry_hour': entry_time.hour,
            'entry_minute': entry_time.minute,
            'day_of_week_num': entry_time.weekday(),
            'is_weekend': 1 if entry_time.weekday() >= 5 else 0,
            'is_morning': 1 if entry_time.hour < 12 else 0,
            'rolling_avg_duration': rolling_avg,
            'historical_overnight_count': hist_overnight,
            'vehicle_type_Motorbike': 1 if vehicle == 'Motorbike' else 0,
            'usual_zone_Zone_B': 1 if usual_zone == 'Zone_B' else 0,
            'usual_zone_Zone_C': 1 if usual_zone == 'Zone_C' else 0,
            'usual_zone_Zone_D': 1 if usual_zone == 'Zone_D' else 0,
            'is_exam_week': 0
        }])[clf_model.feature_names_in_]
        
        predicted_behavior = clf_model.predict(clf_features)[0]
        raw_predicted_minutes = reg_model.predict(clf_features)[0]
        
        # --- BƯỚC 3: LOGIC ĐỀ XUẤT ---
        if predicted_behavior == 'Early_Return':
            est_min = min(raw_predicted_minutes, 210)
            zone_rec = "Khu A (Ra vào nhanh)"
        elif predicted_behavior == 'Full_Day':
            est_min = max(raw_predicted_minutes, 240)
            zone_rec = "Khu B/C (Đỗ lâu)"
        elif predicted_behavior == 'Overnight':
            est_min = max(raw_predicted_minutes, 720)
            zone_rec = "Khu D (An ninh qua đêm)"
        else:
            est_min = raw_predicted_minutes
            zone_rec = "Khu D (Dài ngày)"
            
        estimated_exit = entry_time + pd.Timedelta(minutes=est_min)
        
        # Trả kết quả về cho giao diện
        return jsonify({
            'status': 'success',
            'student_id': student_id,
            'current_demand': current_demand,
            'behavior': predicted_behavior,
            'duration_minutes': int(est_min),
            'estimated_exit': estimated_exit.strftime('%H:%M - %d/%m/%Y'),
            'recommended_zone': zone_rec
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    # Chạy server ở port 5000
    app.run(debug=True, port=5000)