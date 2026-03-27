import pandas as pd
import oracledb
import platform
import joblib
import numpy as np
from xgboost import XGBRegressor  # XGBoost 추가
from sklearn.multioutput import MultiOutputRegressor  # 다중 출력 지원
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

if platform.system() == 'Windows':
    oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
else:
    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")
db_config = {'user': 'scott', 'password': 'tiger', 'dsn': 'localhost:1521/xe'}


def train_disease_xgb(df, disease_type):
    """
    XGBoost 기반 질병별 4일치 발생률 예측 모델
    """
    print(f"\n🚀 [{disease_type} XGBoost 모델] 학습 시작...")

    # [1] 타겟 추출 및 정렬 (비율 변환 로직 동일)
    target_cnt_cols = [col for col in df.columns if disease_type.upper() in col.upper() and 'CNT_D' in col.upper()]
    target_cnt_cols.sort()

    y_rate = pd.DataFrame()
    for col in target_cnt_cols:
        y_rate[col] = (df[col] / df['POP_TOTAL'].replace(0, np.nan)) * 10000
    y_rate = y_rate.fillna(0)

    # [2] 특징(X) 생성
    all_cnt_cols = [col for col in df.columns if 'CNT_D' in col.upper()]
    X_base = df.drop(columns=['DIST_CODE', 'MEASURE_DATE', 'POP_TOTAL'] + all_cnt_cols)
    X_dist = pd.get_dummies(df['DIST_CODE'], prefix='DIST')
    X = pd.concat([X_base, X_dist], axis=1)

    # [3] 데이터 분할 및 스케일링
    X_train, X_test, y_train, y_test = train_test_split(X, y_rate, test_size=0.2, random_state=42)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # [4] XGBoost 모델 설정 (MultiOutputRegressor 사용)
    # n_estimators: 나무 개수, learning_rate: 학습 속도, max_depth: 나무 깊이
    xgb_base = XGBRegressor(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=6,
        random_state=42,
        n_jobs=-1,
        tree_method='hist'  # 대용량 데이터 학습 가속
    )

    # 4일치 타겟을 위해 래퍼 클래스로 감쌈
    model = MultiOutputRegressor(xgb_base)
    model.fit(X_train_scaled, y_train)

    # [5] 성능 평가
    preds = model.predict(X_test_scaled)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    print(f"\n✅ {disease_type} XGBoost 학습 완료!")
    print(f"📈 전체 평균 R2 Score: {r2:.4f}")
    print(f"📊 전체 평균 MAE: {mae:.4f} (명/1만명)")

    # [6] 중요도 및 저장 (XGBoost는 개별 모델의 중요도를 평균내어 확인)
    # MultiOutputRegressor에서는 estimators_[0] 등 개별 접근이 필요함
    # 여기서는 가장 첫날(D0) 예측 모델의 중요도를 출력해봅니다.
    importances = pd.Series(model.estimators_[0].feature_importances_, index=X.columns).sort_values(ascending=False)
    print(f"💡 [D0 기준] 중요 변수 TOP 5:\n{importances.head(5)}")

    # 저장 파일명 구분
    model_filename = f'model_{disease_type.lower()}_xgb.pkl'
    scaler_filename = f'scaler_{disease_type.lower()}_xgb.pkl'

    joblib.dump(model, model_filename)
    joblib.dump(scaler, scaler_filename)

    print(f"💾 저장 완료: {model_filename}, {scaler_filename}")
    return model

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
        train_disease_xgb(df_clean, 'COLD')

        # 2. 천식(ASTHMA) 4일치 모델 학습 및 저장
        train_disease_xgb(df_clean, 'ASTHMA')

        print("\n✨ 모든 모델 학습 및 저장 작업이 완료되었습니다!")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")


if __name__ == '__main__':
    main()