import db_config
import oracledb

def execute_sql_file(filename):
    connection = None
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            full_sql = f.read()

        # 세미콜론(;)을 기준으로 문장들을 나눔
        sql_commands = [cmd.strip() for cmd in full_sql.split(';') if cmd.strip()]

        # DB 연결
        connection = db_config.get_conn()
        cursor = connection.cursor()

        print()
        print(f"총 {len(sql_commands)}개의 SQL 문장을 발견했습니다. 실행 시작.")

        # 루프를 돌며 한 문장씩 실행함
        for i, command in enumerate(sql_commands, 1):
            try:
                cursor.execute(command)
                print(f"[{i}/{len(sql_commands)}] 실행 성공")
            except oracledb.DatabaseError as e:
                error, = e.args

                # ORA-00942: 테이블이 존재하지 않음 (DROP 시 무시 가능)
                if error.code == 942 and "DROP" in command.upper():
                    print(f"이미 삭제되었거나 테이블이 없어 건너뜁니다.")
                # ORA-00955: 이미 존재하는 객체 이름 (CREATE 시 무시 가능)
                elif error.code == 955 and "CREATE" in command.upper():
                    print(f"[{i}/{len(sql_commands)}] 이미 존재하는 테이블입니다.")
                else:
                    print(f"[{i}/{len(sql_commands)}] 실행 실패: {error.message}")
                    connection.rollback()
                    return  # 실패 시 중단

        connection.commit()
        print(f"{filename} 파일의 모든 SQL 실행 완료.")

    except oracledb.DatabaseError as e:
        error, =e.args
        print(f"Oracle 에러: {error.message}")
    except FileNotFoundError:
        print(f"파일을 찾을 수 없음: {filename}")
    finally:
        if connection:
            connection.close()

if __name__ == '__main__':
    # # 학습용 테이블 생성
    # execute_sql_file("SQL/create_train_table.sql")
    #
    # # 학습용 데이터 삽입
    # execute_sql_file("SQL/insert_train_data.sql")

    # # 검색 트렌드 테이블 생성
    # execute_sql_file("SQL/create_search_trend_table.sql")

    # # 검색 트렌드 -> 환자 수 VIEW 생성
    # execute_sql_file("SQL/create_st2pr_view.sql")

    # 실시간 서비스용 예측 환자 수 테이블 생성
    execute_sql_file("SQL/create_pred_patient_cnt.sql")