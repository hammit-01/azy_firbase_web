import pandas as pd

def safe_df(df, name=""):

    if df is None:
        print(f"{name}: None 데이터")
        return pd.DataFrame()

    if not isinstance(df, pd.DataFrame):
        print(f"{name}: DataFrame 아님")
        return pd.DataFrame()

    if df.empty:
        print(f"{name}: 빈 데이터")
        return pd.DataFrame()

    if df.shape[1] <= 2:
        print(f"{name}: 컬럼 부족 ({df.shape[1]}개)")
        return pd.DataFrame()

    return df

def safe_eda(func, df, name=""):
    df = safe_df(df, name)
    return func(df) if not df.empty else df