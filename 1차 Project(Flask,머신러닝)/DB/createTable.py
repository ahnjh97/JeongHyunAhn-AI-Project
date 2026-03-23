import oracledb
import platform

# platform을 체크해서 경로를 유연하게 설정
if platform.system() == 'Windows':
    oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
else:
    # 리눅스(WSL) 경로 설정
    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")

db_config = {
    'user': 'scott',
    'password': 'tiger',
    'dsn': 'localhost:1521/xe',
}

def execute_sql_file(filename):
    connection = None
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            full_sql = f.read()

        # 세미콜론(;)을 기준으로 문장들을 나눔
        sql_commands = [cmd.strip() for cmd in full_sql.split(';') if cmd.strip()]

        # DB 연결
        connection = oracledb.connect(**db_config)
        cursor = connection.cursor()

        print(f"총 {len(sql_commands)}개의 SQL 문장을 발견했습니다. 실행 시작.")

        # 루프를 돌며 한 문장씩 실행함
        for i, command in enumerate(sql_commands, 1):
            clean_command = command.strip()

            # 내용이 없는 빈 줄은 건너뜁니다
            if not clean_command:
                continue

            try:
                cursor.execute(clean_command)
                print(f"[{i}/{len(sql_commands)}] 실행 성공")
            except oracledb.DatabaseError as e:
                error, = e.args

                # ORA-00942: 테이블이 존재하지 않음 (DROP 시 무시 가능)
                if error.code == 942 and "DROP" in command.upper():
                    print(f"이미 삭제되었거나 테이블이 없어 건너뜁니다.")
                # ORA-00955: 이미 존재하는 객체 이름 (CREATE 시 무시 가능)
                elif error.code == 955 and "CREATE" in clean_command.upper():
                    print(f"[{i}/{len(sql_commands)}] 이미 존재하는 테이블입니다.")
                else:
                    print(f"[{i}/{len(sql_commands)}] 실행 실패: {error.message}")

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
    execute_sql_file("create_table.sql")