import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.metrics import r2_score
import joblib
import holidays
import os
import warnings
from db_config import get_conn

warnings.filterwarnings("ignore", category=UserWarning, module='pandas')

def train_st2pr_model(disease_type='COLD', train_end_date='2024-12-31'):
    """
    네이버 검색 지수를 기반으로 가상 환자 발생 비율(Rate)을 추측하는 모델
    """
    conn = get_conn()
    # 검색 지수와 실제 환자 수, 인구수가 모두 포함된 뷰(또는 테이블) 호출
    query = f"SELECT * FROM VW_ST2PR ORDER BY MEASURE_DATE"
    df = pd.read_sql(query, conn)
    conn.close()

    print(f"🚀 [{disease_type}] ST2PR 가상 모델 학습 시작...")

    # 1. 기본 피처 생성
    df['DAY_OF_WEEK'] = pd.to_datetime(df['MEASURE_DATE']).dt.dayofweek.astype('category')
    df['DIST_CODE'] = df['DIST_CODE'].astype('category')
    df['MONTH'] = df['MEASURE_DATE'].dt.month.astype('category')

    search_col = f'{disease_type.upper()}_SEARCH_IDX'
    target_col = 'TARGET_RATE'

    # 2. [가장 중요] 타겟 컬럼을 먼저 생성해야 합니다!
    target_cnt_col = f'{disease_type.upper()}_CNT_D0'
    df[target_col] = (df[target_cnt_col] / df['POP_TOTAL'].replace(0, np.nan)) * 10000
    df[target_col] = df[target_col].fillna(0)  # 결측치 방어

    # 한국 공휴일 객체 생성
    kr_holidays = holidays.KR()

    # 공휴일 피처 생성 (공휴일이면 1, 아니면 0)
    df['IS_HOLIDAY'] = df['MEASURE_DATE'].apply(lambda x: 1 if x in kr_holidays else 0)
    df['IS_SATURDAY'] = (df['MEASURE_DATE'].dt.dayofweek == 5).astype(int)
    df['IS_SUNDAY'] = (df['MEASURE_DATE'].dt.dayofweek == 6).astype(int)

    # 학습 변수에 추가
    features = [
        search_col, 'MONTH', 'DIST_CODE', 'DAY_OF_WEEK',
        'IS_HOLIDAY', 'IS_SATURDAY', 'IS_SUNDAY'
    ]

    # 결측치 제거 (Shift로 인한 것)
    df = df.dropna(subset=features)

    # 4. 데이터 분할 (셔플을 통해 전 기간의 상관관계 학습)
    from sklearn.model_selection import train_test_split

    X = df[features]
    y = df['TARGET_RATE']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,  # 전체의 20%를 테스트용으로
        random_state=42,
        shuffle=True  # [핵심] 셔플 활성화
    )

    # 5. XGBoost 모델 설정
    model = XGBRegressor(
        enable_categorical=True,
        tree_method='hist',
        n_estimators=500,
        learning_rate=0.02,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    # 6. 성능 검증
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)

    # 저장할 경로 설정 (현재 폴더에서 flask 쪽으로 거슬러 올라감)
    save_path = f"../../flask/air/ml/st2pr_{disease_type.lower()}.pkl"
    # 폴더가 없으면 미리 생성 (에러 방지)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    print(f"✅ ST2PR 모델 학습 완료 | R2 Score: {r2:.4f}")
    joblib.dump(model, save_path)
    print(f"💾 모델 저장 완료: {save_path}")

    return model

if __name__ == "__main__":
    train_st2pr_model('COLD')
    train_st2pr_model('ASTHMA')