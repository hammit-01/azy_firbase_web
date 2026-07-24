import atexit
import pandas as pd
import re
import time
from back_end.eda_column import column_replace


def _selenium_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=opts)


# ── 드라이버(=로그인 세션) 캐시 ──────────────────────────────
# 사이트별 로그인은 무겁고(브라우저 기동+로그인) 잦은 반복 로그인은 차단 위험 →
# 사이클 간에는 같은 드라이버를 재사용하고, 죽었거나 세션이 만료됐을 때만 재로그인.
_driver_cache: dict = {}


@atexit.register
def _quit_all_cached_drivers():
    """프로세스 종료 시 캐시에 남은 헤드리스 크롬을 정리 — 안 그러면 스케줄러
    재시작/종료 때마다 고아 chromedriver/chrome 프로세스가 계속 쌓인다."""
    for driver in _driver_cache.values():
        try:
            driver.quit()
        except Exception:
            pass


def _driver_alive(driver) -> bool:
    try:
        _ = driver.title
        return True
    except Exception:
        return False


def _get_cached_driver(key):
    driver = _driver_cache.get(key)
    if driver is not None and _driver_alive(driver):
        return driver
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass
        _driver_cache.pop(key, None)
    return None


def _cache_driver(key, driver):
    _driver_cache[key] = driver


def _discard_driver(key):
    driver = _driver_cache.pop(key, None)
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass


def _ecms_login(driver, base_url, user, pw):
    """eCSMS(Blazor) 계열 사이트 공통 로그인"""
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    wait = WebDriverWait(driver, 15)
    driver.get(base_url)
    time.sleep(3)
    id_box = wait.until(EC.element_to_be_clickable((By.NAME, "Username")))
    id_box.clear(); id_box.send_keys(user)
    pw_box = driver.find_element(By.NAME, "Password")
    pw_box.clear(); pw_box.send_keys(pw)
    for b in driver.find_elements(By.TAG_NAME, "button"):
        if "로그인" in b.text:
            b.click()
            break
    time.sleep(3)


def _krcs_fetch_instock(driver, url):
    """eCSMS 재고 조회. 세션 만료(로그인 폼으로 되돌아감) 시 None 반환 — 재로그인 신호."""
    from selenium.webdriver.common.by import By
    from bs4 import BeautifulSoup
    driver.get(url)
    time.sleep(4)

    if driver.find_elements(By.NAME, "Username"):
        return None  # 세션 만료 → 호출부에서 재로그인

    for b in driver.find_elements(By.TAG_NAME, "button"):
        if "조회" in b.text:
            b.click()
            break
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        return []
    records = []
    for row in tables[0].find_all("tr"):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        try:
            int(cells[0].get_text(strip=True))
            records.append([c.get_text(strip=True) for c in cells])
        except ValueError:
            pass
    return records


def _ecms_fetch_cached(key, base_url, instock_url, user, pw):
    """캐시된 드라이버로 조회 시도 → 없거나 세션 만료/오류면 재로그인 후 1회 재시도.
    로그인(_ecms_login) 자체가 타임아웃/예외를 던져도 여기서 삼킨다 — 안 그러면
    crawling_handmade()가 통째로 죽어서, 같은 사이클에서 이미 정상 크롤된 다른
    타창고(효성냉장 등) 데이터까지 MySQL 반영 전에 날아간다."""
    try:
        driver = _get_cached_driver(key)
        if driver is None:
            driver = _selenium_driver()
            _ecms_login(driver, base_url, user, pw)
            _cache_driver(key, driver)

        try:
            records = _krcs_fetch_instock(driver, instock_url)
        except Exception:
            records = None

        if records is None:
            _discard_driver(key)
            driver = _selenium_driver()
            _ecms_login(driver, base_url, user, pw)
            _cache_driver(key, driver)
            try:
                records = _krcs_fetch_instock(driver, instock_url)
            except Exception as e:
                print(f"[{key}] 재시도 실패: {e}")
                _discard_driver(key)
                records = None
    except Exception as e:
        print(f"[{key}] 로그인 실패: {e}")
        _discard_driver(key)
        records = None

    return records or []


