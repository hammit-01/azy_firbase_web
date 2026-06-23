import pandas as pd
from back_end.crawling_list import start_crawling
from back_end.back_eda_main import list_eda
from post import post

# 오늘 크롤링
final_df, jns = start_crawling()
_, jns = list_eda(final_df, jns)
jns = jns.drop_duplicates().copy()

jns.to_excel("jns.xlsx", index=False)

# 창고 데이터 DB 업로드
post(jns)
