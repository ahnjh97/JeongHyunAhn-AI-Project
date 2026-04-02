DROP TABLE PRED_PATIENT_RATE_COLD;
DROP TABLE PRED_PATIENT_RATE_ASTHMA;

CREATE TABLE PRED_PATIENT_RATE_COLD (
    measure_date    DATE NOT NULL,
    district_code   CHAR(5) NOT NULL,               -- 자치구 코드
    pred_rate       NUMBER(10, 4) NOT NULL,         -- 예측 환자 비율 (1만명 당)
    pred_cnt        NUMBER,

    CONSTRAINT pk_pred_patient_rate_cold UNIQUE (measure_date, district_code)
);

CREATE TABLE PRED_PATIENT_RATE_ASTHMA (
    measure_date    DATE NOT NULL,
    district_code   CHAR(5) NOT NULL,               -- 자치구 코드
    pred_rate       NUMBER(10, 4) NOT NULL,         -- 예측 환자 비율 (1만명 당)
    pred_cnt        NUMBER,

    CONSTRAINT pk_pred_patient_rate_asthma UNIQUE (measure_date, district_code)
);