def rename_column(ch, jns, plz):
    dfs = {
        "ch": ch,
        "jns": jns,
        "plz": plz
    }
    
    for name, d in dfs.items():
        if name == "jns":
            d.rename(columns={
                "사업부": "수탁품",
                "수탁품": "브랜드",
                "규격단위중량": "등급",
                "단위": "ESTNO",
                "LOT-NO": "평균중량",
                "ESTNO": "B/L NO식별번호",
                "담보수량": "소비기한제조일자"
            }, inplace=True)
        else:
            d.rename(columns={
                "품목코드": "규격단위중량",
                "LOT-NO": "B/L NO식별번호",
                "B/L NO식별번호": "ESTNO",
                "저장구역": "재고수량",
                "재고수량": "중량",
                "중량": "허용수량",
                "허용수량": "담보수량",
                "적재수량": "소비기한제조일자"
            }, inplace=True)

    return ch, jns, plz