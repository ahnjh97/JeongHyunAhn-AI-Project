DROP TABLE SEARCH_TREND_COLD;

-- 1. 감기 검색 트렌드 테이블 (감기, 목감기, 코감기 통합 지수)
CREATE TABLE SEARCH_TREND_COLD (
    MEASURE_DATE    DATE NOT NULL,          -- 날짜 (PK)
    SEARCH_INDEX    NUMBER(10, 5),          -- 네이버 API 검색 지수 (0~100 사이 실수)
    CONSTRAINT PK_SEARCH_TREND_COLD PRIMARY KEY (MEASURE_DATE)
);

-- 2. 천식 검색 트렌드 테이블 (천식, 벤토린, 네블라이저 통합 지수)
CREATE TABLE SEARCH_TREND_ASTHMA (
    MEASURE_DATE    DATE NOT NULL,          -- 날짜 (PK)
    SEARCH_INDEX    NUMBER(10, 5),          -- 네이버 API 검색 지수 (0~100 사이 실수)
    CONSTRAINT PK_SEARCH_TREND_ASTHMA PRIMARY KEY (MEASURE_DATE)
);