# 미빙냉장 (eCSMS, 로그인 az0810/0101 확인 완료)
# TODO: DevExpress Blazor 그리드(dxbl-grid)라 고려/유상의 <table> 파싱이 안 먹힘.
#       현재 실 재고 0건이라 그리드 DOM 구조 미확인 — 실제 재고 들어오면 구조 보고 파서 교체할 것.
def mibing_eda():
    records = _ecms_fetch_cached(
        "미빙냉장", "http://112.170.18.24/", "http://112.170.18.24/instockpageprime",
        "az0810", "0101",
    )

    if not records:
        print("[미빙냉장] 데이터 없음 (또는 그리드 구조 미확인 — 파서 점검 필요)")
        return pd.DataFrame()

    mibing = pd.DataFrame()
    mibing["수탁품"] = [r[1] if len(r) > 1 else "" for r in records]
    mibing["평균중량"] = [r[2] if len(r) > 2 else "" for r in records]
    mibing["재고수량"] = [r[7] if len(r) > 7 else 0 for r in records]
    mibing["BL번호"] = [r[14] if len(r) > 14 else "" for r in records]
    mibing["유통기한"] = [r[21] if len(r) > 21 else "" for r in records]
    mibing["브랜드"] = [r[17] if len(r) > 17 else "" for r in records]
    mibing["창고"] = "미빙냉장"

    mibing = mibing.dropna(subset=["수탁품"])
    if mibing.empty:
        return pd.DataFrame()
    mibing[["수탁품", "등급", "ESTNO"]] = mibing["수탁품"].apply(_parse_korea_web)

    return mibing


# 고려 냉장
def korea_eda():
    try:
        from bs4 import BeautifulSoup  # noqa: imported in helpers
    except ImportError:
        print("[고려냉장] bs4 미설치 → 건너뜀")
        return pd.DataFrame()

    records = _ecms_fetch_cached(
        "고려", "http://krcs.itfarm.co.kr/", "http://krcs.itfarm.co.kr/instockpageprime",
        "az0810", "0101",
    )

    if not records:
        print("[고려냉장] 데이터 없음")
        return pd.DataFrame()

    # 컬럼: 1=수탁품목, 2=규격, 7=재고수량, 14=B/L No, 21=유효일자
    korea = pd.DataFrame()
    korea["수탁품"] = [r[1] if len(r) > 1 else "" for r in records]
    korea["평균중량"] = [r[2] if len(r) > 2 else "" for r in records]
    korea["재고수량"] = [r[7] if len(r) > 7 else 0 for r in records]
    korea["BL번호"] = [r[14] if len(r) > 14 else "" for r in records]
    korea["유통기한"] = [r[21] if len(r) > 21 else "" for r in records]
    korea["창고"] = "고려"

    korea["브랜드"] = [r[17] if len(r) > 17 else "" for r in records]
    korea = korea.dropna(subset=["수탁품"])
    if korea.empty:
        return pd.DataFrame()
    korea[["수탁품", "등급", "ESTNO"]] = korea["수탁품"].apply(_parse_korea_web)

    return korea

# 에이스냉장 공통 헬퍼
_ACE_DEPOT_ROW = {
    '처인사업소': 'gridLookupDepotInventoryInfo_DDD_gv_DXDataRow0',
    '기흥사업소': 'gridLookupDepotInventoryInfo_DDD_gv_DXDataRow1',
    '용인사업소': 'gridLookupDepotInventoryInfo_DDD_gv_DXDataRow2',
}

_ACE_KEY = "에이스"


def _ace_login(driver):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    wait = WebDriverWait(driver, 15)
    driver.get("https://cs.acecs.co.kr/IL6/")
    time.sleep(3)
    wait.until(EC.element_to_be_clickable((By.ID, "UserID"))).send_keys("AZ0810")
    driver.find_element(By.ID, "UserPw").send_keys("0101")
    for b in driver.find_elements(By.TAG_NAME, "button"):
        if "로그인" in b.text:
            b.click()
            break
    time.sleep(4)


def _ace_get_driver():
    driver = _get_cached_driver(_ACE_KEY)
    if driver is None:
        driver = _selenium_driver()
        _ace_login(driver)
        _cache_driver(_ACE_KEY, driver)
    return driver


