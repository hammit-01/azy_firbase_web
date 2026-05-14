from back_end.crawling_list import start_crawling
from back_end.eda_main import list_eda
from post import post

# 통합 창고 크롤링
# final_df, warehouse_dfs = start_crawling()

final_df, warehouse_dfs, jns = start_crawling()

final_df.to_excel("final_df.xlsx", index=False)

# for name, df in warehouse_dfs.items():
#     df.to_excel(f"{name}.xlsx", index=False)

# 창고 데이터 EDA
total_df = list_eda(warehouse_dfs, jns)
# total_df.to_excel("total_df.xlsx", index=False)
# 창고 데이터 DB 업로드
# post(total_df)
