import cv2
from flask import Flask, Response, jsonify
from flask_cors import CORS
from ultralytics import YOLO

app = Flask(__name__)
CORS(app)

# 1. 모델 로드 (파일 경로 확인 필수)
model = YOLO("PreDect.pt")

# 최신 추론 결과를 저장할 전역 변수
current_risk_data = {
    "probability": 0.0,
    "detected_objects": []
}

def calculate_posterior_probability(prior_prob, likelihood_jump, likelihood_not_jump):
    """
    베이즈 정리를 이용한 사후 확률 계산 함수
    """
    # P(Ball): 공이 존재할 전체 확률 = P(Ball|Jump)*P(Jump) + P(Ball|Not Jump)*P(Not Jump)
    ball_prob = (prior_prob * likelihood_jump) + ((1 - prior_prob) * likelihood_not_jump)

    # P(Jump|Ball): 공이 있을 때 아이가 도로로 뛰어들 사후 확률
    post_prob = (likelihood_jump * prior_prob) / ball_prob

    return post_prob

def calculate_risk(results, model):
    """
    탐지된 객체들을 바탕으로 베이즈 정리를 활용해 아이가 뛰어들 확률을 계산하는 로직
    """
    has_person = False
    has_ball = False
    
    # 1. YOLO 탐지 결과에서 객체 확인
    for r in results:
        for box in r.boxes:
            cls_name = model.names[int(box.cls[0])]
            
            if cls_name == 'person':
                has_person = True
            elif cls_name == 'sports ball':
                has_ball = True
                
    # 2. 보행자(사람)가 아예 탐지되지 않았다면 뛰어들 위험도는 0%
    if not has_person:
        return 0.0
        
    # 3. 확률 변수 설정 (실제 환경에 맞게 튜닝 가능)
    prior_prob = 0.1          # P(Jump): 평상시 아이가 도로로 뛰어들 기본 확률 (10%)
    likelihood_jump = 0.8     # P(Ball|Jump): 도로로 뛰어드는 아이 상황에서 공이 발견될 확률 (80%)
    likelihood_not_jump = 0.3 # P(Ball|Not Jump): 뛰어들지 않는 아이 주변에 공이 있을 확률 (30%)
    
    # 4. 객체 탐지 상태에 따른 위험도 계산
    if has_ball:
        # 사람과 공이 모두 있는 경우: 베이즈 정리로 사후 확률 계산
        risk_prob = calculate_posterior_probability(prior_prob, likelihood_jump, likelihood_not_jump)
    else:
        # 사람만 있고 공은 없는 경우: 기본 사전 확률 유지
        risk_prob = prior_prob
        
    return min(risk_prob, 1.0) # 최대 100%로 제한 (안전 장치)

def generate_frames():
    # 비디오 파일 경로 또는 0 (웹캠)
    cap = cv2.VideoCapture("clip_ball.mp4")
    
    while True:
        success, frame = cap.read()
        if not success:
            # 영상이 끝나면 다시 처음으로 돌리거나 루프 종료
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        
        # 1. YOLO 추론 수행
        results = model(frame, verbose=False)
        
        # 2. 전역 변수에 데이터 업데이트
        global current_risk_data
        current_risk_data["probability"] = calculate_risk(results)
        # 중복 제거된 탐지 객체 리스트 생성
        current_risk_data["detected_objects"] = list(set([model.names[int(b.cls[0])] for r in results for b in r.boxes]))
        
        # 3. 화면용 프레임 인코딩 (바운딩 박스 포함)
        annotated_frame = results[0].plot()
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    """실시간 영상 스트리밍 엔드포인트"""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_risk')
def get_risk():
    """최신 확률 데이터 JSON 엔드포인트"""
    return jsonify(current_risk_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=False)