def _ace_do_fetch(driver, depot_key):
    from selenium.webdriver.common.by import By
    from bs4 import BeautifulSoup
    driver.find_element(By.PARTIAL_LINK_TEXT, "재고조회").click()
    time.sleep(3)
    driver.find_element(By.ID, "gridLookupDepotInventoryInfo_B-1").click()
    time.sleep(1)
    driver.find_element(By.ID, _ACE_DEPOT_ROW[depot_key]).click()
    time.sleep(2)
    driver.find_element(By.ID, "btnInventorySearch").click()
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    inv_table = soup.find("table", id="InventoryList_DXMainTable")
    if not inv_table:
        return []
    records = []
    for row in inv_table.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        vals = [c.get_text(strip=True) for c in cells]
        if len([v for v in vals if v]) >= 8 and vals[5]:
            records.append(vals)
    return records


def _ace_fetch_depot(depot_key):
    driver = _ace_get_driver()
    try:
        return _ace_do_fetch(driver, depot_key)
    except Exception:
        # 세션 문제로 의심 → 캐시 폐기하고 재로그인 후 한 번만 재시도
        _discard_driver(_ACE_KEY)
        driver = _ace_get_driver()
        try:
            return _ace_do_fetch(driver, depot_key)
        except Exception as e:
            print(f"[에이스-{depot_key}] 재시도 실패: {e}")
            _discard_driver(_ACE_KEY)
            return []


def _parse_ace_product(text):
    """에이스 수탁품명 파싱: BRAND)수탁품"등급 /est.ESTNO → 브랜드, 수탁품, 등급
    따옴표가 없는 경우엔 품목명 바로 뒤에 등급이 붙어있음 (예: 우차돌양지S,IW/VAC → 등급 S)."""
    if pd.isna(text):
        return pd.Series({"브랜드": None, "수탁품": None, "등급": None})
    text = re.sub(r"\s*/est\.\S+", "", str(text).strip()).strip()
    if ")" in text:
        brand, rest = text.split(")", 1)
        brand = brand.strip()
    else:
        brand, rest = None, text
    if '"' in rest:
        product, grade = rest.split('"', 1)
        grade = grade.split("(")[0].strip() or None
    else:
        # 콤마/공백 중 먼저 나오는 지점 뒤(가공방식·부가코드 등)는 버림
        head = re.split(r"[,\s]", rest, maxsplit=1)[0]
        m = re.match(r"^(.*?)([A-Z]+)$", head)
        if m and m.group(1):
            product, grade = m.group(1), m.group(2)
        else:
            product, grade = head, None
    return pd.Series({"브랜드": brand, "수탁품": product.strip(), "등급": grade})


def _ace_records_to_df(records, wh_name):
    if not records:
        print(f"[{wh_name}] 데이터 없음")
        return pd.DataFrame()
    df = pd.DataFrame()
    df["수탁품"] = [r[0] for r in records]
    df["평균중량"] = ""
    df["재고수량"] = [r[9] if len(r) > 9 else 0 for r in records]
    df["BL번호"] = [r[5] if len(r) > 5 else "" for r in records]
    df["유통기한"] = [r[12] if len(r) > 12 else "" for r in records]
    df["ESTNO"] = [r[7] if len(r) > 7 else "" for r in records]
    df["창고"] = wh_name
    df = df.dropna(subset=["수탁품"])
    if df.empty:
        return pd.DataFrame()
    df[["브랜드", "수탁품", "등급"]] = df["수탁품"].apply(_parse_ace_product)
    return df


# 에이스기흥
def aceGH_eda():
    records = _ace_fetch_depot("기흥사업소")
    return _ace_records_to_df(records, "에이스기흥")


# 에이스처인
def aceCHIN_eda():
    records = _ace_fetch_depot("처인사업소")
    return _ace_records_to_df(records, "에이스처인")


# 에이스용인
def aceYOGIN_eda():
    records = _ace_fetch_depot("용인사업소")
    return _ace_records_to_df(records, "에이스용인")

