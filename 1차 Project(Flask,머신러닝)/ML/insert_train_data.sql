-- 1. 통합 뷰 생성 (7개 테이블 Join)
CREATE OR REPLACE VIEW V_TRAIN AS
SELECT
    -- [기본 정보]
    A.dist_code,
    TRUNC(A.measure_time) AS m_date,
    EXTRACT(YEAR FROM A.measure_time) AS m_year,
    TO_CHAR(A.measure_time, 'Q') AS m_qt,

    -- [대기 및 기상] (시간 데이터를 일 평균/최대로 요약)
    AVG(A.pm10) AS pm10_avg,
    MAX(A.pm10) AS pm10_max,
    AVG(A.pm25) AS pm25_avg,
    MAX(A.pm25) AS pm25_max,
    AVG(A.temp) AS temp_avg,
    MIN(A.temp) AS temp_min,
    MAX(A.temp) AS temp_max,

    -- [환자 수]
    NVL(P.cold_cnt, 0) AS cold_cnt,
    NVL(P.asthma_cnt, 0) AS asthma_cnt,

    -- [인구 데이터 가져오기: 인구 통계 테이블 활용]
    (SELECT SUM(pop_cnt)
     FROM AGE_STATS_QUARTERLY
     WHERE std_year = EXTRACT(YEAR FROM A.measure_time)
       AND std_qt = TO_CHAR(A.measure_time, 'Q')
       AND dist_code = A.dist_code) AS pop_total,

    -- [인구 통계 계산: 아동(0-9세) 및 노인(65세+) 비율]
    (SELECT ROUND(SUM(CASE WHEN age_grp IN ('0-9세') THEN pop_cnt ELSE 0 END) / SUM(pop_cnt) * 100, 2)
     FROM AGE_STATS_QUARTERLY
     WHERE std_year = EXTRACT(YEAR FROM A.measure_time)
       AND std_qt = TO_CHAR(A.measure_time, 'Q')
       AND dist_code = A.dist_code) AS pop_child_ratio,

    (SELECT ROUND(SUM(CASE WHEN age_grp IN ('60-69세', '70-79세', '80-89세', '90-99세', '100세 이상') THEN pop_cnt ELSE 0 END) / SUM(pop_cnt) * 100, 2)
     FROM AGE_STATS_QUARTERLY
     WHERE std_year = EXTRACT(YEAR FROM A.measure_time)
       AND std_qt = TO_CHAR(A.measure_time, 'Q')
       AND dist_code = A.dist_code) AS pop_old_ratio,

    -- [경제 지표]
    NVL(G.grdp_pc,
        CASE
            WHEN EXTRACT(YEAR FROM A.measure_time) < 2015 THEN (SELECT grdp_pc FROM GRDP_PER_CAPITA WHERE std_year = 2015 AND dist_code = A.dist_code)
            WHEN EXTRACT(YEAR FROM A.measure_time) > 2022 THEN (SELECT grdp_pc FROM GRDP_PER_CAPITA WHERE std_year = 2022 AND dist_code = A.dist_code)
        END
    ) AS grdp_pc

FROM AIR_QUALITY_HOURLY A
LEFT JOIN PATIENT_CNT_DAILY P ON TRUNC(A.measure_time) = P.measure_date AND A.dist_code = P.dist_code
LEFT JOIN GRDP_PER_CAPITA G ON EXTRACT(YEAR FROM A.measure_time) = G.std_year AND A.dist_code = G.dist_code
GROUP BY A.dist_code, TRUNC(A.measure_time), EXTRACT(YEAR FROM A.measure_time), TO_CHAR(A.measure_time, 'Q'), G.grdp_pc, P.cold_cnt, P.asthma_cnt;


-- 2. TRAIN_SET 데이터 적재
TRUNCATE TABLE TRAIN_SET;

INSERT INTO TRAIN_SET
SELECT
    dist_code, m_date,
    -- [D0]
    pm10_avg, pm10_max, 0, -- pm10_streak (추후 연산 시 교체)
    pm25_avg, pm25_max, 0, -- pm25_streak
    temp_avg, (temp_max - temp_min), temp_min, temp_max,
    (temp_avg - LAG(temp_avg, 1) OVER (PARTITION BY dist_code ORDER BY m_date)),

    -- [D-1]
    LAG(pm10_avg, 1) OVER (PARTITION BY dist_code ORDER BY m_date), 0,
    LAG(pm25_avg, 1) OVER (PARTITION BY dist_code ORDER BY m_date), 0,
    LAG(temp_min, 1) OVER (PARTITION BY dist_code ORDER BY m_date),

    -- [D-2]
    LAG(pm10_avg, 2) OVER (PARTITION BY dist_code ORDER BY m_date), 0,
    LAG(pm25_avg, 2) OVER (PARTITION BY dist_code ORDER BY m_date), 0,
    LAG(temp_min, 2) OVER (PARTITION BY dist_code ORDER BY m_date),

    -- [D-3]
    LAG(pm10_avg, 3) OVER (PARTITION BY dist_code ORDER BY m_date), 0,
    LAG(pm25_avg, 3) OVER (PARTITION BY dist_code ORDER BY m_date), 0,
    LAG(temp_min, 3) OVER (PARTITION BY dist_code ORDER BY m_date),

    -- [장기/사회]
    AVG(pm10_avg) OVER (PARTITION BY dist_code ORDER BY m_date ROWS 2 PRECEDING), -- ma_72h
    AVG(pm25_avg) OVER (PARTITION BY dist_code ORDER BY m_date ROWS 2 PRECEDING), -- ma_72h
    (TO_CHAR(m_date, 'D') - 1), -- day_of_week
    0, -- is_holiday
    EXTRACT(MONTH FROM m_date), -- std_month
    pop_child_ratio,            -- 어린이 비율
    pop_old_ratio,              -- 노인 비율
    grdp_pc,                    -- 1인당 지역내총생산
    pop_total,                  -- 인구

    -- [Y 타겟]
    cold_cnt,
    LEAD(cold_cnt, 1) OVER (PARTITION BY dist_code ORDER BY m_date),
    LEAD(cold_cnt, 2) OVER (PARTITION BY dist_code ORDER BY m_date),
    LEAD(cold_cnt, 3) OVER (PARTITION BY dist_code ORDER BY m_date),
    asthma_cnt,
    LEAD(asthma_cnt, 1) OVER (PARTITION BY dist_code ORDER BY m_date),
    LEAD(asthma_cnt, 2) OVER (PARTITION BY dist_code ORDER BY m_date),
    LEAD(asthma_cnt, 3) OVER (PARTITION BY dist_code ORDER BY m_date)

FROM V_TRAIN;