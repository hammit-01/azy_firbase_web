import requests
from bs4 import BeautifulSoup
import pandas as pd

def get_users(row):
    users = []

    if pd.notna(row["아이디"]):
        users.append(("일반", row["아이디"], row["비밀번호"], row["scustcd"], "00"))

    if pd.notna(row["통관분_아이디"]):
        users.append(("통관분", row["통관분_아이디"], row["통관분_비밀번호"], row["scustcd"], "00"))

    if pd.notna(row["웹출고_아이디"]):
        users.append(("웹출고", row["웹출고_아이디"], row["웹출고_비밀번호"], row["scustcd"], "00"))

    if pd.notna(row["웹출고(통관분)_아이디"]):
        users.append(("웹출고(통관분)", row["웹출고(통관분)_아이디"], row["웹출고(통관분)_비밀번호"], row["scustcd"], row["scmdept"]))

    return users        
    
def login(session, ip_port, path, id, pw):
    base = f"http://211.239.173.{ip_port}"
    login_url = f"{base}/{path}/login.do"

    # 1️⃣ 먼저 페이지 접근 (쿠키 획득)
    session.get(login_url)

    # 2️⃣ 헤더 추가
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": login_url
    }

    # 3️⃣ 로그인 POST
    res = session.post(
        login_url,
        data={"id": id, "pw": pw},
        headers=headers
    )

    return res


def get_data(session, ip_port, path, scustcd, scmdept):
    # 데이터 요청
    url = f"http://211.239.173.{ip_port}/{path}/rtv_stock.do"

    dt = pd.Timestamp.now().strftime("%Y%m%d")

    if pd.isna(scmdept):
        scmdept = "00"
    
    # 나중에 창고별로 만들어둬야함
    payload = {
        "nav_num": "0102",
        "scmdept": scmdept, #
        "swms_cd": "",
        "scustcd": scustcd, #
        "pmname": "",
        "blno": "",
        "dt": dt,
        "pass_fg": "*"
    }

    print(payload)
    res = session.post(url, data=payload)  

    # 3️⃣ HTML 파싱
    soup = BeautifulSoup(res.text, "html.parser")

    rows = soup.select("tbody tr")

    data = []
    for row in rows:
        cols = [td.get_text(strip=True).replace("\n", " ") for td in row.find_all("td")]
        if cols:
            data.append(cols)
    
    df = pd.DataFrame(data)
    
    return  df


def start_crawling():
    # 크롤링
    warehouse_list = pd.read_excel("warehouse_list.xlsx")

    warehouse_list.columns = warehouse_list.iloc[0]   # 첫 행을 컬럼으로 설정
    warehouse_list = warehouse_list[1:].reset_index(drop=True)  # 첫 행 제거
    warehouse_list = warehouse_list[(warehouse_list["타사이트"] != True) &(warehouse_list["주소"].notna())]

    wh_90 = warehouse_list[warehouse_list["ip포트"] == 90]
    wh_88 = warehouse_list[warehouse_list["ip포트"] == "88:8080"]
    wh_91 = warehouse_list[warehouse_list["ip포트"] == "91:8080"]

    dfs = [wh_90, wh_88, wh_91]
    names = ["wh_90", "wh_88", "wh_91"]

    all_data = []

    for df in dfs:
        for _, row in df.iterrows():
            users = get_users(row)

            ip_port = str(row["ip포트"])
            path = str(row["약식주소"])
            
            print(users)

            for user_type, id, pw, scustcd, scmdept in users:
                session = requests.Session()

                res = login(session, ip_port, path, id, pw)

                print(f"{user_type} 로그인:", res.status_code, row["창고"])

                data = get_data(session, ip_port, path, scustcd, scmdept)
                
                data["창고"] = row["창고"]
                data["수집일"] = pd.Timestamp.now().strftime("%Y%m%d")
                
                all_data.append(data)

    final_df = pd.concat(all_data, ignore_index=True)
    final_df.to_excel("final_df.xlsx", index=False)

    print(final_df.head())
    
    return final_df