# 유상
def yousang_eda():
    records = _ecms_fetch_cached(
        "유상", "http://www.xn--hg4bn0j.kr/", "http://www.xn--hg4bn0j.kr/instockpageprime",
        "az0810", "0101",
    )

    if not records:
        print("[유상] 데이터 없음")
        return pd.DataFrame()

    # 컬럼: 1=수탁품목, 2=규격, 7=재고수량, 14=B/L No, 17=브랜드, 21=유효일자
    yousang = pd.DataFrame()
    yousang["수탁품"] = [r[1] if len(r) > 1 else "" for r in records]
    yousang["평균중량"] = [r[2] if len(r) > 2 else "" for r in records]
    yousang["재고수량"] = [r[7] if len(r) > 7 else 0 for r in records]
    yousang["BL번호"] = [r[14] if len(r) > 14 else "" for r in records]
    yousang["유통기한"] = [r[21] if len(r) > 21 else "" for r in records]
    yousang["브랜드"] = [r[17] if len(r) > 17 else "" for r in records]
    yousang["창고"] = "유상"

    yousang = yousang.dropna(subset=["수탁품"])
    if yousang.empty:
        return pd.DataFrame()
    yousang[["수탁품", "ESTNO"]] = yousang["수탁품"].apply(parse_product_yousang)

    return yousang


# 견우오아시스
_KYUNU_KEY = "견우오아시스"


def _kyunu_login(driver):
    driver.get("http://gwfood.itfarm.co.kr/")
    time.sleep(3)
    driver.execute_script("""
        function setVal(el, val) { el.value = val; el.dispatchEvent(new Event('change', {bubbles:true})); }
        setVal(document.getElementById('ctl00_ctl00_TopPanel_txtID_I'), 'az0810');
        setVal(document.getElementById('ctl00_ctl00_TopPanel_txtPWD_I'), '0101');
    """)
    time.sleep(0.5)
    driver.execute_script("document.getElementById('ctl00_ctl00_TopPanel_btnLogin').click();")
    time.sleep(3)


def _kyunu_do_fetch(driver):
    from bs4 import BeautifulSoup
    driver.get("http://gwfood.itfarm.co.kr/Pages/InStock.aspx")
    time.sleep(3)
    driver.execute_script("document.getElementById('ctl00_ctl00_Content_MainContent_btnSearch').click();")
    time.sleep(5)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    records = []
    for t in soup.find_all("table"):
        txt = t.get_text()
        if "수탁품명" in txt and "B/L No" in txt and "유효일자" in txt:
            for row in t.find_all("tr"):
                cells = row.find_all(["th", "td"])
                vals = [c.get_text(strip=True) for c in cells]
                vals = [v for v in vals if v]
                # 실제 데이터 행: 16개 이상 컬럼, 재고수량(index 6)이 숫자
                if len(vals) >= 16:
                    try:
                        int(vals[6])
                        records.append(vals)
                    except (ValueError, IndexError):
                        pass
            break
    return records


