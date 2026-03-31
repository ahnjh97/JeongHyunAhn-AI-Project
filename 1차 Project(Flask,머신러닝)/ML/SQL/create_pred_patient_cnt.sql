DROP TABLE PRED_PATIENT_CNT;

CREATE TABLE PRED_PATIENT_CNT (
    measure_date    DATE NOT NULL,
    district_code   INT NOT NULL,               -- 자치구 코드
    pred_count      INT NOT NULL,               -- 예측 환자 수 (Rate * District_Pop / 10000)

    CONSTRAINT pk_pred_patient_cnt UNIQUE (measure_date, district_code)
);