from back_end.crawling_list import start_crawling
from back_end.list_eda import list_eda
from post import post


df = start_crawling()
df = list_eda(df)
post()
