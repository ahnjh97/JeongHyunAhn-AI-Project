import oracledb
import platform
import pandas as pd
import numpy as np
import joblib
from lightgbm import LGBMRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import mean_absolute_error, r2_score

if platform.system() == 'Windows':
    oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
else:
    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")
db_config = {'user': 'scott', 'password': 'tiger', 'dsn': 'localhost:1521/xe'}


def train_disease_lgbm(df, disease_type):
    """
    LightGBM을 이용한 질병별 4일치(D0~D3) 발생률 예측 모델
    (Native Categorical 지원 버전)
    """
    print(f"\n🚀 [{disease_type} 발생률 LightGBM 모델] 학습 시작 (Target: 1만명당 환자수)...")

    # [1] 타겟 설정 (D0 ~ D+3)
    target_cnt_cols = [
        f"{disease_type.upper()}_CNT_D0",
        f"{disease_type.upper()}_CNT_D_PLUS_1",
        f"{disease_type.upper()}_CNT_D_PLUS_2",
        f"{disease_type.upper()}_CNT_D_PLUS_3"
    ]

    # [2] 발생률 및 로그 변환
    y_rate = pd.DataFrame()
    for col in target_cnt_cols:
        rate = (df[col] / df['POP_TOTAL'].replace(0, np.nan)) * 10000
        y_rate[col] = np.log1p(rate)
    y_rate = y_rate.fillna(0)

    # [3] 특징(X) 선택
    all_target_cols = [col for col in df.columns if 'CNT_D' in col.upper()]
    all_prev_cols = ["COLD_PREV_D1", "COLD_PREV_D2", "COLD_PREV_D3",
                     "ASTHMA_PREV_D1", "ASTHMA_PREV_D2", "ASTHMA_PREV_D3"]

    other_disease_prev_cols = [col for col in all_prev_cols if disease_type.upper() not in col]

    drop_cols = ['MEASURE_DATE', 'POP_TOTAL', 'DAY_OF_WEEK'] + all_target_cols + other_disease_prev_cols
    X_final = df.drop(columns=drop_cols).copy()

    # 카테고리 타입 변환
    X_final['DIST_CODE'] = X_final['DIST_CODE'].astype('category')

    # [4] 데이터 분할
    train_mask = (df['MEASURE_DATE'] >= '2015-01-01') & (df['MEASURE_DATE'] <= '2021-12-31')
    test_mask = (df['MEASURE_DATE'] >= '2022-01-01') & (df['MEASURE_DATE'] <= '2022-12-31')

    X_train, y_train = X_final[train_mask], y_rate[train_mask]
    X_test, y_test = X_final[test_mask], y_rate[test_mask]

    # [5] LightGBM 모델 설정
    lgbm_model = LGBMRegressor(
        n_estimators=1000,
        learning_rate=0.05,
        num_leaves=64,  # XGBoost의 max_depth와 유사한 개념 (2^max_depth 보단 작게)
        max_depth=7,
        subsample=0.8,
        colsample_bytree=0.8,
        n_jobs=-1,
        random_state=42,
        importance_type='gain',  # 변수 중요도를 결정 트리 분기 시 이득으로 계산
        verbose=-1  # 불필요한 로그 출력 방지
    )

    # MultiOutput 적용 (이 안에서 모델 4개가 각각 학습됩니다)
    multi_model = MultiOutputRegressor(lgbm_model)
    multi_model.fit(X_train, y_train)

    # [6] 예측 및 복원
    preds_log = multi_model.predict(X_test)
    y_test_original = np.expm1(y_test)
    preds_original = np.expm1(preds_log)

    # 평가
    mae = mean_absolute_error(y_test_original, preds_original)
    r2 = r2_score(y_test_original, preds_original)

    print(f"✅ {disease_type} LightGBM 학습 완료!")
    print(f"📈 전체 평균 R2 Score: {r2:.4f}")
    print(f"📊 전체 평균 MAE: {mae:.4f} (명/1만명)")

    # [7] 모델 저장
    model_filename = f'model_{disease_type.lower()}_lgbm.pkl'
    joblib.dump(multi_model, model_filename)
    print(f"💾 모델 저장 완료: {model_filename}")

    # 중요도 확인
    first_model = multi_model.estimators_[0]
    importances = pd.Series(first_model.feature_importances_, index=X_train.columns).sort_values(ascending=False)
    print(f"💡 중요 변수 TOP 5 (D0 기준):\n{importances.head(5)}")

    return multi_model

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
        train_disease_lgbm(df_clean, 'COLD')

        # 2. 천식(ASTHMA) 4일치 모델 학습 및 저장
        train_disease_lgbm(df_clean, 'ASTHMA')

        print("\n✨ 모든 모델 학습 및 저장 작업이 완료되었습니다!")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == '__main__':
    main()