import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from db_config import get_conn


def check_log_correlation():
    # 1. 데이터 로드
    conn = get_conn()
    query = "SELECT * FROM VW_ST2PR ORDER BY MEASURE_DATE"
    df = pd.read_sql(query, conn)
    conn.close()

    # 2. 인구 1만 명당 발생 비율 계산
    df['COLD_RATE'] = (df['COLD_CNT_D0'] / df['POP_TOTAL']) * 10000
    df['ASTHMA_RATE'] = (df['ASTHMA_CNT_D0'] / df['POP_TOTAL']) * 10000

    # 3. 로그 변환 (log1p 사용: 데이터가 0인 경우 대비)
    # 상관계수를 구하기 전에 타겟 변수를 정규화합니다.
    df['LOG_COLD_RATE'] = np.log1p(df['COLD_RATE'])
    df['LOG_ASTHMA_RATE'] = np.log1p(df['ASTHMA_RATE'])

    # 4. 시차(Lag) 데이터 생성 (검색 지수)
    df['ASTHMA_IDX_LAG1'] = df.groupby('DIST_CODE')['ASTHMA_SEARCH_IDX'].shift(1)
    df['COLD_IDX_LAG1'] = df.groupby('DIST_CODE')['COLD_SEARCH_IDX'].shift(1)

    # 5. 결측치 제거
    df = df.dropna()

    # 6. 상관관계 분석 대상 설정
    target_cols = [
        'LOG_COLD_RATE', 'LOG_ASTHMA_RATE',
        'ASTHMA_SEARCH_IDX', 'ASTHMA_IDX_LAG1',
        'COLD_SEARCH_IDX', 'COLD_IDX_LAG1'
    ]

    corr_matrix = df[target_cols].corr()

    # 7. 결과 출력
    print("--- 📈 [로그 변환 + 1만명당 비율] 상관계수 결과 ---")
    # 로그 변환된 발생률과 검색 지수들 간의 관계 확인
    print(corr_matrix[['LOG_COLD_RATE', 'LOG_ASTHMA_RATE']])

    # 8. 히트맵 시각화
    plt.figure(figsize=(10, 8))
    sns.heatmap(corr_matrix, annot=True, cmap='YlGnBu', fmt=".2f")
    plt.title("Log-Transformed Correlation: Disease Rate vs Search Index")
    plt.show()


if __name__ == "__main__":
    check_log_correlation()