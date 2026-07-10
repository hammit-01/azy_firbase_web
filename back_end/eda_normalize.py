import logging
import pandas as pd

log = logging.getLogger("eda")


def assign_columns(df: pd.DataFrame, schema: list, name: str) -> pd.DataFrame:
    """Schema 기반 열 할당. WMS 레이아웃 변경에도 crash 없이 동작.

    - 열 수 일치: 정상 할당
    - 열 수 초과: 앞 N열만 사용 (WMS가 컬럼 추가한 경우)
    - 열 수 부족: 빈 DataFrame 반환 (데이터 미정합, 사용 불가)
    """
    n_actual   = len(df.columns)
    n_expected = len(schema)

    if n_actual == n_expected:
        result = df.copy()
        result.columns = schema
        return result

    if n_actual > n_expected:
        log.warning(
            f"[{name}] 열 초과: 실제 {n_actual}열 > 예상 {n_expected}열 "
            f"→ 앞 {n_expected}열만 사용 (WMS 레이아웃 변경 확인 필요)"
        )
        result = df.iloc[:, :n_expected].copy()
        result.columns = schema
        return result

    log.error(
        f"[{name}] 열 부족: 실제 {n_actual}열 < 예상 {n_expected}열 "
        f"→ 데이터 미정합으로 해당 창고 스킵"
    )
    return pd.DataFrame()
