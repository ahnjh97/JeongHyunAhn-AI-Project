import pandas as pd
import numpy as np
import joblib
from xgboost import XGBRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from db_config import get_conn

def train_by_district(df, dist, disease_type, run_cv=False):
    """
    XGBoost를 이용한 질병별 4일치(D0~D3) 발생률 예측 모델
    """
    print(f"\n🔥 [{dist}구 {disease_type} 발생률 XGBoost 모델] 학습 시작 (Target: 1만명당 환자수)...")

    df = df[df['DIST_CODE'] == dist].copy()

    # [1] 타겟 추출 (D0 ~ D+3)
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

    # [3] 특징(X) 생성 및 전처리
    all_target_cols = [col for col in df.columns if 'CNT_D' in col.upper()]
    all_prev_cols = ["COLD_PREV_D1", "COLD_PREV_D2", "COLD_PREV_D3",
                     "ASTHMA_PREV_D1", "ASTHMA_PREV_D2", "ASTHMA_PREV_D3"]

    # 타 질병 과거치는 모델 혼선을 위해 제거
    other_disease_prev_cols = [col for col in all_prev_cols if disease_type.upper() not in col]

    drop_cols = (['MEASURE_DATE', 'POP_TOTAL', 'DIST_CODE'] + all_target_cols + other_disease_prev_cols)
    X_final = df.drop(columns=drop_cols).copy()

    # 범주형으로 설정
    X_final['STD_MONTH'] = X_final['STD_MONTH'].astype('category')
    X_final['DAY_OF_WEEK'] = X_final['DAY_OF_WEEK'].astype('category')

    # [4] 데이터 분할 (2022년을 테스트셋으로 활용)
    train_mask = (df['MEASURE_DATE'] >= '2015-01-01') & (df['MEASURE_DATE'] <= '2021-12-31')
    test_mask = (df['MEASURE_DATE'] >= '2022-01-01') & (df['MEASURE_DATE'] <= '2022-12-31')

    X_train, y_train = X_final[train_mask], y_rate[train_mask]
    X_test, y_test = X_final[test_mask], y_rate[test_mask]

    # [5] XGBoost 모델 설정 (범주형 활성화)
    xgb_model = XGBRegressor(
        n_estimators=1000,  # 데이터 양에 맞춰 트리 개수도 약간 조절
        learning_rate=0.01,
        max_depth=4,
        gamma=0.2,
        min_child_weight=10,  # 트리 분기 시 필요한 최소 샘플 수 (작은 데이터셋에 적합)
        tree_method='hist',
        enable_categorical=True,
        subsample=0.7,
        colsample_bytree=0.7,
        n_jobs=-1,
        random_state=42
    )

    # [6] 시계열 교차 검증 (TimeSeriesSplit) 실행
    # n_splits=5 는 데이터를 5개 구간으로 쪼개서 점진적으로 학습/검증을 반복함
    if run_cv:
        tscv = TimeSeriesSplit(n_splits=5)
        cv_scores = []

        print(f"🔄 {disease_type} 시계열 교차 검증(TimeSeriesSplit) 진행 중...")

        # X_train 내부에서 인덱스를 시계열 순서대로 쪼갬
        for i, (tr_idx, val_idx) in enumerate(tscv.split(X_train)):
            X_cv_train, X_cv_val = X_train.iloc[tr_idx], X_train.iloc[val_idx]
            y_cv_train, y_cv_val = y_train.iloc[tr_idx], y_train.iloc[val_idx]

            cv_multi_model = MultiOutputRegressor(xgb_model)
            cv_multi_model.fit(X_cv_train, y_cv_train)

            cv_preds = cv_multi_model.predict(X_cv_val)
            # 로그 복원 후 R2 계산
            cv_r2 = r2_score(np.expm1(y_cv_val), np.expm1(cv_preds))
            cv_scores.append(cv_r2)
            print(f"   📍 Fold {i + 1} R2 Score: {cv_r2:.4f}")

        avg_cv_r2 = np.mean(cv_scores)
        print(f"📊 평균 교차 검증 R2 Score: {avg_cv_r2:.4f}")

    # MultiOutput 래퍼 적용
    multi_model = MultiOutputRegressor(xgb_model)
    multi_model.fit(X_train, y_train)  # 스케일링 안 한 원본 투입

    # [7] 예측 및 복원
    preds_log = multi_model.predict(X_test)
    y_test_original = np.expm1(y_test)
    preds_original = np.expm1(preds_log)

    # 평가 지표
    mae = mean_absolute_error(y_test_original, preds_original)
    r2 = r2_score(y_test_original, preds_original)

    print(f"✅ {disease_type} XGBoost 학습 완료!")
    print(f"📈 전체 평균 R2 Score: {r2:.4f}")
    print(f"📊 전체 평균 MAE: {mae:.4f} (명/1만명)")

    # 중요도 시각화용 데이터
    first_model = multi_model.estimators_[0]
    importances = pd.Series(first_model.feature_importances_, index=X_train.columns).sort_values(ascending=False)
    print(f"💡 중요 변수 TOP 5:\n{importances.head(5)}")

    return multi_model

def main():
    try:
        # 데이터 로드
        conn = get_conn()
        print("🔗 DB 연결 성공!")
        df = pd.read_sql("SELECT * FROM TRAIN_SET ORDER BY measure_date, dist_code", conn)
        conn.close()

        # 결측치 제거
        df_clean = df.dropna()
        if len(df_clean) == 0:
            print("❌ 에러: 정제 후 데이터가 0행입니다. 결측치를 확인하세요.")
            return

        print(f"🧹 전처리 완료: {len(df)}행 -> {len(df_clean)}행")
        dist_list = df['DIST_CODE'].unique()

        # 구별 모델을 담을 빈 딕셔너리 생성
        cold_model_dict = {}
        asthma_model_dict = {}

        # 자치구별 4일치 모델 학습 및 저장
        for dist in dist_list:
            cold_model_dict[dist] = train_by_district(df_clean, dist, 'COLD')
            asthma_model_dict[dist] = train_by_district(df_clean, dist, 'ASTHMA')

        joblib.dump(cold_model_dict, 'model_cold_all_districts.pkl')
        joblib.dump(asthma_model_dict, 'model_asthma_all_districts.pkl')
        print("\n✨ [통합 완료] 모든 자치구 모델이 딕셔너리 형태로 저장되었습니다.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")


if __name__ == '__main__':
    main()