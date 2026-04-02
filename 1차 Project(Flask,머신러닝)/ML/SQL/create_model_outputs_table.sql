DROP TABLE MODEL_OUTPUTS;

CREATE TABLE MODEL_OUTPUTS (
    dist_code       CHAR(5) NOT NULL,
    disease_type    VARCHAR2 (40) NOT NULL, -- 감기 / 천식

    pred_date       NUMBER NOT NULL,        -- 오늘: 0, 내일: 1, 모레: 2, 3일 후: 3
    dist_name       VARCHAR2 (40) NOT NULL,
    pred_rate       NUMBER(10, 4) NOT NULL, -- 예측 환자 비율 (1만명당)
    pred_cnt        NUMBER NOT NULL,        -- 예측 환자 수
    created_at      DATE DEFAULT SYSDATE,   -- 데이터 입력 시점 기록용

    CONSTRAINT pk_model_outputs UNIQUE (pred_date, dist_code, disease_type)
);