import platform
import os
import oracledb

# platform을 체크해서 경로를 유연하게 설정
if platform.system() == 'Windows':
    oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
else:
    # 리눅스(WSL) 경로 설정
    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")

BASE_DIR = os.path.dirname(__file__)
print("BASE_DIR:", BASE_DIR)

#Oracle 11g 설정
SQLALCHEMY_DATABASE_URI = "oracle+oracledb://scott:tiger@localhost:1521/xe"
print("SQLALCHEMY_DATABASE_URI:", SQLALCHEMY_DATABASE_URI)

SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = "dev"