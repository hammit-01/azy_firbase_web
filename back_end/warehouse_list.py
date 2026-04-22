# 타창고 사이트 정보 엑셀 불러오기

import pandas as pd

df = pd.read_excel("warehouse_list.xlsx")

df.columns = df.iloc[0]   # 첫 행을 컬럼으로 설정
df = df[1:].reset_index(drop=True)  # 첫 행 제거

print(df)