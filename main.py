import pandas as pd

from back_end.crawling_list import start_crawling
from back_end.back_eda_main import list_eda
from back_end.equal_df import equal_df

# 통합 창고 크롤링
final_df, jns = start_crawling()

# CS,견우오아시스,고려,에이스,유상 엑셀 로드 및 EDA

# 창고 데이터 EDA
total_df, jns = list_eda(final_df, jns)

jns = jns.drop_duplicates().copy()
jns = equal_df(jns)

jns.to_excel("jns.xlsx", index=False)

from post import post
# 창고 데이터 DB 업로드
# post(jns)
