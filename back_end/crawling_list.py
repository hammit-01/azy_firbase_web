import requests
from bs4 import BeautifulSoup
import pandas as pd
from back_end.eda_common import eda_common
from requests.exceptions import RequestException, Timeout, ConnectionError
from back_end.eda_column import jns,beige,samil,sinu,huichang,aurora,hyosung,eastbelly,swc,ch,daechung,hanladt,hanla,gangdong1,gangdong2,gyungin,plaza,samjin1,samjin2,cs,daejae

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


SPECIAL_SITES = {
    "베이지박스투": {
        "login": "http://211.239.173.91:8080/bbtdst/login.do",
        "data": "http://211.239.173.91:8080/bbtdst/rtv_stock.do"
    },

    "삼일물류": {
        "login": "http://nwill.net:8080/sidst/login.do",
        "data": "http://nwill.net:8080/sidst/rtv_stock.do"
    },

    "신우냉장": {
        "login": "http://nwill.net:8080/swdst/login.do",
        "data": "http://nwill.net:8080/swdst/rtv_stock.do"
    },

    "오로라CS": {
        "login": "http://211.239.173.90:8080/aurdst/login.do",
        "data": "http://211.239.173.90:8080/aurdst/rtv_stock.do"
    },

    "이스트밸리": {
        "login": "http://nwill.net:8080/estdst/login.do",
        "data": "http://nwill.net:8080/estdst/rtv_stock.do"
    },

    "효성냉장": {
        "login": "http://coldwms.hyosung.com/login.do",
        "data": "http://coldwms.hyosung.com/rtv_stock.do"
    },

    "희창냉장": {
        "login": "http://nwill.net/hcy1dst/login.do",
        "data": "http://nwill.net/hcy1dst/rtv_stock.do"
    },

    "SWC": {
        "login": "http://nwill.net:8080/nswdst/login.do",
        "data": "http://nwill.net:8080/nswdst/rtv_stock.do"
    },
    "대재": {
        "login": "http://nwill.net:8080/djedst/login.do",
        "data": "http://nwill.net:8080/djedst/rtv_stock.do"
    }
}

def get_loginUrls(ip_port, path, warehouse):
    if warehouse in SPECIAL_SITES:
        return SPECIAL_SITES[warehouse]["login"]
    else:
        base = f"http://211.239.173.{ip_port}"
        return f"{base}/{path}/login.do"


def login(session, ip_port, path, id, pw, warehouse):

    try:
        login_url = get_loginUrls(ip_port, path, warehouse)

        # 1️⃣ 페이지 접근
        first_res = session.get(
            login_url,
            timeout=10
        )

        first_res.raise_for_status()

        # 2️⃣ 헤더
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": login_url
        }

        # 3️⃣ 로그인 요청
        res = session.post(
            login_url,
            data={
                "id": id,
                "pw": pw
            },
            headers=headers,
            timeout=10
        )

        res.raise_for_status()

        # 4️⃣ 로그인 성공 여부 체크
        # 사이트 구조에 맞게 수정 필요
        if "로그아웃" in res.text or "logout" in res.text.lower():
            print(f"[{warehouse}] 로그인 성공")
            return res

        elif "아이디" in res.text and "비밀번호" in res.text:
            raise Exception("아이디 또는 비밀번호 불일치")

        else:
            raise Exception("로그인 실패 (원인 불명)")

    except Timeout:
        print(f"[{warehouse}] 서버 응답 시간 초과")

    except ConnectionError:
        print(f"[{warehouse}] 서버 연결 실패")

    except RequestException as e:
        print(f"[{warehouse}] HTTP 오류: {e}")

    except Exception as e:
        print(f"[{warehouse}] 로그인 오류: {e}")

    return None


