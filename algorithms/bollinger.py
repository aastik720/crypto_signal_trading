# ============================================
# CRYPTO SIGNAL BOT - BOLLINGER BANDS ANALYZER
# ============================================
# Brain #3 of 4: Bollinger Bands
#
# Bollinger Bands measure volatility and identify
# overbought/oversold conditions using a moving
# average with standard deviation envelopes.
#
# Components:
#   Middle Band = SMA(20)
#   Upper Band  = SMA(20) + 2 × StdDev(20)
#   Lower Band  = SMA(20) - 2 × StdDev(20)
#
# Key signals:
#   Price near Upper Band  → potentially overbought
#   Price near Lower Band  → potentially oversold
#   Band Squeeze (narrow)  → low volatility, breakout coming
#   Band Expansion (wide)  → high volatility move underway
#   Bounce off band        → mean reversion signal
#   Break through band     → trend continuation signal
#
# Additional indicators:
#   %B = (Price - Lower) / (Upper - Lower)
#       %B > 1 → above upper band
#       %B < 0 → below lower band
#       %B = 0.5 → at middle band
#
#   Bandwidth = (Upper - Lower) / Middle × 100
#       Low bandwidth → squeeze → breakout incoming
#
# All calculations done FROM SCRATCH.
# No external TA library used.
#
# Usage:
#   from algorithms.bollinger import bollinger_analyzer
#   result = bollinger_analyzer.analyze(dataframe)
# ============================================

import numpy as np
import pandas as pd
from config.settings import Config


