from back_end.crawling_list import start_crawling
from back_end.eda_main import list_eda
from post import post

# 통합 창고 크롤링
df = start_crawling()
# 창고 데이터 EDA
total_df = list_eda(df)
# 창고 데이터 DB 업로드
post(total_df)