def get_data(session, ip_port, path, scustcd, scmdept, warehouse, date=None):
    url = ""
    try:
        if warehouse in SPECIAL_SITES:
            url = SPECIAL_SITES[warehouse]["data"]
        else:
            url = f"http://211.239.173.{ip_port}/{path}/rtv_stock.do"

        dt = date if date else pd.Timestamp.now().strftime("%Y%m%d")

        if pd.isna(scmdept):
            scmdept = "00"

        payload = {
            "nav_num": "0102",
            "scmdept": scmdept,
            "swms_cd": "",
            "scustcd": scustcd,
            "pmname": "",
            "blno": "",
            "dt": dt,
            "pass_fg": "*"
        }

        res = session.post(url, data=payload, timeout=15)

        res.raise_for_status()

        soup = BeautifulSoup(res.text, "html.parser")

        rows = soup.select("tbody tr")

        data = []

        for row in rows:
            cols = [
                td.get_text(strip=True).replace("\n", " ")
                for td in row.find_all("td")
            ]

            if cols:
                data.append(cols)

        return pd.DataFrame(data)

    except Exception as e:
        print(f"데이터 수집 실패: {e}")
        return pd.DataFrame()

PROCESS_MAP = {
    "베이지박스투": beige,
    "삼일물류": samil,
    "신우냉장": sinu,
    "희창냉장": huichang,
    "오로라CS": aurora,
    "효성냉장": hyosung,
    "이스트밸리": eastbelly,
    "SWC": swc,
    "시에이치물류": ch,
    "대청": daechung,
    "대재": daejae,
    "한라 동탄": hanladt,
    "한라": hanla,
    "강동1": gangdong1,
    "강동2": gangdong2,
    "경인": gyungin,
    "프라자로지스": plaza,
    "삼진1": samjin1,
    "삼진2": samjin2,
    "CS": cs,
    "제니스(곤지암)": jns
}

def start_crawling(date=None):
    # 크롤링
    warehouse_list = pd.read_excel("back_end/data/warehouse_list.xlsx")

    warehouse_list.columns = warehouse_list.iloc[0]   # 첫 행을 컬럼으로 설정
    warehouse_list = warehouse_list[1:].reset_index(drop=True)  # 첫 행 제거

    warehouse_list["ip포트"] = (
        warehouse_list["ip포트"]
        .astype(str)
        .str.strip()
    )
    # wh_90 = warehouse_list[warehouse_list["ip포트"] == "90"]
    # wh_88 = warehouse_list[warehouse_list["ip포트"] == "88:8080"]
    # wh_91 = warehouse_list[warehouse_list["ip포트"] == "91:8080"]
    # wh_else = warehouse_list[
    #     warehouse_list["창고"].isin([
    #         "베이지박스투",
    #         "삼일물류",
    #         "신우냉장",
    #         "오로라CS",
    #         "이스트밸리",
    #         "효성냉장",
    #         "희창냉장",
    #         "SWC",
    #         "대재"
    #     ])
    # ]
    jns = warehouse_list[warehouse_list["창고"] == "제니스(곤지암)"]

    # for name in warehouse_list["창고"].unique():
    #     print(repr(name))
    # dfs = [wh_90, wh_88, wh_91, wh_else]
    dfs = [jns.copy()]

    all_data = []
    # jns = pd.DataFrame()

    for df in dfs:
        for _, row in df.iterrows():
            users = get_users(row)

            warehouse = str(row["창고"])
            ip_port = str(row["ip포트"])
            path = str(row["약식주소"])

            for user_type, id, pw, scustcd, scmdept in users:
                session = requests.Session()

                res = login(session, ip_port, path, id, pw, warehouse)
                if res is None:
                    continue

                print(f"{user_type} 로그인:", res.status_code, row["창고"])

                data = get_data(session, ip_port, path, scustcd, scmdept, warehouse, date=date)

                if data is None or data.empty:
                    print(f"{warehouse}: 재고 없음")
                    continue
                else: data = data
                
                data["창고"] = row["창고"]
                
                # 창고 기준으로 중복 행 제거
                data = data.drop_duplicates()

                # CS -> 한라동탄, 한라동탄 -> CS, 한라곤지암 -> 한라 로 변경
                # warehouse_replace_map = {
                #     "한라곤지암": "한라",
                # }

                # warehouse = warehouse_replace_map.get(warehouse, warehouse)

                data["창고"] = warehouse

                # 여기다 열 전처리 넣을까
                func = PROCESS_MAP.get(warehouse)

                if func:
                    data = func(data)
                    if warehouse == "제니스(곤지암)":
                        jns = pd.DataFrame(data)
                    # else: all_data.append(data)

    # final_df = pd.concat(all_data, ignore_index=True)
    final_df = pd.DataFrame()

    return final_df, jns
