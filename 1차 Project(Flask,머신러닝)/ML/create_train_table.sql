DROP TABLE TRAIN_SET;

CREATE TABLE TRAIN_SET (
    dist_code           CHAR(5),        -- 자치구 코드
    measure_date        DATE,           -- 측정 날짜 및 시간
    
    -- [D-Day]
    pm10_avg_d0         NUMBER(10, 1),  -- 미세먼지 농도 평균
    pm10_max_d0         NUMBER(10, 1),  -- 미세먼지 농도 최대치
    pm10_streak_d0      NUMBER(2),      -- 매우 나쁨 이상 최대 연속 시간

    pm25_avg_d0         NUMBER(10, 1),  -- 초미세먼지 농도 평균
    pm25_max_d0         NUMBER(10, 1),  -- 초미세먼지 농도 최대치
    pm25_streak_d0      NUMBER(2),      -- 매우 나쁨 이상 최대 연속 시간

    temp_avg_d0         NUMBER(10, 1),  -- 평균 기온
    temp_diff_d0        NUMBER(10, 1),  -- 일교차
    temp_min_d0         NUMBER(10, 1),  -- 최저 기온
    temp_max_d0         NUMBER(10, 1),  -- 최대 기온
    temp_diff_prev_d0   NUMBER(10, 1),  -- 전날 대비 기온차

    -- [D-1]
    pm10_avg_d1         NUMBER(10, 1),  -- 미세먼지 농도 평균
    pm10_streak_d1      NUMBER(2),      -- 매우 나쁨 이상 최대 연속 시간
    pm25_avg_d1         NUMBER(10, 1),  -- 초미세먼지 농도 평균
    pm25_streak_d1      NUMBER(2),      -- 매우 나쁨 이상 최대 연속 시간
    temp_min_d1         NUMBER(10, 1),  -- 최저 기온

    -- [D-2]
    pm10_avg_d2         NUMBER(10, 1),  -- 미세먼지 농도 평균
    pm10_streak_d2      NUMBER(2),      -- 매우 나쁨 이상 최대 연속 시간
    pm25_avg_d2         NUMBER(10, 1),  -- 초미세먼지 농도 평균
    pm25_streak_d2      NUMBER(2),      -- 매우 나쁨 이상 최대 연속 시간
    temp_min_d2         NUMBER(10, 1),  -- 최저 기온

    -- [D-3]
    pm10_avg_d3         NUMBER(10, 1),  -- 미세먼지 농도 평균
    pm10_streak_d3      NUMBER(2),      -- 매우 나쁨 이상 최대 연속 시간
    pm25_avg_d3         NUMBER(10, 1),  -- 초미세먼지 농도 평균
    pm25_streak_d3      NUMBER(2),      -- 매우 나쁨 이상 최대 연속 시간
    temp_min_d3         NUMBER(10, 1),  -- 최저 기온

    -- [장기 흐름 및 사회적 요인]
    pm10_ma_72h         NUMBER(10, 1),  -- 미세먼지 72시간 이동평균
    pm25_ma_72h         NUMBER(10, 1),  -- 초미세먼지 72시간 이동평균
    day_of_week         NUMBER(1),      -- 요일(0:월 ~ 6:일)
    is_holiday          NUMBER(1),      -- 공휴일 여부 (0, 1)
    std_month           NUMBER(2),      -- 월 (1~12): 계절성 파악용
    pop_child_ratio     NUMBER(5, 2),   -- 아동 비율 (%)
    pop_old_ratio       NUMBER(5, 2),   -- 노인 비율 (%)
    grdp_pc             NUMBER,         -- 1인당 GRDP
    pop_total           NUMBER,         -- 인구

    -- [Y 타겟: 오늘~3일 후 환자 수]
    cold_cnt_d0         NUMBER,         -- 당일 감기 환자
    cold_cnt_d_plus_1   NUMBER,         -- 1일 후 감기 환자
    cold_cnt_d_plus_2   NUMBER,         -- 2일 후 감기 환자
    cold_cnt_d_plus_3   NUMBER,         -- 3일 후 감기 환자
    asthma_cnt_d0       NUMBER,         -- 당일 천식 환자
    asthma_cnt_d_plus_1 NUMBER,         -- 1일 후 천식 환자
    asthma_cnt_d_plus_2 NUMBER,         -- 2일 후 천식 환자
    asthma_cnt_d_plus_3 NUMBER,         -- 3일 후 천식 환자
    
    CONSTRAINT pk_train_set PRIMARY KEY (dist_code, measure_date)
);