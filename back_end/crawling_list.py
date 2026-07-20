from bs4 import BeautifulSoup
import pandas as pd
from back_end.eda_common import eda_common
from requests.exceptions import RequestException, Timeout, ConnectionError
from back_end.eda_column import jns,beige,samil,sinu,huichang,aurora,hyosung,eastbelly,swc,ch,daechung,hanladt,hanla,gangdong1,gangdong2,gyungin,plaza,samjin1,samjin2,cs,daejae,irn

# 실제 브라우저와 유사한 UA — 세션 하나 동안은 절대 바꾸지 않음(중간에 바뀌면 오히려 봇 신호)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

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

    "제니스(곤지암)": {
        "login": "http://211.239.173.91:8080/jnsdst3/login.do",
        "data":  "http://211.239.173.91:8080/jnsdst3/rtv_stock01.do"
    },

    "SWC": {
        "login": "http://nwill.net:8080/nswdst/login.do",
        "data": "http://nwill.net:8080/nswdst/rtv_stock.do"
    },
    "대재": {
        "login": "http://nwill.net:8080/djedst/login.do",
        "data": "http://nwill.net:8080/djedst/rtv_stock.do"
    },
    "아이린냉장": {
        "login": "http://211.239.173.91:8080/irndst/login.do",
        "data": "http://211.239.173.91:8080/irndst/rtv_stock.do"
    },
    # 도지냉장: PentascanWMS(완전히 다른 플랫폼) — 로그인 검증만 우선 연결, 데이터 파싱/EDA는 보류
    "도지냉장": {
        "login": "https://wms.pentascan.com/login/login",
        "data": "https://wms.pentascan.com/list/stock"
    }
}

# 창고별 nav_num 오버라이드 (기본값 "0103")
NAV_NUM_OVERRIDE = {
    "아이린냉장": "0105",
    "오로라CS": "0110",
    "신우냉장": "0107",
    "희창냉장": "0107",
}

# 창고별 로그인 폼 필드명 오버라이드 (기본값 id/pw)
LOGIN_FIELD_OVERRIDE = {
    "도지냉장": {"id": "login", "pw": "password"},
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
            "User-Agent": USER_AGENT,
            "Referer": login_url
        }

        # 3️⃣ 로그인 요청
        fields = LOGIN_FIELD_OVERRIDE.get(warehouse, {"id": "id", "pw": "pw"})
        res = session.post(
            login_url,
            data={
                fields["id"]: id,
                fields["pw"]: pw
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
            url = f"http://211.239.173.{ip_port}/{path}/rtv_stock01.do"

        dt = date if date else pd.Timestamp.now().strftime("%Y%m%d")

        if pd.isna(scmdept):
            scmdept = "00"

        payload = {
            "nav_num": NAV_NUM_OVERRIDE.get(warehouse, "0103"),
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

        # thead 헤더 캡처
        header_row = soup.select_one("thead tr")

        # 세션 만료 감지: 조회 응답에 데이터 테이블 없이 로그인 폼이 돌아오면 재로그인 필요
        if header_row is None and "아이디" in res.text and "비밀번호" in res.text:
            return None

        headers = []
        if header_row:
            headers = [
                th.get_text(strip=True).replace("\n", " ")
                for th in header_row.find_all(["th", "td"])
            ]

        _NO_DATA_PHRASES = ("조회된 결과가 없습니다", "데이터가 없습니다", "결과가 없습니다")
        rows = soup.select("tbody tr")
        data = []
        for row in rows:
            cols = [
                td.get_text(strip=True).replace("\n", " ")
                for td in row.find_all("td")
            ]
            if not cols:
                continue
            row_text = " ".join(cols)
            if any(phrase in row_text for phrase in _NO_DATA_PHRASES):
                continue
            data.append(cols)

        if not data:
            return pd.DataFrame()

        if headers:
            n = len(data[0])
            if len(headers) > n:
                headers = headers[:n]
            elif len(headers) < n:
                headers += [f"col_{i}" for i in range(len(headers), n)]
            return pd.DataFrame(data, columns=headers)

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
    "한라동탄": hanladt,
    "한라곤지암": hanla,
    "강동1": gangdong1,
    "강동2": gangdong2,
    "경인": gyungin,
    "프라자로지스": plaza,
    "삼진1": samjin1,
    "삼진2": samjin2,
    "CS": cs,
    "아이린냉장": irn,
    "제니스(곤지암)": jns
}
