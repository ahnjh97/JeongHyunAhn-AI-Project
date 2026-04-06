import pandas as pd
import numpy as np
import joblib
import holidays
import os
from xgboost import XGBRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from db_config import get_conn
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

def train_disease_xgb(df_feat, disease_type):
    """
    환자 수(CNT) 데이터를 1만 명당 환자 비율(RATIO)로 통일하여 학습
    - 타겟(D0~D3) 및 과거 데이터(PREV_D1~3) 모두 비율 변환
    """
    df_feat = df_feat.copy()
    kr_holidays = holidays.KR()

    cat_features = ['DIST_CODE', 'STD_MONTH']
    for col in cat_features:
        if col in df_feat.columns:
            # 문자열이나 단순 숫자를 'category' 타입으로 변경
            df_feat[col] = df_feat[col].astype('category')

    # ---------------------------------------------------------
    # 1. 과거 데이터(PREV) 변환: 수(CNT) -> 1만 명당 비율(RATIO)
    # ---------------------------------------------------------
    # 감기(COLD)와 천식(ASTHMA) 두 질병 모두의 과거 데이터를 비율로 변환합니다.
    for disease in ['COLD', 'ASTHMA']:
        for i in range(1, 4):  # D1, D2, D3
            prev_cnt_col = f'{disease}_PREV_D{i}'
            if prev_cnt_col in df_feat.columns:
                # 기존 CNT 컬럼을 RATIO로 업데이트 (1만명당 비율)
                df_feat[prev_cnt_col] = (df_feat[prev_cnt_col] / df_feat['POP_TOTAL']) * 10000

    # ---------------------------------------------------------
    # 2. 타겟 생성: 오늘~미래 환자 수 -> 1만 명당 비율 변환
    # ---------------------------------------------------------
    for i in range(4):
        cnt_col = f'{disease_type}_CNT_D0' if i == 0 else f'{disease_type}_CNT_D_PLUS_{i}'
        ratio_col = f'{disease_type}_RATIO_D{i}'
        df_feat[ratio_col] = (df_feat[cnt_col] / df_feat['POP_TOTAL']) * 10000

    # ---------------------------------------------------------
    # 3. 미래 휴일 피처 생성 (D1~D3)
    # ---------------------------------------------------------
    for i in range(1, 4):
        target_date = df_feat['MEASURE_DATE'] + pd.Timedelta(days=i)
        prev_to_target = target_date - pd.Timedelta(days=1)

        df_feat[f'IS_HOLIDAY_D{i}'] = ((target_date.dt.weekday == 6) | (target_date.isin(kr_holidays))).astype(int)
        df_feat[f'AFTER_HOLIDAY_D{i}'] = ((prev_to_target.dt.weekday == 6) | (prev_to_target.isin(kr_holidays))).astype(
            int)

    # ---------------------------------------------------------
    # 4. 데이터셋 분리 (X, y 설정)
    # ---------------------------------------------------------
    target_cols = [f'{disease_type}_RATIO_D{i}' for i in range(4)]

    # 다른 질환의 과거 데이터는 학습 피처로 유지하되(비율로 변환됨), 타겟 컬럼들은 제거
    other_disease = 'ASTHMA' if disease_type == 'COLD' else 'COLD'
    other_disease_cols = [c for c in df_feat.columns if c.startswith(f'{other_disease}_')]
    all_cnt_cols = [c for c in df_feat.columns if '_CNT_' in c]
    all_ratio_cols = [c for c in df_feat.columns if '_RATIO_D' in c]

    # 리크(Leak) 방지를 위해 타겟과 직접 연결된 CNT/RATIO 컬럼들 모두 제거
    drop_cols = ['MEASURE_DATE', 'POP_TOTAL', 'DAY_OF_WEEK'] + \
                all_cnt_cols + all_ratio_cols + other_disease_cols

    X = df_feat.drop(columns=drop_cols)
    y = df_feat[target_cols]

    # [X 피처 리스트 출력]
    features = list(X.columns)
    # print(f"\n🔎 [{disease_type}] 학습 피처 ({len(features)}개 / PREV 데이터 비율 변환 완료):")
    # for i, f in enumerate(features):
    #     print(f"{f:<25}", end='\t' if (i + 1) % 3 != 0 else '\n')
    # print("\n" + "=" * 80)

    # Train/Test 분할
    split_idx = int(len(df_feat) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    # ---------------------------------------------------------
    # 5. 샘플 가중치 및 모델 학습
    # ---------------------------------------------------------
    extreme_weather_mask = (
            (X_train['PM10_MA_72H'] > 80) |
            (X_train['PM25_MA_72H'] > 35) |
            (X_train['TEMP_DIFF_PREV_D0'] < 0)
    )
    sample_weights = np.where(extreme_weather_mask, 5.0, 1.0)

    xgb_model = XGBRegressor(
        n_estimators=2000,
        learning_rate=0.02,
        max_depth=5,  # ★ 깊이를 확 낮춰서 복잡한 요일 패턴 암기 방지
        subsample=0.7,
        colsample_bytree=0.2,  # ★ 요일 변수가 선택될 확률을 확 줄임
        min_child_weight=25,  # ★ 더 많은 데이터가 모여야 분기하도록 규제
        reg_lambda=20.0,  # ★ L2 규제를 강화하여 변수 가중치를 골고루 분산
        random_state=42,
        tree_method='hist',
        enable_categorical=True,
        objective='count:poisson'
    )

    multi_model = MultiOutputRegressor(xgb_model)
    print(f"🔥 [{disease_type}] 비율 기반 XGBoost 학습 시작...")
    multi_model.fit(X_train, y_train, sample_weight=sample_weights)

    # 결과 평가 및 저장
    y_pred = multi_model.predict(X_test)
    print(f"✅ {disease_type} 학습 완료! R2: {r2_score(y_test, y_pred):.4f}")

    model_path = f"../../flask/air/ml/model_{disease_type.lower()}_seoul.pkl"
    joblib.dump(multi_model, model_path)

    # 중요도 출력
    avg_imp = np.mean([est.feature_importances_ for est in multi_model.estimators_], axis=0)
    print(pd.Series(avg_imp, index=features).sort_values(ascending=False).head(15))

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

        # print(f"🧹 전처리 완료: {len(df)}행 -> {len(df_clean)}행")

        # 1. 감기(COLD) 4일치 모델 학습 및 저장
        train_disease_xgb(df_clean, 'COLD')

        # 2. 천식(ASTHMA) 4일치 모델 학습 및 저장
        train_disease_xgb(df_clean, 'ASTHMA')

        print("\n✨ 모든 모델 학습 및 저장 작업이 완료되었습니다!")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")


if __name__ == '__main__':
    main()