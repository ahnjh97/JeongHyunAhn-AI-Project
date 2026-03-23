import oracledb
import platform
import pandas as pd
import glob
from sqlalchemy import create_engine

# platform을 체크해서 경로를 유연하게 설정
if platform.system() == 'Windows':
    oracledb.init_oracle_client(lib_dir=r"C:\oraclexe\instantclient_19_25")
else:
    # 리눅스(WSL) 경로 설정
    oracledb.init_oracle_client(lib_dir="/opt/oracle/instantclient_19_25")

user = 'scott'
password = 'tiger'
host_port_sid = 'localhost:1521/xe'
engine = create_engine(f'oracle+oracledb://{user}:{password}@{host_port_sid}')

