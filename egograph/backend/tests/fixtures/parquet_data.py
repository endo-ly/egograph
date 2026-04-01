"""サンプルParquetデータ生成ユーティリティ。"""

from io import BytesIO

import pandas as pd


def save_parquet_to_bytes(df: pd.DataFrame) -> bytes:
    """DataFrameをParquetバイト列に変換。

    Args:
        df: 変換するDataFrame

    Returns:
        Parquet形式のバイト列
    """
    buffer = BytesIO()
    df.to_parquet(buffer, engine="pyarrow")
    buffer.seek(0)
    return buffer.read()
