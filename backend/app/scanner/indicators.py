import pandas as pd
import pandas_ta as ta
from typing import Union


class IndicatorCompute:
    """Wrapper for pandas-ta indicators. Returns scalar or Series."""

    @staticmethod
    def sma(df: pd.DataFrame, period: int) -> pd.Series:
        return ta.sma(df["close"], length=period)

    @staticmethod
    def ema(df: pd.DataFrame, period: int) -> pd.Series:
        return ta.ema(df["close"], length=period)

    @staticmethod
    def wma(df: pd.DataFrame, period: int) -> pd.Series:
        return ta.wma(df["close"], length=period)

    @staticmethod
    def dema(df: pd.DataFrame, period: int) -> pd.Series:
        return ta.dema(df["close"], length=period)

    @staticmethod
    def tema(df: pd.DataFrame, period: int) -> pd.Series:
        return ta.tema(df["close"], length=period)

    @staticmethod
    def rsi(df: pd.DataFrame, period: int) -> pd.Series:
        return ta.rsi(df["close"], length=period)

    @staticmethod
    def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
        """Returns (macd_line, signal_line, histogram)."""
        result = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
        return result.iloc[:, 0], result.iloc[:, 1], result.iloc[:, 2]

    @staticmethod
    def stochastic(df: pd.DataFrame, period: int = 14) -> tuple:
        """Returns (k, d)."""
        result = ta.stoch(df["high"], df["low"], df["close"], k=period)
        return result.iloc[:, 0], result.iloc[:, 1]

    @staticmethod
    def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
        return ta.cci(df["high"], df["low"], df["close"], length=period)

    @staticmethod
    def bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> tuple:
        """Returns (upper, middle, lower)."""
        result = ta.bbands(df["close"], length=period, std=std)
        return result.iloc[:, 2], result.iloc[:, 1], result.iloc[:, 0]

    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        return ta.atr(df["high"], df["low"], df["close"], length=period)

    @staticmethod
    def keltner(df: pd.DataFrame, period: int = 20) -> tuple:
        """Returns (upper, middle, lower)."""
        result = ta.kc(df["high"], df["low"], df["close"], length=period)
        return result.iloc[:, 2], result.iloc[:, 1], result.iloc[:, 0]

    @staticmethod
    def obv(df: pd.DataFrame) -> pd.Series:
        return ta.obv(df["close"], df["volume"])

    @staticmethod
    def vwap(df: pd.DataFrame) -> pd.Series:
        return ta.vwap(df["high"], df["low"], df["close"], df["volume"])

    @staticmethod
    def volume_sma(df: pd.DataFrame, period: int) -> pd.Series:
        return df["volume"].rolling(window=period).mean()

    @staticmethod
    def mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        return ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=period)

    @staticmethod
    def avg_volume(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Simple moving average of volume."""
        return df["volume"].rolling(window=period).mean()

    @staticmethod
    def get_last_value(series: Union[pd.Series, tuple]) -> float:
        """Extract last non-NaN value from indicator output."""
        if isinstance(series, tuple):
            series = series[0]
        return series.dropna().iloc[-1]