def kyunu_eda():
    try:
        from selenium import webdriver  # noqa: 미설치 여부 확인용
        from bs4 import BeautifulSoup  # noqa
    except ImportError:
        print("[견우오아시스] selenium/bs4 미설치 → 건너뜀")
        return pd.DataFrame()

    try:
        driver = _get_cached_driver(_KYUNU_KEY)
        if driver is None:
            driver = _selenium_driver()
            _kyunu_login(driver)
            _cache_driver(_KYUNU_KEY, driver)

        try:
            records = _kyunu_do_fetch(driver)
        except Exception:
            # 세션 만료(로그인 페이지로 튕겨 JS 대상 엘리먼트가 없어 예외) → 재로그인 후 재시도
            _discard_driver(_KYUNU_KEY)
            driver = _selenium_driver()
            _kyunu_login(driver)
            _cache_driver(_KYUNU_KEY, driver)
            try:
                records = _kyunu_do_fetch(driver)
            except Exception as e:
                print(f"[견우오아시스] 재시도 실패: {e}")
                _discard_driver(_KYUNU_KEY)
                records = []
    except Exception as e:
        # 로그인(_kyunu_login) 자체가 타임아웃/예외를 던져도 여기서 삼킨다 — _ecms_fetch_cached와
        # 동일한 이유(크롤링_handmade 전체가 죽어서 이미 크롤된 다른 타창고 데이터까지 날아감)
        print(f"[견우오아시스] 로그인 실패: {e}")
        _discard_driver(_KYUNU_KEY)
        records = []

    if not records:
        print("[견우오아시스] 데이터 없음")
        return pd.DataFrame()

    # 컬럼 인덱스: 0=수탁품명, 1=규격, 6=재고수량, 13=BL번호, 15=유효일자, 19=브랜드
    kyunu = pd.DataFrame()
    kyunu["수탁품"] = [r[0] for r in records]
    kyunu["평균중량"] = [r[1] if len(r) > 1 else "" for r in records]
    kyunu["재고수량"] = [r[6] if len(r) > 6 else 0 for r in records]
    kyunu["BL번호"] = [r[13] if len(r) > 13 else "" for r in records]
    kyunu["유통기한"] = [r[15] if len(r) > 15 else "" for r in records]
    kyunu["브랜드"] = [r[19] if len(r) > 19 else "" for r in records]
    kyunu["창고"] = "견우오아시스"

    kyunu = kyunu.dropna(subset=["수탁품"])
    if kyunu.empty:
        return pd.DataFrame()
    kyunu[["수탁품", "등급", "ESTNO"]] = kyunu["수탁품"].apply(parse_product_kyunu)

    return kyunu

# 견우 오아시스
def parse_product_kyunu(text):
    pattern = r'^(.*?)\s*\((.*?)\)\s*([A-Z]+)/(.*)$'
    match = re.match(pattern, text)

    if match:
        return pd.Series({
            '수탁품': match.group(1).strip(),
            '등급': match.group(3).strip(),
            'ESTNO': match.group(4).strip()
        })
    else:
        return pd.Series({
            '수탁품': None,
            '등급': None,
            'ESTNO': None
        })

# 유상
def parse_product_yousang(text):

    if pd.isna(text):
        return pd.Series({
            '수탁품': None,
            'ESTNO': None
        })

    text = str(text).strip()

    # 수탁품 추출
    product_match = re.match(r'^([가-힣A-Za-z]+)', text)

    # E.숫자 추출
    estno_match = re.search(r'E\.(\d+)', text)

    return pd.Series({
        '수탁품': product_match.group(1) if product_match else None,
        'ESTNO': estno_match.group(1) if estno_match else None
    })


def _parse_korea_web(text):
    """고려냉장 웹 수탁품명 파싱: 대창(8788610)ACC → 대창, ACC등급"""
    if pd.isna(text):
        return pd.Series({"수탁품": None, "등급": None, "ESTNO": None})
    text = str(text).strip()
    cleaned = re.sub(r"\(\d+\)", "", text).strip()
    m = re.match(r"^([가-힣\s]+)([A-Z/\-]+)$", cleaned)
    if m:
        return pd.Series({"수탁품": m.group(1).strip(), "등급": m.group(2), "ESTNO": None})
    return pd.Series({"수탁품": cleaned, "등급": None, "ESTNO": None})


def _finalize_handmade(result):
    if result.empty:
        return result

    result["평균중량"] = (
        result["평균중량"]
        .astype(str)
        .str.extract(r"([\d.]+)")[0]
        .astype(float)
    )

    result["유통기한"] = (
        pd.to_datetime(result["유통기한"])
        .dt.strftime("%Y.%m.%d")
    )
    return result


def crawling_handmade():
    """수동 크롤링 창고 — 에이스냉장(기흥/처인/용인) 제외.
    에이스는 동시접속 1명 제한(2명째부터 404)이 있어 pipeline/scheduler.py의
    별도 정각 1시간 간격 잡(run_ace_pipeline)에서 처리한다."""
    result = pd.concat([korea_eda(), yousang_eda(), kyunu_eda(), mibing_eda()], ignore_index=True)
    return _finalize_handmade(result)


def crawling_ace():
    """에이스냉장 3개 사업소(기흥/처인/용인) 전용 — 별도 스케줄에서만 호출."""
    result = pd.concat([aceGH_eda(), aceCHIN_eda(), aceYOGIN_eda()], ignore_index=True)
    return _finalize_handmade(result)
