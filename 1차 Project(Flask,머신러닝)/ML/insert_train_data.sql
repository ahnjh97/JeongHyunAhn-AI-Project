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
-- [A] 미세먼지 연속 시간(STREAK) 사전 계산 (기준: PM10 >= 151, PM25 >= 76)
WITH STREAK_CALC AS (
    SELECT
        dist_code,
        TRUNC(measure_time) as m_date,
        CASE WHEN pm10 >= 151 THEN
            COUNT(*) OVER (PARTITION BY dist_code, TRUNC(measure_time), (row_num - grp_pm10))
            ELSE 0 END as streak_pm10_raw,
        CASE WHEN pm25 >= 76 THEN
            COUNT(*) OVER (PARTITION BY dist_code, TRUNC(measure_time), (row_num - grp_pm25))
            ELSE 0 END as streak_pm25_raw
    FROM (
        SELECT
            dist_code, measure_time, pm10, pm25,
            ROW_NUMBER() OVER (PARTITION BY dist_code, TRUNC(measure_time) ORDER BY measure_time) as row_num,
            ROW_NUMBER() OVER (PARTITION BY dist_code, TRUNC(measure_time) ORDER BY measure_time) -
            ROW_NUMBER() OVER (PARTITION BY dist_code, TRUNC(measure_time), CASE WHEN pm10 >= 151 THEN 1 ELSE 0 END ORDER BY measure_time) as grp_pm10,
            ROW_NUMBER() OVER (PARTITION BY dist_code, TRUNC(measure_time) ORDER BY measure_time) -
            ROW_NUMBER() OVER (PARTITION BY dist_code, TRUNC(measure_time), CASE WHEN pm25 >= 76 THEN 1 ELSE 0 END ORDER BY measure_time) as grp_pm25
        FROM AIR_QUALITY_HOURLY
    )
),
DAILY_STREAK AS (
    SELECT
        dist_code, m_date,
        MAX(streak_pm10_raw) as pm10_streak,
        MAX(streak_pm25_raw) as pm25_streak
    FROM STREAK_CALC
    GROUP BY dist_code, m_date
)
-- [B] 최종 데이터 병합 및 삽입
SELECT
    V.dist_code, V.m_date,
    -- [D0] 기상 정보
    V.pm10_avg, V.pm10_max, NVL(S.pm10_streak, 0),
    V.pm25_avg, V.pm25_max, NVL(S.pm25_streak, 0),
    V.temp_avg, (V.temp_max - V.temp_min), V.temp_min, V.temp_max,
    (V.temp_avg - LAG(V.temp_avg, 1) OVER (PARTITION BY V.dist_code ORDER BY V.m_date)) as temp_diff_prev_d0,

    -- [D-1] 기상 및 STREAK 과거치
    LAG(V.pm10_avg, 1) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(NVL(S.pm10_streak, 0), 1) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(V.pm25_avg, 1) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(NVL(S.pm25_streak, 0), 1) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(V.temp_min, 1) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),

    -- [D-2]
    LAG(V.pm10_avg, 2) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(NVL(S.pm10_streak, 0), 2) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(V.pm25_avg, 2) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(NVL(S.pm25_streak, 0), 2) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(V.temp_min, 2) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),

    -- [D-3]
    LAG(V.pm10_avg, 3) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(NVL(S.pm10_streak, 0), 3) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(V.pm25_avg, 3) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(NVL(S.pm25_streak, 0), 3) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LAG(V.temp_min, 3) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),

    -- [장기/사회 요인]
    AVG(V.pm10_avg) OVER (PARTITION BY V.dist_code ORDER BY V.m_date ROWS 2 PRECEDING) as pm10_ma_72h,
    AVG(V.pm25_avg) OVER (PARTITION BY V.dist_code ORDER BY V.m_date ROWS 2 PRECEDING) as pm25_ma_72h,
    (TO_CHAR(V.m_date, 'D') - 1) as day_of_week, -- 0:월 ~ 6:일 (Oracle 1:일 ~ 7:토 기준 보정 필요시 확인)

    -- [IS_HOLIDAY 로직]
    CASE
        WHEN TO_CHAR(V.m_date, 'D') IN ('1', '7') THEN 1 -- 토(7), 일(1)
        WHEN TO_CHAR(V.m_date, 'MMDD') IN (
            '0101', -- 신정
            '0301', -- 삼일절
            '0505', -- 어린이날
            '0606', -- 현충일
            '0815', -- 광복절
            '1003', -- 개천절
            '1009', -- 한글날
            '1225'  -- 크리스마스
        ) THEN 1
        ELSE 0
    END as is_holiday,

    EXTRACT(MONTH FROM V.m_date) as std_month,
    V.pop_child_ratio,
    V.pop_old_ratio,
    V.grdp_pc,
    V.pop_total,

    -- [과거 환자 수 추이]
    LAG(V.cold_cnt, 1) OVER (PARTITION BY V.dist_code ORDER BY V.m_date) as cold_prev_d1,
    LAG(V.cold_cnt, 2) OVER (PARTITION BY V.dist_code ORDER BY V.m_date) as cold_prev_d2,
    LAG(V.cold_cnt, 3) OVER (PARTITION BY V.dist_code ORDER BY V.m_date) as cold_prev_d3,
    LAG(V.asthma_cnt, 1) OVER (PARTITION BY V.dist_code ORDER BY V.m_date) as asthma_prev_d1,
    LAG(V.asthma_cnt, 2) OVER (PARTITION BY V.dist_code ORDER BY V.m_date) as asthma_prev_d2,
    LAG(V.asthma_cnt, 3) OVER (PARTITION BY V.dist_code ORDER BY V.m_date) as asthma_prev_d3,

    -- [Y 타겟]
    V.cold_cnt,
    LEAD(V.cold_cnt, 1) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LEAD(V.cold_cnt, 2) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LEAD(V.cold_cnt, 3) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    V.asthma_cnt,
    LEAD(V.asthma_cnt, 1) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LEAD(V.asthma_cnt, 2) OVER (PARTITION BY V.dist_code ORDER BY V.m_date),
    LEAD(V.asthma_cnt, 3) OVER (PARTITION BY V.dist_code ORDER BY V.m_date)

FROM V_TRAIN V
LEFT JOIN DAILY_STREAK S ON V.dist_code = S.dist_code AND V.m_date = S.m_date;