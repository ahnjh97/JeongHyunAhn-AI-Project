import cv2
import datetime
from flask import Flask, Response
from flask_cors import CORS
from flask_restx import Api, Resource, fields
from ultralytics import YOLO

app = Flask(__name__)
CORS(app)

# --- 1. RESTX API 설정 ---
api = Api(app, 
          version='1.0', 
          title='PreDect AI API',
          description='베이즈 정리 기반 자율주행 위험 감지 시스템 (YOLOv11n)',
          doc='/docs')

ns = api.namespace('detection', description='AI 추론 및 실시간 데이터 제공')

# --- 2. 모델 로드 및 전역 변수 ---
model = YOLO("PreDect.pt")
current_risk_data = {
    "probability": 0.0,
    "detected_objects": []
}

# Swagger UI에 표시될 데이터 모델 정의
risk_model = api.model('RiskData', {
    'probability': fields.Float(description='계산된 사후 확률 (0.0~1.0)', example=0.228),
    'detected_objects': fields.List(fields.String, description='탐지된 객체 목록', example=['person', 'sports ball'])
})

# --- 3. 확률 계산 로직 (베이즈 정리) ---
def calculate_posterior_probability(prior_prob, likelihood_jump, likelihood_not_jump):
    """베이즈 정리를 이용한 사후 확률 계산: P(Jump|Ball)"""
    # P(Ball) = P(Ball|Jump)P(Jump) + P(Ball|NotJump)P(NotJump)
    ball_prob = (prior_prob * likelihood_jump) + ((1 - prior_prob) * likelihood_not_jump)
    # P(Jump|Ball) = P(Ball|Jump)P(Jump) / P(Ball)
    post_prob = (likelihood_jump * prior_prob) / ball_prob
    return post_prob

def calculate_risk(results):
    """객체 탐지 결과에 기반한 위험도 산출"""
    has_person = False
    has_ball = False
    
    for r in results:
        for box in r.boxes:
            cls_name = model.names[int(box.cls[0])]
            if cls_name == 'person':
                has_person = True
            elif cls_name == 'sports_ball':
                has_ball = True
                
    if not has_person:
        return 0.0
        
    prior_prob = 0.1           # P(Jump)
    likelihood_jump = 0.8      # P(Ball|Jump)
    likelihood_not_jump = 0.3  # P(Ball|Not Jump)
    
    if has_ball:
        risk_prob = calculate_posterior_probability(prior_prob, likelihood_jump, likelihood_not_jump)
    else:
        risk_prob = prior_prob
        
    return min(risk_prob, 1.0)

# --- 4. 영상 처리 생성기 ---
def generate_frames():
    cap = cv2.VideoCapture("clip_ball.mp4")
    
    while True:
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        results = model(frame, verbose=False)
        
        global current_risk_data
        current_risk_data["probability"] = calculate_risk(results)
        current_risk_data["detected_objects"] = list(set([model.names[int(b.cls[0])] for r in results for b in r.boxes]))
        
        annotated_frame = results[0].plot()
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        if not ret:
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# --- 5. RESTful Resources (엔드포인트) ---

@ns.route('/video-feed')
class VideoFeed(Resource):
    @ns.doc('실시간 스트리밍 영상 전송')
    def get(self):
        """YOLO 바운딩 박스가 포함된 MJPEG 스트림을 반환합니다."""
        return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@ns.route('/risk-data')
class RiskData(Resource):
    @ns.marshal_with(risk_model)
    @ns.doc('현재 위험 확률 데이터 조회')
    def get(self):
        """베이즈 정리에 의해 계산된 최신 확률 데이터를 반환합니다."""
        return current_risk_data

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=False)