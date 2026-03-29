import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import db_config
import os

def get_data():
    """DB에서 분석용 데이터를 가져오는 함수"""
    conn = db_config.get_conn()
    query = """
            SELECT * FROM TRAIN_SET
            WHERE measure_date >= TO_DATE('2015-01-01', 'YYYY-MM-DD')
              AND measure_date <= TO_DATE('2021-12-31', 'YYYY-MM-DD')
            ORDER BY measure_date, dist_code
            """
    df = pd.read_sql(query, conn)
    conn.close()
    df.columns = [col.lower() for col in df.columns]
    return df


def analyze_district(df, dist_name, disease_type):
    """특정 데이터셋(전체 or 특정구)의 상관계수 계산"""
    targets = [f'{disease_type}_cnt_d0', f'{disease_type}_cnt_d_plus_1',
               f'{disease_type}_cnt_d_plus_2', f'{disease_type}_cnt_d_plus_3']

    features = [
        'pm25_avg_d0', 'pm25_max_d0', 'pm25_streak_d0', 'pm25_ma_72h',
        'pm10_avg_d0', 'pm10_streak_d0', 'pm10_ma_72h',
        'temp_avg_d0', 'temp_diff_d0', 'temp_min_d0',
        'is_holiday', 'std_month',
        f'{disease_type}_prev_d1', f'{disease_type}_prev_d2', f'{disease_type}_prev_d3'
    ]

    # 상관계수 계산
    corr_matrix = df[targets + features].corr()
    # 피처(행) x 타겟(열) 형태로 추출
    target_corr = corr_matrix.loc[features, targets].copy()

    # 구분용 컬럼 추가
    target_corr['dist_name'] = dist_name
    return target_corr

if __name__ == "__main__":
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False

    save_dir = "correlation_results"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    df = get_data()

    for disease in ['cold', 'asthma']:
        print(f"\n🚀 {disease.upper()} 통합 분석 및 파일 생성 중...")

        # 결과를 담을 리스트
        combined_results = []

        # 1. 서울시 전체 데이터 추가
        total_corr = analyze_district(df, "SEOUL_TOTAL", disease)
        combined_results.append(total_corr)

        # 2. 25개 자치구별 데이터 추가
        dist_codes = sorted(df['dist_code'].unique())
        for code in dist_codes:
            dist_df = df[df['dist_code'] == code]
            if len(dist_df) > 100:
                dist_corr = analyze_district(dist_df, f"DIST_{code}", disease)
                combined_results.append(dist_corr)

        # 3. 모든 결과 하나로 합치기
        final_df = pd.concat(combined_results)

        # 4. CSV 저장 (인덱스인 피처명이 포함되도록 저장)
        csv_path = os.path.join(save_dir, f"correlation_{disease}_all_districts.csv")
        final_df.to_csv(csv_path)

        print(f"✅ {disease.upper()} 통합 CSV 생성 완료: {csv_path}")