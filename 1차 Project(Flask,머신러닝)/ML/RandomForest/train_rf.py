import pandas as pd
import oracledb
import platform
import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

# 1. DB 접속 설정
if platform.system() == 'Windows':
    oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
else:
    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")
db_config = {'user': 'scott', 'password': 'tiger', 'dsn': 'localhost:1521/xe'}


def train_disease_model(df, disease_type):
    """
    질병별 4일치(D0~D3) '인구 1만 명당 발생률' 예측 모델
    """
    print(f"\n🚀 [{disease_type} 발생률 모델] 학습 시작 (Target: 1만명당 환자수)...")

    # [1] 타겟 추출 및 정렬
    target_cnt_cols = [col for col in df.columns if disease_type.upper() in col.upper() and 'CNT_D' in col.upper()]
    target_cnt_cols.sort()

    # [2] 핵심: 환자 수를 발생률로 변환 (명 -> 1만명당 발생건수)
    y_rate = pd.DataFrame()
    for col in target_cnt_cols:
        # pop_total이 0인 경우 대비하여 1만명당 비율 계산
        y_rate[col] = (df[col] / df['POP_TOTAL'].replace(0, np.nan)) * 10000
    y_rate = y_rate.fillna(0) # 결측치 방어

    # [3] 특징(X) 생성
    # 제외 대상: ID성(DIST_CODE, MEASURE_DATE), 타겟계산용(POP_TOTAL), 모든 질병 CNT 컬럼들
    all_cnt_cols = [col for col in df.columns if 'CNT_D' in col.upper()]
    X_base = df.drop(columns=['DIST_CODE', 'MEASURE_DATE', 'POP_TOTAL'] + all_cnt_cols)

    # 자치구 원-핫 인코딩
    X_dist = pd.get_dummies(df['DIST_CODE'], prefix='DIST')
    X = pd.concat([X_base, X_dist], axis=1)

    # [4] 데이터 분할 및 스케일링
    X_train, X_test, y_train, y_test = train_test_split(X, y_rate, test_size=0.2, random_state=42)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # [5] 학습 (랜덤 포레스트)
    rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X_train_scaled, y_train)

    # [6] 성능 평가
    preds = rf.predict(X_test_scaled)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    print(f"✅ {disease_type} 발생률 학습 완료!")
    print(f"📈 전체 평균 R2 Score: {r2:.4f}")
    print(f"📊 전체 평균 MAE: {mae:.4f} (명/1만명)")

    # [7] 중요도 및 저장
    importances = pd.Series(rf.feature_importances_, index=X.columns).sort_values(ascending=False)
    print(f"💡 중요 변수 TOP 5:\n{importances.head(5)}")

    model_filename = f'model_{disease_type.lower()}_4days.pkl'
    scaler_filename = f'scaler_{disease_type.lower()}_4days.pkl'

    joblib.dump(rf, model_filename)
    joblib.dump(scaler, scaler_filename)

    print(f"💾 저장 완료: {model_filename}, {scaler_filename}")
    return rf


def main():
    try:
        # 데이터 로드
        conn = oracledb.connect(**db_config)
        print("🔗 DB 연결 성공!")
        df = pd.read_sql("SELECT * FROM TRAIN_SET ORDER BY measure_date, dist_code", conn)
        conn.close()

        # 결측치 제거
        df_clean = df.dropna()
        if len(df_clean) == 0:
            print("❌ 에러: 정제 후 데이터가 0행입니다. 결측치를 확인하세요.")
            return

        print(f"🧹 전처리 완료: {len(df)}행 -> {len(df_clean)}행")

        # --- 질병별 4일 통합 모델 학습 시작 ---

        # 1. 감기(COLD) 4일치 모델 학습 및 저장
        train_disease_model(df_clean, 'COLD')

        # 2. 천식(ASTHMA) 4일치 모델 학습 및 저장
        train_disease_model(df_clean, 'ASTHMA')

        print("\n✨ 모든 모델 학습 및 저장 작업이 완료되었습니다!")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")


if __name__ == '__main__':
    main()