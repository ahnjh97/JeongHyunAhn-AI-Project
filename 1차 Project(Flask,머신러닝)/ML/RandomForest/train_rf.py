import pandas as pd
import oracledb
import platform
import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

if platform.system() == 'Windows':
    oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
else:
    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")
db_config = {'user': 'scott', 'password': 'tiger', 'dsn': 'localhost:1521/xe'}

def train_disease_rf(df, disease_type):
    """
    질병별 4일치(D0~D3) '인구 1만 명당 발생률' 예측 모델
    """
    print(f"\n🚀 [{disease_type} 발생률 RandomForest 모델] 학습 시작 (Target: 1만명당 환자수)...")

    # [1] 타겟 추출 및 정렬
    target_cnt_cols = [
        f"{disease_type.upper()}_CNT_D0",
        f"{disease_type.upper()}_CNT_D_PLUS_1",
        f"{disease_type.upper()}_CNT_D_PLUS_2",
        f"{disease_type.upper()}_CNT_D_PLUS_3"
    ]

    # [2] 핵심: 환자 수를 발생률로 변환 후 로그 변환 추가
    y_rate = pd.DataFrame()
    for col in target_cnt_cols:
        # 발생률 계산
        rate = (df[col] / df['POP_TOTAL'].replace(0, np.nan)) * 10000
        # 로그 변환 적용 (데이터의 왜곡 완화)
        y_rate[col] = np.log1p(rate)
    y_rate = y_rate.fillna(0)

    # [3] 특징(X) 생성
    # 모든 정답(Target) 컬럼 식별 (D0, D+1, D+2, D+3 모두 포함)
    all_target_cols = [col for col in df.columns if 'CNT_D' in col.upper()]

    # 모든 과거 환자수(PREV) 컬럼 중 '다른 질병' 것만 식별
    all_prev_cols = ["COLD_PREV_D1", "COLD_PREV_D2", "COLD_PREV_D3",
                     "ASTHMA_PREV_D1", "ASTHMA_PREV_D2", "ASTHMA_PREV_D3"]
    other_disease_prev_cols = [col for col in all_prev_cols if disease_type not in col]

    # 3. 기본 드랍 (ID성, 정답들, 다른 질병 과거치, 인구, 요일)
    # DIST_CODE는 인코딩을 위해 잠시 남겨둡니다.
    drop_cols = ['MEASURE_DATE', 'POP_TOTAL', 'DAY_OF_WEEK'] + all_target_cols + other_disease_prev_cols
    X_base = df.drop(columns=drop_cols)

    # 4. 자치구 원-핫 인코딩 수행
    #  컬럼 순서 고정을 위해 get_dummies 후 컬럼명을 정렬
    X_final = pd.get_dummies(X_base, columns=['DIST_CODE'], prefix='DIST', dtype=int)

    # [4] 데이터 분할 (날짜 기준)
    # X_final에는 이미 DIST 인코딩이 완료되었고 MEASURE_DATE는 df에서 가져와서 마스킹
    train_mask = (df['MEASURE_DATE'] >= '2015-01-01') & (df['MEASURE_DATE'] <= '2021-12-31')
    test_mask = (df['MEASURE_DATE'] >= '2022-01-01') & (df['MEASURE_DATE'] <= '2022-12-31')

    X_train = X_final[train_mask]
    y_train = y_rate[train_mask]

    X_test = X_final[test_mask]
    y_test = y_rate[test_mask]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # [5] 학습 (랜덤 포레스트)
    rf = RandomForestRegressor(n_estimators=200, max_depth=20, min_samples_split=5, random_state=42, n_jobs=-1)
    rf.fit(X_train_scaled, y_train)

    # [6] 성능 평가
    preds_log = rf.predict(X_test_scaled)

    # 로그 처리된 값을 다시 원래 숫자로 복원
    y_test_original = np.expm1(y_test)
    preds_original = np.expm1(preds_log)

    # 복원된 값으로 오차 계산
    mae = mean_absolute_error(y_test_original, preds_original)
    r2 = r2_score(y_test_original, preds_original)

    print(f"✅ {disease_type} 발생률 학습 완료!")
    print(f"📈 전체 평균 R2 Score: {r2:.4f}")
    print(f"📊 전체 평균 MAE: {mae:.4f} (명/1만명)")

    # [7] 중요도 및 저장
    importances = pd.Series(rf.feature_importances_, index=X_train.columns).sort_values(ascending=False)
    print(f"💡 중요 변수 TOP 5:\n{importances.head(5)}")

    model_filename = f'model_{disease_type.lower()}_rf.pkl'
    scaler_filename = f'scaler_{disease_type.lower()}_rf.pkl'

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
        train_disease_rf(df_clean, 'COLD')

        # 2. 천식(ASTHMA) 4일치 모델 학습 및 저장
        train_disease_rf(df_clean, 'ASTHMA')

        print("\n✨ 모든 모델 학습 및 저장 작업이 완료되었습니다!")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == '__main__':
    main()