class BollingerAnalyzer:
    """
    Bollinger Bands trading signal analyzer.

    Calculates upper, middle, and lower bands from raw
    price data, detects squeezes, bounces, breakouts,
    and band walks. Produces a scored signal with
    direction and confidence.

    Attributes:
        period (int):   SMA and StdDev period (default 20)
        std_dev (int):  Standard deviation multiplier (default 2)
        results (dict): Stores latest analysis results
    """

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self, period=None, std_dev=None):
        """
        Initialize the Bollinger Bands Analyzer.

        Args:
            period (int):  SMA period for middle band.
                          Uses Config.BOLLINGER_PERIOD if not given.
            std_dev (int): Standard deviation multiplier.
                          Uses Config.BOLLINGER_STD if not given.
        """
        # ------ Periods from Config or arguments ------
        self.period = period if period is not None else Config.BOLLINGER_PERIOD
        self.std_dev = std_dev if std_dev is not None else Config.BOLLINGER_STD

        # ------ Minimum data needed ------
        # Need 'period' candles for first SMA value plus
        # extra buffer for analysis functions
        self.min_data_points = self.period + 10

        # ------ Storage for latest analysis results ------
        self.results = {}

        print("[BOLLINGER] ✅ Analyzer initialized | "
              "Period: {} | StdDev: {}x".format(
                  self.period, self.std_dev
              ))

    # ============================================
    # FUNCTION 2: CALCULATE BANDS (From Scratch)
    # ============================================

    def calculate_bands(self, df):
        """
        Calculates Bollinger Bands from close prices.

        Step 1: Middle Band = Simple Moving Average (SMA)
            SMA[i] = mean(close[i-period+1 : i+1])

        Step 2: Standard Deviation over same window
            StdDev[i] = std(close[i-period+1 : i+1])

        Step 3: Upper Band = Middle + (std_dev × StdDev)
                Lower Band = Middle - (std_dev × StdDev)

        First (period-1) values are NaN because the
        rolling window hasn't filled yet.

        Args:
            df (DataFrame): Must have 'close' column (float)

        Returns:
            dict: {
                "upper": pd.Series,
                "middle": pd.Series,
                "lower": pd.Series
            }
            Returns None on error.
        """
        try:
            # ------ Validate input ------
            if df is None or df.empty:
                print("[BOLLINGER] ⚠️ Empty DataFrame received")
                return None

            if "close" not in df.columns:
                print("[BOLLINGER] ⚠️ 'close' column missing")
                return None

            close = df["close"].astype(float)

            if len(close) < self.period:
                print("[BOLLINGER] ⚠️ Need {} prices, got {}".format(
                    self.period, len(close)
                ))
                return None

            # ------ Convert to numpy for speed ------
            values = close.values
            data_length = len(values)

            # ------ Pre-allocate arrays with NaN ------
            middle_arr = np.full(data_length, np.nan, dtype=np.float64)
            upper_arr = np.full(data_length, np.nan, dtype=np.float64)
            lower_arr = np.full(data_length, np.nan, dtype=np.float64)

            # ------ Calculate rolling SMA and StdDev ------
            # For each position from (period-1) onward:
            #   window = values[i - period + 1 : i + 1]
            #   SMA = mean(window)
            #   STD = std(window, ddof=0)  ← population std dev
            for i in range(self.period - 1, data_length):
                window = values[i - self.period + 1: i + 1]

                # Skip if window contains NaN
                valid = window[~np.isnan(window)]
                if len(valid) < self.period:
                    continue

                sma = np.mean(valid)
                std = np.std(valid, ddof=0)  # Population std dev

                middle_arr[i] = sma
                upper_arr[i] = sma + (self.std_dev * std)
                lower_arr[i] = sma - (self.std_dev * std)

            # ------ Build pandas Series with original index ------
            middle = pd.Series(
                middle_arr, index=close.index,
                name="BB_Middle", dtype=np.float64
            )
            upper = pd.Series(
                upper_arr, index=close.index,
                name="BB_Upper", dtype=np.float64
            )
            lower = pd.Series(
                lower_arr, index=close.index,
                name="BB_Lower", dtype=np.float64
            )

            valid_count = middle.dropna().shape[0]
            if valid_count > 0:
                print("[BOLLINGER] Calculated | {} valid points | "
                      "Upper: {:.4f} | Mid: {:.4f} | "
                      "Lower: {:.4f}".format(
                          valid_count,
                          upper.dropna().iloc[-1],
                          middle.dropna().iloc[-1],
                          lower.dropna().iloc[-1],
                      ))

            return {
                "upper": upper,
                "middle": middle,
                "lower": lower,
            }

        except Exception as e:
            print("[BOLLINGER] ❌ Band calculation error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 3: CALCULATE %B
    # ============================================

    def calculate_percent_b(self, close, upper, lower):
        """
        Calculates the %B (Percent B) indicator.

        %B shows where the price is relative to the bands:
            %B = (Close - Lower Band) / (Upper Band - Lower Band)

        Interpretation:
            %B = 1.0  → price at upper band
            %B = 0.5  → price at middle band
            %B = 0.0  → price at lower band
            %B > 1.0  → price ABOVE upper band (extreme bullish)
            %B < 0.0  → price BELOW lower band (extreme bearish)

        Args:
            close (pd.Series):  Close prices
            upper (pd.Series):  Upper band values
            lower (pd.Series):  Lower band values

        Returns:
            pd.Series: %B values, or None on error
        """
        try:
            # ------ Validate inputs ------
            if close is None or upper is None or lower is None:
                return None

            # ------ Calculate band width (denominator) ------
            band_width = upper - lower

            # ------ Avoid division by zero ------
            # Replace zero band width with NaN to prevent inf
            band_width_safe = band_width.replace(0, np.nan)

            # ------ %B formula ------
            percent_b = (close - lower) / band_width_safe
            percent_b.name = "Percent_B"

            return percent_b

        except Exception as e:
            print("[BOLLINGER] ❌ %B calculation error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 4: CALCULATE BANDWIDTH
    # ============================================

    def calculate_bandwidth(self, upper, lower, middle):
        """
        Calculates Bollinger Bandwidth.

        Bandwidth = (Upper - Lower) / Middle × 100

        Bandwidth measures how wide the bands are
        relative to the middle band. Higher values
        mean more volatility.

        Typical values:
            < 5%   → Very low volatility (squeeze)
            5-15%  → Normal volatility
            > 15%  → High volatility

        Args:
            upper (pd.Series):  Upper band values
            lower (pd.Series):  Lower band values
            middle (pd.Series): Middle band (SMA) values

        Returns:
            pd.Series: Bandwidth as percentage, or None on error
        """
        try:
            if upper is None or lower is None or middle is None:
                return None

            # Avoid division by zero
            middle_safe = middle.replace(0, np.nan)

            bandwidth = ((upper - lower) / middle_safe) * 100.0
            bandwidth.name = "Bandwidth"

            return bandwidth

        except Exception as e:
            print("[BOLLINGER] ❌ Bandwidth calculation error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 5: DETECT SQUEEZE
    # ============================================

    def detect_squeeze(self, bandwidth, lookback=50):
        """
        Detects a Bollinger Band squeeze (low volatility).

        A squeeze occurs when bandwidth is at historically
        low levels, indicating the market is "coiling up"
        for a big move. This is one of the most powerful
        Bollinger Band signals.

        Detection method:
        1. Look at the last 'lookback' bandwidth values
        2. Find the min and max bandwidth in that window
        3. Calculate where current bandwidth sits as a percentile
        4. If current bandwidth is in the bottom 20% → SQUEEZE

        Squeeze strength:
        - Bottom 5%  → strength = 100 (extreme squeeze)
        - Bottom 10% → strength = 80
        - Bottom 15% → strength = 60
        - Bottom 20% → strength = 40

        Args:
            bandwidth (pd.Series): Bandwidth values from calculate_bandwidth
            lookback (int):        How far back to check (default 50 candles)

        Returns:
            dict: {
                "is_squeeze": True/False,
                "squeeze_strength": 0-100
            }
        """
        default_result = {
            "is_squeeze": False,
            "squeeze_strength": 0,
        }

        try:
            if bandwidth is None:
                return default_result

            valid_bw = bandwidth.dropna()

            if len(valid_bw) < 5:
                return default_result

            # ------ Get lookback window ------
            actual_lookback = min(lookback, len(valid_bw))
            window = valid_bw.iloc[-actual_lookback:]

            current_bw = float(window.iloc[-1])
            bw_min = float(window.min())
            bw_max = float(window.max())

            # ------ Calculate percentile position ------
            bw_range = bw_max - bw_min

            if bw_range == 0:
                # All bandwidth values are the same — no squeeze
                return default_result

            # percentile: 0 = at minimum, 1 = at maximum
            percentile = (current_bw - bw_min) / bw_range

            # ------ Squeeze detection ------
            # Bottom 20% of range = squeeze
            is_squeeze = percentile <= 0.20

            # ------ Squeeze strength ------
            # Lower percentile = stronger squeeze
            if percentile <= 0.05:
                squeeze_strength = 100
            elif percentile <= 0.10:
                squeeze_strength = 80
            elif percentile <= 0.15:
                squeeze_strength = 60
            elif percentile <= 0.20:
                squeeze_strength = 40
            else:
                squeeze_strength = 0

            if is_squeeze:
                print("[BOLLINGER] 🔥 SQUEEZE detected | "
                      "BW: {:.2f}% | Percentile: {:.1f}% | "
                      "Strength: {}".format(
                          current_bw, percentile * 100,
                          squeeze_strength
                      ))

            return {
                "is_squeeze": is_squeeze,
                "squeeze_strength": squeeze_strength,
            }

        except Exception as e:
            print("[BOLLINGER] ❌ Squeeze detection error: {}".format(e))
            return default_result

    # ============================================
    # FUNCTION 6: DETECT BOUNCE
    # ============================================

    def detect_bounce(self, df, upper, lower):
        """
        Detects price bouncing off Bollinger Bands.

        A bounce occurs when price touches or crosses a band
        and then reverses direction. This is a mean-reversion
        signal — price tends to return toward the middle band.

        BOUNCE FROM LOWER BAND (bullish):
            Recent candle low touched/crossed lower band
            AND current close is ABOVE the low (price recovering)
            AND current close is above lower band (bounced back)

        BOUNCE FROM UPPER BAND (bearish):
            Recent candle high touched/crossed upper band
            AND current close is BELOW the high (price retreating)
            AND current close is below upper band (bounced back)

        Checks the last 5 candles for bounce patterns.

        Args:
            df (DataFrame):     Must have 'close', 'low', 'high'
            upper (pd.Series):  Upper band values
            lower (pd.Series):  Lower band values

        Returns:
            str: "BOUNCE_LOWER" | "BOUNCE_UPPER" | "NONE"
        """
        try:
            # ------ Validate inputs ------
            if df is None or df.empty:
                return "NONE"

            if upper is None or lower is None:
                return "NONE"

            required_cols = ["close", "high", "low"]
            for col in required_cols:
                if col not in df.columns:
                    return "NONE"

            # ------ Get last 5 candles of valid data ------
            # Align all series to same valid indices
            valid_mask = upper.notna() & lower.notna()
            valid_indices = valid_mask[valid_mask].index

            if len(valid_indices) < 3:
                return "NONE"

            check_count = min(5, len(valid_indices))
            recent_idx = valid_indices[-check_count:]

            close = df.loc[recent_idx, "close"].values.astype(float)
            high = df.loc[recent_idx, "high"].values.astype(float)
            low = df.loc[recent_idx, "low"].values.astype(float)
            up_vals = upper.loc[recent_idx].values.astype(float)
            lo_vals = lower.loc[recent_idx].values.astype(float)

            current_close = close[-1]
            current_lower = lo_vals[-1]
            current_upper = up_vals[-1]

            # ------ Check LOWER BAND bounce ------
            # Look for any candle that touched/crossed lower band
            # followed by price recovering above the lower band
            for i in range(len(low) - 1):
                # Did this candle's low touch or go below lower band?
                touched_lower = low[i] <= lo_vals[i]

                if touched_lower:
                    # Did price recover? Current close above lower band
                    if current_close > current_lower:
                        # Confirm upward movement after touch
                        if current_close > close[i]:
                            print("[BOLLINGER] ⬆️ BOUNCE from LOWER band "
                                  "detected (low {:.4f} touched band "
                                  "{:.4f})".format(low[i], lo_vals[i]))
                            return "BOUNCE_LOWER"

            # ------ Check UPPER BAND bounce ------
            for i in range(len(high) - 1):
                # Did this candle's high touch or go above upper band?
                touched_upper = high[i] >= up_vals[i]

                if touched_upper:
                    # Did price retreat? Current close below upper band
                    if current_close < current_upper:
                        # Confirm downward movement after touch
                        if current_close < close[i]:
                            print("[BOLLINGER] ⬇️ BOUNCE from UPPER band "
                                  "detected (high {:.4f} touched band "
                                  "{:.4f})".format(high[i], up_vals[i]))
                            return "BOUNCE_UPPER"

            return "NONE"

        except Exception as e:
            print("[BOLLINGER] ❌ Bounce detection error: {}".format(e))
            return "NONE"

    # ============================================
    # FUNCTION 7: DETECT BREAKOUT
    # ============================================

    def detect_breakout(self, df, upper, lower, volume_series=None):
        """
        Detects price breaking through Bollinger Bands with volume.

        A breakout is DIFFERENT from a bounce:
        - Bounce = price touches band and reverses (mean reversion)
        - Breakout = price pushes THROUGH band and keeps going
                     (trend continuation)

        Volume confirmation makes breakouts more reliable.
        If volume is above its 20-period average during the
        breakout, it's a confirmed breakout.

        BREAKOUT UP:
            Current close ABOVE upper band
            AND close is higher than previous close (momentum)
            AND volume above average (if volume data available)

        BREAKOUT DOWN:
            Current close BELOW lower band
            AND close is lower than previous close (momentum)
            AND volume above average (if volume data available)

        Args:
            df (DataFrame):          Must have 'close', 'volume'
            upper (pd.Series):       Upper band values
            lower (pd.Series):       Lower band values
            volume_series (pd.Series): Volume data (optional,
                                      falls back to df['volume'])

        Returns:
            str: "BREAKOUT_UP" | "BREAKOUT_DOWN" | "NONE"
        """
        try:
            # ------ Validate inputs ------
            if df is None or df.empty:
                return "NONE"

            if upper is None or lower is None:
                return "NONE"

            if "close" not in df.columns:
                return "NONE"

            # ------ Get last 3 valid data points ------
            valid_mask = upper.notna() & lower.notna()
            valid_indices = valid_mask[valid_mask].index

            if len(valid_indices) < 2:
                return "NONE"

            last_idx = valid_indices[-1]
            prev_idx = valid_indices[-2]

            current_close = float(df.loc[last_idx, "close"])
            prev_close = float(df.loc[prev_idx, "close"])
            current_upper = float(upper.loc[last_idx])
            current_lower = float(lower.loc[last_idx])

            # ------ Volume confirmation (optional) ------
            volume_confirmed = True  # Default: confirmed if no volume data

            if volume_series is not None and len(volume_series.dropna()) >= 20:
                vol_valid = volume_series.dropna()
                current_vol = float(vol_valid.iloc[-1])
                avg_vol = float(vol_valid.iloc[-20:].mean())
                volume_confirmed = current_vol > avg_vol

            elif "volume" in df.columns:
                vol_data = df["volume"].dropna()
                if len(vol_data) >= 20:
                    current_vol = float(vol_data.iloc[-1])
                    avg_vol = float(vol_data.iloc[-20:].mean())
                    volume_confirmed = current_vol > avg_vol

            # ------ Check BREAKOUT UP ------
            if current_close > current_upper:
                # Price is above upper band
                if current_close > prev_close:
                    # Momentum is upward
                    if volume_confirmed:
                        print("[BOLLINGER] 🚀 BREAKOUT UP detected | "
                              "Close: {:.4f} > Upper: {:.4f} | "
                              "Volume confirmed: {}".format(
                                  current_close, current_upper,
                                  volume_confirmed
                              ))
                        return "BREAKOUT_UP"

            # ------ Check BREAKOUT DOWN ------
            if current_close < current_lower:
                # Price is below lower band
                if current_close < prev_close:
                    # Momentum is downward
                    if volume_confirmed:
                        print("[BOLLINGER] 💥 BREAKOUT DOWN detected | "
                              "Close: {:.4f} < Lower: {:.4f} | "
                              "Volume confirmed: {}".format(
                                  current_close, current_lower,
                                  volume_confirmed
                              ))
                        return "BREAKOUT_DOWN"

            return "NONE"

        except Exception as e:
            print("[BOLLINGER] ❌ Breakout detection error: {}".format(e))
            return "NONE"

    # ============================================
    # FUNCTION 8: DETECT BAND WALK
    # ============================================

    def detect_band_walk(self, df, upper, lower, periods=5):
        """
        Detects price "walking" along a Bollinger Band.

        Band walking occurs during strong trends when price
        stays near one band for multiple consecutive candles.
        Unlike a bounce, the price doesn't reverse — it keeps
        pushing along the band.

        WALKING UPPER BAND (strong uptrend):
            3 out of last 5 candle highs are within 0.3% of
            upper band (touching or very close)

        WALKING LOWER BAND (strong downtrend):
            3 out of last 5 candle lows are within 0.3% of
            lower band (touching or very close)

        The 0.3% threshold accounts for the fact that price
        rarely sits exactly on the band.

        Args:
            df (DataFrame):     Must have 'close', 'high', 'low'
            upper (pd.Series):  Upper band values
            lower (pd.Series):  Lower band values
            periods (int):      How many candles to check (default 5)

        Returns:
            str: "WALKING_UPPER" | "WALKING_LOWER" | "NONE"
        """
        try:
            # ------ Validate inputs ------
            if df is None or df.empty:
                return "NONE"

            if upper is None or lower is None:
                return "NONE"

            required_cols = ["high", "low"]
            for col in required_cols:
                if col not in df.columns:
                    return "NONE"

            # ------ Get last N valid candles ------
            valid_mask = upper.notna() & lower.notna()
            valid_indices = valid_mask[valid_mask].index

            actual_periods = min(periods, len(valid_indices))

            if actual_periods < 3:
                return "NONE"

            recent_idx = valid_indices[-actual_periods:]

            high = df.loc[recent_idx, "high"].values.astype(float)
            low = df.loc[recent_idx, "low"].values.astype(float)
            up_vals = upper.loc[recent_idx].values.astype(float)
            lo_vals = lower.loc[recent_idx].values.astype(float)

            # ------ Proximity threshold: 0.3% of band value ------
            # This defines "touching" — within 0.3% of the band

            # ------ Check UPPER BAND walking ------
            upper_touches = 0
            for i in range(len(high)):
                if up_vals[i] == 0:
                    continue
                distance_pct = abs(high[i] - up_vals[i]) / up_vals[i] * 100.0
                if distance_pct <= 0.3 or high[i] >= up_vals[i]:
                    upper_touches += 1

            # ------ Check LOWER BAND walking ------
            lower_touches = 0
            for i in range(len(low)):
                if lo_vals[i] == 0:
                    continue
                distance_pct = abs(low[i] - lo_vals[i]) / lo_vals[i] * 100.0
                if distance_pct <= 0.3 or low[i] <= lo_vals[i]:
                    lower_touches += 1

            # ------ Determine band walk ------
            # Need 60%+ of candles touching the band
            threshold = actual_periods * 0.6

            if upper_touches >= threshold:
                print("[BOLLINGER] 📈 WALKING UPPER band "
                      "({}/{} candles touching)".format(
                          upper_touches, actual_periods
                      ))
                return "WALKING_UPPER"

            if lower_touches >= threshold:
                print("[BOLLINGER] 📉 WALKING LOWER band "
                      "({}/{} candles touching)".format(
                          lower_touches, actual_periods
                      ))
                return "WALKING_LOWER"

            return "NONE"

        except Exception as e:
            print("[BOLLINGER] ❌ Band walk detection error: {}".format(e))
            return "NONE"

    # ============================================
    # FUNCTION 9: ANALYZE (Main Entry Point)
    # ============================================

    def analyze(self, df):
        """
        MAIN ANALYSIS FUNCTION — Runs all Bollinger Band checks
        and produces a scored trading signal.

        Pipeline:
        1. Calculate bands (upper, middle, lower)
        2. Calculate %B indicator
        3. Calculate bandwidth
        4. Detect squeeze
        5. Detect bounce
        6. Detect breakout
        7. Detect band walking
        8. Calculate composite score (0-100)
        9. Determine direction and confidence

        SCORING SYSTEM:
        Base score = 50 (neutral center)

        LONG factors (add to score):
        +15  Price below lower band (oversold)
        +20  Bounce from lower band (mean reversion buy)
        +10  Squeeze detected (breakout expected)
        +15  %B below 0 (extreme oversold)
        +20  Breakout upward (trend continuation)

        SHORT factors (subtract from score):
        -15  Price above upper band (overbought)
        -20  Bounce from upper band (mean reversion sell)
        -15  %B above 1 (extreme overbought)
        -20  Breakout downward (trend continuation)

        CONTEXT adjustments:
        +5   Walking upper band (strong uptrend confirmation)
        -5   Walking lower band (strong downtrend confirmation)

        Score clamped to 0-100 range.

        DIRECTION MAPPING:
         0-30  → Strong SHORT  | confidence = (50-score) * 2
        30-45  → Weak SHORT    | confidence = (50-score) * 2
        45-55  → NEUTRAL       | confidence = 0
        55-70  → Weak LONG     | confidence = (score-50) * 2
        70-100 → Strong LONG   | confidence = (score-50) * 2

        Args:
            df (DataFrame): Price data with columns:
                           [open, high, low, close, volume]

        Returns:
            dict: {
                "brain": "BOLLINGER",
                "direction": "LONG" / "SHORT" / "NEUTRAL",
                "confidence": 0-100 (float),
                "upper_band": float,
                "middle_band": float,
                "lower_band": float,
                "percent_b": float,
                "bandwidth": float,
                "details": {
                    "squeeze": True/False,
                    "bounce": str,
                    "breakout": str,
                    "band_walk": str
                }
            }
        """
        # ------ Default neutral result ------
        neutral_result = {
            "brain": "BOLLINGER",
            "direction": "NEUTRAL",
            "confidence": 0,
            "upper_band": 0.0,
            "middle_band": 0.0,
            "lower_band": 0.0,
            "percent_b": 0.5,
            "bandwidth": 0.0,
            "details": {
                "squeeze": False,
                "bounce": "NONE",
                "breakout": "NONE",
                "band_walk": "NONE",
            },
        }

        try:
            # ============================================
            # STEP 1: Validate input DataFrame
            # ============================================
            if df is None or df.empty:
                print("[BOLLINGER] ⚠️ No data provided for analysis")
                return neutral_result

            if "close" not in df.columns:
                print("[BOLLINGER] ⚠️ 'close' column missing")
                return neutral_result

            if len(df) < self.min_data_points:
                print("[BOLLINGER] ⚠️ Need {} rows, got {}".format(
                    self.min_data_points, len(df)
                ))
                return neutral_result

            # ============================================
            # STEP 2: Calculate Bollinger Bands
            # ============================================
            bands = self.calculate_bands(df)

            if bands is None:
                print("[BOLLINGER] ⚠️ Band calculation returned None")
                return neutral_result

            upper = bands["upper"]
            middle = bands["middle"]
            lower = bands["lower"]

            # ------ Get current band values ------
            valid_upper = upper.dropna()
            valid_middle = middle.dropna()
            valid_lower = lower.dropna()

            if len(valid_upper) == 0 or len(valid_lower) == 0:
                print("[BOLLINGER] ⚠️ No valid band values")
                return neutral_result

            current_upper = float(valid_upper.iloc[-1])
            current_middle = float(valid_middle.iloc[-1])
            current_lower = float(valid_lower.iloc[-1])
            current_close = float(df["close"].iloc[-1])

            # ============================================
            # STEP 3: Calculate %B
            # ============================================
            close_series = df["close"].astype(float)
            percent_b_series = self.calculate_percent_b(
                close_series, upper, lower
            )

            current_percent_b = 0.5  # default
            if percent_b_series is not None:
                valid_pb = percent_b_series.dropna()
                if len(valid_pb) > 0:
                    current_percent_b = float(valid_pb.iloc[-1])

            # ============================================
            # STEP 4: Calculate Bandwidth
            # ============================================
            bandwidth_series = self.calculate_bandwidth(
                upper, lower, middle
            )

            current_bandwidth = 0.0
            if bandwidth_series is not None:
                valid_bw = bandwidth_series.dropna()
                if len(valid_bw) > 0:
                    current_bandwidth = float(valid_bw.iloc[-1])

            # ============================================
            # STEP 5: Run all sub-analyses
            # ============================================

            # 5a: Squeeze detection
            squeeze_result = self.detect_squeeze(bandwidth_series, lookback=50)
            is_squeeze = squeeze_result["is_squeeze"]

            # 5b: Bounce detection
            bounce = self.detect_bounce(df, upper, lower)

            # 5c: Breakout detection
            breakout = self.detect_breakout(df, upper, lower)

            # 5d: Band walk detection
            band_walk = self.detect_band_walk(df, upper, lower, periods=5)

            # 5e: Price position relative to bands
            price_above_upper = current_close > current_upper
            price_below_lower = current_close < current_lower

            # ============================================
            # STEP 6: Calculate composite score
            # ============================================
            score = 50.0  # Neutral center

            # ------ LONG factors (add to score) ------

            # Price below lower band: +15 (oversold)
            if price_below_lower:
                score += 15.0
                print("[BOLLINGER] 📈 +15 pts | Price BELOW lower band")

            # Bounce from lower band: +20
            if bounce == "BOUNCE_LOWER":
                score += 20.0
                print("[BOLLINGER] 📈 +20 pts | BOUNCE from lower band")

            # Squeeze detected: +10 (breakout pending)
            if is_squeeze:
                score += 10.0
                print("[BOLLINGER] 📈 +10 pts | SQUEEZE detected")

            # %B below 0: +15 (extreme oversold)
            if current_percent_b < 0.0:
                score += 15.0
                print("[BOLLINGER] 📈 +15 pts | %%B below 0 "
                      "({:.2f})".format(current_percent_b))

            # Breakout upward: +20
            if breakout == "BREAKOUT_UP":
                score += 20.0
                print("[BOLLINGER] 📈 +20 pts | BREAKOUT UP")

            # ------ SHORT factors (subtract from score) ------

            # Price above upper band: -15 (overbought)
            if price_above_upper:
                score -= 15.0
                print("[BOLLINGER] 📉 -15 pts | Price ABOVE upper band")

            # Bounce from upper band: -20
            if bounce == "BOUNCE_UPPER":
                score -= 20.0
                print("[BOLLINGER] 📉 -20 pts | BOUNCE from upper band")

            # %B above 1: -15 (extreme overbought)
            if current_percent_b > 1.0:
                score -= 15.0
                print("[BOLLINGER] 📉 -15 pts | %%B above 1 "
                      "({:.2f})".format(current_percent_b))

            # Breakout downward: -20
            if breakout == "BREAKOUT_DOWN":
                score -= 20.0
                print("[BOLLINGER] 📉 -20 pts | BREAKOUT DOWN")

            # ------ CONTEXT adjustments ------

            # Walking upper band: +5 (trend continuation)
            if band_walk == "WALKING_UPPER":
                score += 5.0
                print("[BOLLINGER] 📈 + 5 pts | Walking UPPER band")

            # Walking lower band: -5 (trend continuation)
            if band_walk == "WALKING_LOWER":
                score -= 5.0
                print("[BOLLINGER] 📉 - 5 pts | Walking LOWER band")

            # ============================================
            # STEP 7: Clamp score to 0-100
            # ============================================
            score = max(0.0, min(100.0, score))

            # ============================================
            # STEP 8: Determine direction and confidence
            # ============================================

            if score < 30:
                direction = "SHORT"
                confidence = (50.0 - score) * 2.0

            elif score < 45:
                direction = "SHORT"
                confidence = (50.0 - score) * 2.0

            elif score <= 55:
                direction = "NEUTRAL"
                confidence = 0.0

            elif score <= 70:
                direction = "LONG"
                confidence = (score - 50.0) * 2.0

            else:
                direction = "LONG"
                confidence = (score - 50.0) * 2.0

            # Clamp confidence
            confidence = max(0.0, min(100.0, round(confidence, 2)))

            # ============================================
            # STEP 9: Build result dictionary
            # ============================================
            result = {
                "brain": "BOLLINGER",
                "direction": direction,
                "confidence": confidence,
                "upper_band": round(current_upper, 6),
                "middle_band": round(current_middle, 6),
                "lower_band": round(current_lower, 6),
                "percent_b": round(current_percent_b, 4),
                "bandwidth": round(current_bandwidth, 4),
                "details": {
                    "squeeze": is_squeeze,
                    "bounce": bounce,
                    "breakout": breakout,
                    "band_walk": band_walk,
                },
            }

            # Store for later reference
            self.results = result

            # ============================================
            # STEP 10: Log the analysis summary
            # ============================================
            print("\n[BOLLINGER] ═══════════════════════════════════")
            print("[BOLLINGER]  Bollinger Analysis Complete")
            print("[BOLLINGER]  Upper Band  : {:.4f}".format(current_upper))
            print("[BOLLINGER]  Middle Band : {:.4f}".format(current_middle))
            print("[BOLLINGER]  Lower Band  : {:.4f}".format(current_lower))
            print("[BOLLINGER]  Close Price : {:.4f}".format(current_close))
            print("[BOLLINGER]  %B          : {:.4f}".format(current_percent_b))
            print("[BOLLINGER]  Bandwidth   : {:.4f}%".format(current_bandwidth))
            print("[BOLLINGER]  Squeeze     : {}".format(
                "YES (strength {})".format(squeeze_result["squeeze_strength"])
                if is_squeeze else "No"
            ))
            print("[BOLLINGER]  Bounce      : {}".format(bounce))
            print("[BOLLINGER]  Breakout    : {}".format(breakout))
            print("[BOLLINGER]  Band Walk   : {}".format(band_walk))
            print("[BOLLINGER]  Raw Score   : {:.1f}/100".format(score))
            print("[BOLLINGER]  Direction   : {}".format(direction))
            print("[BOLLINGER]  Confidence  : {:.1f}%".format(confidence))
            print("[BOLLINGER] ═══════════════════════════════════\n")

            return result

        except Exception as e:
            print("[BOLLINGER] ❌ Analysis error: {}".format(e))
            return neutral_result


# ==================================================
# MODULE-LEVEL SINGLETON INSTANCE
# ==================================================
# Every module imports this same instance:
#
#   from algorithms.bollinger import bollinger_analyzer
#   result = bollinger_analyzer.analyze(dataframe)
# ==================================================

bollinger_analyzer = BollingerAnalyzer()

print("[BOLLINGER] ✅ Bollinger module loaded and ready")