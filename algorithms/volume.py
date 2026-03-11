# ============================================
# CRYPTO SIGNAL BOT - VOLUME ANALYZER
# ============================================
# Brain #4 of 4: Volume Analysis
#
# Volume is the CONFIRMATION brain. It validates
# signals from RSI, MACD, and Bollinger Bands.
# A signal without volume support is weak.
#
# Key principles:
#   High volume + price up   → STRONG bullish
#   High volume + price down → STRONG bearish
#   Low volume + price up    → WEAK move (may reverse)
#   Low volume + price down  → WEAK move (may reverse)
#   Volume spike             → something significant
#   Volume drying up         → trend exhaustion
#
# Indicators calculated FROM SCRATCH:
#   - Volume Moving Average
#   - Volume Ratio (current vs average)
#   - On-Balance Volume (OBV)
#   - Accumulation/Distribution (A/D)
#   - Volume Spike Detection
#   - Volume Trend Direction
#   - Volume Climax Detection
#   - Volume-Price Confirmation
#
# No external TA library used.
#
# Usage:
#   from algorithms.volume import volume_analyzer
#   result = volume_analyzer.analyze(dataframe)
# ============================================

import numpy as np
import pandas as pd
from config.settings import Config


class VolumeAnalyzer:
    """
    Volume-based trading signal analyzer.

    Acts as a CONFIRMATION brain that validates
    signals from other technical indicators.
    Calculates OBV, A/D, volume spikes, and
    volume-price divergences to produce a scored
    signal with direction and confidence.

    Attributes:
        ma_period (int):  Volume moving average period (default 20)
        results (dict):   Stores latest analysis results
    """

    # ============================================
    # FUNCTION 1: __init__
    # ============================================

    def __init__(self, ma_period=None):
        """
        Initialize the Volume Analyzer.

        Args:
            ma_period (int): Volume MA period.
                            Uses Config.VOLUME_MA_PERIOD if not given.
        """
        # ------ Period from Config or argument ------
        self.ma_period = (
            ma_period if ma_period is not None
            else Config.VOLUME_MA_PERIOD
        )

        # ------ Minimum data needed ------
        # Need ma_period candles for first MA value
        # plus buffer for trend and OBV analysis
        self.min_data_points = self.ma_period + 5

        # ------ Storage for latest results ------
        self.results = {}

        print("[VOLUME] ✅ Analyzer initialized | "
              "MA Period: {}".format(self.ma_period))

    # ============================================
    # FUNCTION 2: CALCULATE VOLUME MA
    # ============================================

    def calculate_volume_ma(self, volume_series):
        """
        Calculates Simple Moving Average of volume.

        SMA[i] = mean(volume[i-period+1 : i+1])

        This provides the baseline "normal" volume level.
        Current volume is compared against this average
        to detect unusual activity.

        Args:
            volume_series (pd.Series): Raw volume data (float)

        Returns:
            pd.Series: Volume SMA with same index.
                      First (period-1) values are NaN.
                      Returns None on error.
        """
        try:
            # ------ Validate input ------
            if volume_series is None or len(volume_series) == 0:
                print("[VOLUME] ⚠️ Empty volume data received")
                return None

            if len(volume_series) < self.ma_period:
                print("[VOLUME] ⚠️ Need {} volume points, "
                      "got {}".format(self.ma_period, len(volume_series)))
                return None

            # ------ Convert to numpy for speed ------
            values = volume_series.astype(float).values
            data_length = len(values)

            # ------ Pre-allocate with NaN ------
            ma_values = np.full(data_length, np.nan, dtype=np.float64)

            # ------ Calculate rolling SMA ------
            for i in range(self.ma_period - 1, data_length):
                window = values[i - self.ma_period + 1: i + 1]
                valid = window[~np.isnan(window)]
                if len(valid) > 0:
                    ma_values[i] = np.mean(valid)

            # ------ Build Series ------
            vol_ma = pd.Series(
                ma_values,
                index=volume_series.index,
                name="Volume_MA",
                dtype=np.float64,
            )

            return vol_ma

        except Exception as e:
            print("[VOLUME] ❌ Volume MA error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 3: CALCULATE VOLUME RATIO
    # ============================================

    def calculate_volume_ratio(self, current_volume, avg_volume):
        """
        Calculates ratio of current volume to average volume.

        Interpretation:
            > 2.0  → Volume spike (very unusual)
            > 1.5  → Above average (notable)
            0.8-1.2 → Normal range
            0.5-0.8 → Below average (quiet)
            < 0.5  → Very low volume (no interest)

        Args:
            current_volume (float): Current candle volume
            avg_volume (float):     Average volume (from MA)

        Returns:
            float: Volume ratio, or 0.0 on error
        """
        try:
            if current_volume is None or avg_volume is None:
                return 0.0

            current_volume = float(current_volume)
            avg_volume = float(avg_volume)

            # Avoid division by zero
            if avg_volume <= 0:
                return 0.0

            ratio = current_volume / avg_volume
            return round(ratio, 4)

        except (ValueError, TypeError) as e:
            print("[VOLUME] ❌ Volume ratio error: {}".format(e))
            return 0.0

    # ============================================
    # FUNCTION 4: CALCULATE OBV (On-Balance Volume)
    # ============================================

    def calculate_obv(self, df):
        """
        Calculates On-Balance Volume from scratch.

        OBV is a cumulative running total that adds
        or subtracts volume based on price direction:

        Rule:
            If close[i] > close[i-1] → OBV += volume[i]
            If close[i] < close[i-1] → OBV -= volume[i]
            If close[i] == close[i-1] → OBV unchanged

        Rising OBV = accumulation (buying pressure)
        Falling OBV = distribution (selling pressure)
        OBV divergence from price = potential reversal

        Args:
            df (DataFrame): Must have 'close' and 'volume' columns

        Returns:
            pd.Series: OBV values, or None on error
        """
        try:
            # ------ Validate input ------
            if df is None or df.empty:
                return None

            if "close" not in df.columns or "volume" not in df.columns:
                print("[VOLUME] ⚠️ 'close' or 'volume' column missing")
                return None

            close = df["close"].astype(float).values
            volume = df["volume"].astype(float).values
            data_length = len(close)

            if data_length < 2:
                return None

            # ------ Pre-allocate OBV array ------
            obv_values = np.zeros(data_length, dtype=np.float64)

            # First OBV value = first volume
            obv_values[0] = volume[0]

            # ------ Calculate OBV ------
            for i in range(1, data_length):
                if np.isnan(close[i]) or np.isnan(close[i - 1]):
                    obv_values[i] = obv_values[i - 1]
                elif np.isnan(volume[i]):
                    obv_values[i] = obv_values[i - 1]
                elif close[i] > close[i - 1]:
                    # Price went UP → add volume
                    obv_values[i] = obv_values[i - 1] + volume[i]
                elif close[i] < close[i - 1]:
                    # Price went DOWN → subtract volume
                    obv_values[i] = obv_values[i - 1] - volume[i]
                else:
                    # Price unchanged → OBV stays same
                    obv_values[i] = obv_values[i - 1]

            # ------ Build Series ------
            obv = pd.Series(
                obv_values,
                index=df.index,
                name="OBV",
                dtype=np.float64,
            )

            return obv

        except Exception as e:
            print("[VOLUME] ❌ OBV calculation error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 5: DETECT VOLUME SPIKE
    # ============================================

    def detect_volume_spike(self, volume_series, threshold=2.0):
        """
        Detects if current volume is a spike (abnormally high).

        A volume spike indicates significant market activity:
        - Institutional buying or selling
        - News event reaction
        - Breakout confirmation
        - Potential reversal at extremes

        Compares the latest volume against the MA of volume.
        If ratio exceeds threshold, it's a spike.

        Spike magnitude shows HOW extreme the spike is:
            magnitude = (ratio - threshold) / threshold × 100
            Higher magnitude = more extreme spike

        Args:
            volume_series (pd.Series): Raw volume data
            threshold (float):        Spike multiplier (default 2.0x)

        Returns:
            dict: {
                "is_spike": True/False,
                "spike_magnitude": 0-100+,
                "volume_ratio": float
            }
        """
        default_result = {
            "is_spike": False,
            "spike_magnitude": 0,
            "volume_ratio": 0.0,
        }

        try:
            if volume_series is None or len(volume_series) == 0:
                return default_result

            # ------ Calculate volume MA ------
            vol_ma = self.calculate_volume_ma(volume_series)

            if vol_ma is None:
                return default_result

            valid_ma = vol_ma.dropna()
            if len(valid_ma) == 0:
                return default_result

            # ------ Get current values ------
            current_volume = float(volume_series.iloc[-1])
            avg_volume = float(valid_ma.iloc[-1])

            # ------ Calculate ratio ------
            ratio = self.calculate_volume_ratio(current_volume, avg_volume)

            # ------ Check for spike ------
            is_spike = ratio >= threshold

            # ------ Calculate magnitude ------
            if is_spike:
                magnitude = min(
                    100.0,
                    ((ratio - threshold) / threshold) * 100.0
                )
                print("[VOLUME] 📊 SPIKE detected | "
                      "Ratio: {:.2f}x | Magnitude: {:.0f}".format(
                          ratio, magnitude
                      ))
            else:
                magnitude = 0.0

            return {
                "is_spike": is_spike,
                "spike_magnitude": round(magnitude, 2),
                "volume_ratio": ratio,
            }

        except Exception as e:
            print("[VOLUME] ❌ Spike detection error: {}".format(e))
            return default_result

    # ============================================
    # FUNCTION 6: DETECT VOLUME TREND
    # ============================================

    def detect_volume_trend(self, volume_series, periods=10):
        """
        Determines if volume is trending up, down, or stable.

        Checks the volume MA over the last N periods.
        Uses net change + consistency (same approach as RSI trend).

        INCREASING: volume growing → market interest rising
        DECREASING: volume shrinking → market interest fading
        STABLE: volume roughly unchanged

        Args:
            volume_series (pd.Series): Raw volume data
            periods (int):            Lookback window (default 10)

        Returns:
            str: "INCREASING" | "DECREASING" | "STABLE"
        """
        try:
            if volume_series is None or len(volume_series) == 0:
                return "STABLE"

            # ------ Calculate volume MA for smoother trend ------
            vol_ma = self.calculate_volume_ma(volume_series)

            if vol_ma is None:
                return "STABLE"

            valid_ma = vol_ma.dropna()

            if len(valid_ma) < 3:
                return "STABLE"

            # ------ Get last N values ------
            actual_periods = min(periods, len(valid_ma))
            last_n = valid_ma.iloc[-actual_periods:]

            # ------ Net change ------
            first_val = float(last_n.iloc[0])
            last_val = float(last_n.iloc[-1])

            if first_val == 0:
                return "STABLE"

            net_change_pct = ((last_val - first_val) / first_val) * 100.0

            # ------ Consistency check ------
            diffs = last_n.diff().dropna()

            if len(diffs) == 0:
                return "STABLE"

            rising_count = (diffs > 0).sum()
            falling_count = (diffs < 0).sum()
            total = len(diffs)

            consistency_threshold = 0.55  # 55% same direction

            # ------ Determine trend ------
            # Net change > 10% AND mostly rising
            if (net_change_pct > 10.0 and
                    rising_count >= total * consistency_threshold):
                return "INCREASING"

            # Net change < -10% AND mostly falling
            if (net_change_pct < -10.0 and
                    falling_count >= total * consistency_threshold):
                return "DECREASING"

            return "STABLE"

        except Exception as e:
            print("[VOLUME] ❌ Volume trend error: {}".format(e))
            return "STABLE"

    # ============================================
    # FUNCTION 7: DETECT VOLUME CLIMAX
    # ============================================

    def detect_volume_climax(self, df):
        """
        Detects volume climax events.

        A volume climax occurs when EXTREME volume appears
        at EXTREME price levels. This often signals exhaustion
        and a potential reversal.

        BUYING CLIMAX (potential top):
            - Volume spike (> 2.5x average)
            - Price near recent high (top 10% of range)
            - Often followed by price reversal DOWN

        SELLING CLIMAX (potential bottom):
            - Volume spike (> 2.5x average)
            - Price near recent low (bottom 10% of range)
            - Often followed by price reversal UP

        Note: Climax signals are CONTRARIAN — they suggest
        the current trend is exhausting itself.

        Args:
            df (DataFrame): Must have 'close', 'high', 'low', 'volume'

        Returns:
            str: "BUYING_CLIMAX" | "SELLING_CLIMAX" | "NONE"
        """
        try:
            # ------ Validate input ------
            if df is None or df.empty:
                return "NONE"

            required = ["close", "high", "low", "volume"]
            for col in required:
                if col not in df.columns:
                    return "NONE"

            if len(df) < self.ma_period + 5:
                return "NONE"

            # ------ Get recent data for price range ------
            lookback = min(50, len(df))
            recent_df = df.iloc[-lookback:]

            close = recent_df["close"].astype(float)
            volume = recent_df["volume"].astype(float)

            current_close = float(close.iloc[-1])
            price_high = float(close.max())
            price_low = float(close.min())
            price_range = price_high - price_low

            if price_range == 0:
                return "NONE"

            # ------ Check volume spike (2.5x threshold) ------
            spike = self.detect_volume_spike(volume, threshold=2.5)

            if not spike["is_spike"]:
                return "NONE"

            # ------ Check price position ------
            # Percentage of price range (0 = at low, 100 = at high)
            price_position = (
                (current_close - price_low) / price_range
            ) * 100.0

            # ------ BUYING CLIMAX: extreme volume at high prices ------
            # Price in top 10% of range + volume spike
            if price_position >= 90:
                print("[VOLUME] 🔴 BUYING CLIMAX detected | "
                      "Price at {:.0f}% of range | "
                      "Volume {:.1f}x avg".format(
                          price_position, spike["volume_ratio"]
                      ))
                return "BUYING_CLIMAX"

            # ------ SELLING CLIMAX: extreme volume at low prices ------
            # Price in bottom 10% of range + volume spike
            if price_position <= 10:
                print("[VOLUME] 🟢 SELLING CLIMAX detected | "
                      "Price at {:.0f}% of range | "
                      "Volume {:.1f}x avg".format(
                          price_position, spike["volume_ratio"]
                      ))
                return "SELLING_CLIMAX"

            return "NONE"

        except Exception as e:
            print("[VOLUME] ❌ Volume climax error: {}".format(e))
            return "NONE"

    # ============================================
    # FUNCTION 8: ACCUMULATION/DISTRIBUTION
    # ============================================

    def calculate_accumulation_distribution(self, df):
        """
        Calculates the Accumulation/Distribution (A/D) line.

        The A/D line measures the cumulative flow of money
        into and out of an asset.

        Formula per candle:
            Money Flow Multiplier (MFM):
                MFM = ((Close - Low) - (High - Close)) / (High - Low)
                Range: -1 to +1
                Close at High → MFM = +1 (all accumulation)
                Close at Low  → MFM = -1 (all distribution)
                Close at Mid  → MFM = 0  (neutral)

            Money Flow Volume (MFV):
                MFV = MFM × Volume

            A/D Line:
                A/D[i] = A/D[i-1] + MFV[i]

        Rising A/D = accumulation (smart money buying)
        Falling A/D = distribution (smart money selling)

        Args:
            df (DataFrame): Must have 'close', 'high', 'low', 'volume'

        Returns:
            pd.Series: Cumulative A/D line, or None on error
        """
        try:
            # ------ Validate input ------
            if df is None or df.empty:
                return None

            required = ["close", "high", "low", "volume"]
            for col in required:
                if col not in df.columns:
                    print("[VOLUME] ⚠️ '{}' column missing for A/D".format(col))
                    return None

            close = df["close"].astype(float).values
            high = df["high"].astype(float).values
            low = df["low"].astype(float).values
            volume = df["volume"].astype(float).values
            data_length = len(close)

            if data_length < 2:
                return None

            # ------ Pre-allocate A/D array ------
            ad_values = np.zeros(data_length, dtype=np.float64)

            for i in range(data_length):
                # Skip NaN values
                if (np.isnan(close[i]) or np.isnan(high[i]) or
                        np.isnan(low[i]) or np.isnan(volume[i])):
                    ad_values[i] = ad_values[i - 1] if i > 0 else 0.0
                    continue

                hl_range = high[i] - low[i]

                if hl_range == 0:
                    # No price range → no flow
                    mfm = 0.0
                else:
                    # Money Flow Multiplier
                    mfm = ((close[i] - low[i]) - (high[i] - close[i])) / hl_range

                # Money Flow Volume
                mfv = mfm * volume[i]

                # Cumulative A/D
                if i == 0:
                    ad_values[i] = mfv
                else:
                    ad_values[i] = ad_values[i - 1] + mfv

            # ------ Build Series ------
            ad_line = pd.Series(
                ad_values,
                index=df.index,
                name="AD_Line",
                dtype=np.float64,
            )

            return ad_line

        except Exception as e:
            print("[VOLUME] ❌ A/D calculation error: {}".format(e))
            return None

    # ============================================
    # FUNCTION 9: VOLUME PRICE CONFIRMATION
    # ============================================

    def volume_price_confirmation(self, df):
        """
        Checks if volume confirms the current price direction.

        This is the CORE of volume analysis. Volume should
        increase in the direction of the trend. If it doesn't,
        the trend may be weak or about to reverse.

        CONFIRMED_BULLISH:
            Price rising (last 3 closes trending up)
            AND volume rising or above average
            → Strong bullish — trend is real

        CONFIRMED_BEARISH:
            Price falling (last 3 closes trending down)
            AND volume rising or above average
            → Strong bearish — trend is real

        DIVERGENCE_BULLISH:
            Price falling
            BUT volume decreasing
            → Sellers losing steam, reversal UP possible

        DIVERGENCE_BEARISH:
            Price rising
            BUT volume decreasing
            → Buyers losing steam, reversal DOWN possible

        Args:
            df (DataFrame): Must have 'close' and 'volume'

        Returns:
            str: "CONFIRMED_BULLISH" | "CONFIRMED_BEARISH" |
                 "DIVERGENCE_BULLISH" | "DIVERGENCE_BEARISH" |
                 "NEUTRAL"
        """
        try:
            # ------ Validate input ------
            if df is None or df.empty:
                return "NEUTRAL"

            if "close" not in df.columns or "volume" not in df.columns:
                return "NEUTRAL"

            if len(df) < self.ma_period + 3:
                return "NEUTRAL"

            # ------ Get price direction (last 5 candles) ------
            close = df["close"].astype(float)
            last_5 = close.iloc[-5:]

            price_change = float(last_5.iloc[-1]) - float(last_5.iloc[0])

            # Threshold: at least 0.1% price change to matter
            price_pct = abs(price_change) / float(last_5.iloc[0]) * 100.0

            if price_pct < 0.1:
                return "NEUTRAL"

            price_rising = price_change > 0
            price_falling = price_change < 0

            # ------ Get volume direction ------
            volume = df["volume"].astype(float)
            vol_ma = self.calculate_volume_ma(volume)

            if vol_ma is None:
                return "NEUTRAL"

            valid_ma = vol_ma.dropna()
            if len(valid_ma) < 3:
                return "NEUTRAL"

            current_vol = float(volume.iloc[-1])
            avg_vol = float(valid_ma.iloc[-1])

            # Volume ratio
            vol_ratio = self.calculate_volume_ratio(current_vol, avg_vol)
            volume_above_avg = vol_ratio >= 1.0

            # Volume trend over last 5 candles
            last_5_vol = volume.iloc[-5:]
            vol_change = float(last_5_vol.iloc[-1]) - float(last_5_vol.iloc[0])
            volume_rising = vol_change > 0

            # ------ Determine confirmation ------

            # Price UP + Volume UP/above avg → CONFIRMED BULLISH
            if price_rising and (volume_rising or volume_above_avg):
                print("[VOLUME] ✅ CONFIRMED BULLISH | "
                      "Price ↑ + Volume ↑ | "
                      "Ratio: {:.2f}x".format(vol_ratio))
                return "CONFIRMED_BULLISH"

            # Price DOWN + Volume UP/above avg → CONFIRMED BEARISH
            if price_falling and (volume_rising or volume_above_avg):
                print("[VOLUME] ✅ CONFIRMED BEARISH | "
                      "Price ↓ + Volume ↑ | "
                      "Ratio: {:.2f}x".format(vol_ratio))
                return "CONFIRMED_BEARISH"

            # Price DOWN + Volume DOWN → DIVERGENCE BULLISH
            # (Sellers losing momentum → potential reversal UP)
            if price_falling and not volume_rising and not volume_above_avg:
                print("[VOLUME] 🔄 DIVERGENCE BULLISH | "
                      "Price ↓ but Volume ↓ | "
                      "Ratio: {:.2f}x".format(vol_ratio))
                return "DIVERGENCE_BULLISH"

            # Price UP + Volume DOWN → DIVERGENCE BEARISH
            # (Buyers losing momentum → potential reversal DOWN)
            if price_rising and not volume_rising and not volume_above_avg:
                print("[VOLUME] 🔄 DIVERGENCE BEARISH | "
                      "Price ↑ but Volume ↓ | "
                      "Ratio: {:.2f}x".format(vol_ratio))
                return "DIVERGENCE_BEARISH"

            return "NEUTRAL"

        except Exception as e:
            print("[VOLUME] ❌ Volume-price confirmation error: {}".format(e))
            return "NEUTRAL"

    # ============================================
    # HELPER: GET OBV TREND
    # ============================================

    def _get_obv_trend(self, obv_series, periods=10):
        """
        Determines OBV direction over last N periods.

        Uses net change + consistency check.

        Args:
            obv_series (pd.Series): OBV values
            periods (int):         Lookback (default 10)

        Returns:
            str: "RISING" | "FALLING" | "FLAT"
        """
        try:
            if obv_series is None or len(obv_series) < 3:
                return "FLAT"

            valid_obv = obv_series.dropna()
            if len(valid_obv) < 3:
                return "FLAT"

            actual = min(periods, len(valid_obv))
            last_n = valid_obv.iloc[-actual:]

            first_val = float(last_n.iloc[0])
            last_val = float(last_n.iloc[-1])

            # Net change
            net_change = last_val - first_val

            # Consistency
            diffs = last_n.diff().dropna()
            if len(diffs) == 0:
                return "FLAT"

            rising = (diffs > 0).sum()
            falling = (diffs < 0).sum()
            total = len(diffs)

            # OBV rising: net positive AND > 55% candles rising
            if net_change > 0 and rising >= total * 0.55:
                return "RISING"

            # OBV falling: net negative AND > 55% candles falling
            if net_change < 0 and falling >= total * 0.55:
                return "FALLING"

            return "FLAT"

        except Exception as e:
            print("[VOLUME] ❌ OBV trend error: {}".format(e))
            return "FLAT"

    # ============================================
    # HELPER: GET A/D TREND
    # ============================================

    def _get_ad_trend(self, ad_series, periods=10):
        """
        Determines Accumulation/Distribution trend.

        Args:
            ad_series (pd.Series): A/D line values
            periods (int):        Lookback (default 10)

        Returns:
            str: "ACCUMULATION" | "DISTRIBUTION" | "NEUTRAL"
        """
        try:
            if ad_series is None or len(ad_series) < 3:
                return "NEUTRAL"

            actual = min(periods, len(ad_series))
            last_n = ad_series.iloc[-actual:]

            first_val = float(last_n.iloc[0])
            last_val = float(last_n.iloc[-1])

            net_change = last_val - first_val

            # Consistency check
            diffs = last_n.diff().dropna()
            if len(diffs) == 0:
                return "NEUTRAL"

            rising = (diffs > 0).sum()
            falling = (diffs < 0).sum()
            total = len(diffs)

            if net_change > 0 and rising >= total * 0.55:
                return "ACCUMULATION"

            if net_change < 0 and falling >= total * 0.55:
                return "DISTRIBUTION"

            return "NEUTRAL"

        except Exception as e:
            print("[VOLUME] ❌ A/D trend error: {}".format(e))
            return "NEUTRAL"

    # ============================================
    # FUNCTION 10: ANALYZE (Main Entry Point)
    # ============================================

    def analyze(self, df):
        """
        MAIN ANALYSIS FUNCTION — Runs all volume checks and
        produces a scored trading signal.

        This brain is SPECIAL — it acts as a CONFIRMATION
        brain. Its signals validate or invalidate the signals
        from RSI, MACD, and Bollinger Bands.

        Pipeline:
        1. Calculate volume MA and ratio
        2. Detect volume spikes
        3. Detect volume trend
        4. Calculate OBV and its trend
        5. Calculate A/D line and its trend
        6. Detect volume climax
        7. Check volume-price confirmation
        8. Calculate composite score (0-100)
        9. Determine direction and confidence

        SCORING SYSTEM:
        Base score = 50 (neutral center)

        LONG factors (add to score):
        +15  Volume above avg + price rising (confirmed bullish)
        +20  Volume spike + price rising
        +10  OBV rising (accumulation pressure)
        +10  A/D line accumulation
        +15  Volume confirmed bullish
        +10  Selling climax (contrarian reversal UP signal)

        SHORT factors (subtract from score):
        -15  Volume above avg + price falling (confirmed bearish)
        -20  Volume spike + price falling
        -10  OBV falling (distribution pressure)
        -10  A/D line distribution
        -15  Volume confirmed bearish
        -10  Buying climax (contrarian reversal DOWN signal)

        LOW VOLUME (score stays near 50):
            No volume confirmation → neutral, no adjustments

        Score clamped to 0-100.

        DIRECTION MAPPING:
         0-30  → Strong SHORT  | confidence = (50-score)*2
        30-45  → Weak SHORT    | confidence = (50-score)*2
        45-55  → NEUTRAL       | confidence = 0
        55-70  → Weak LONG     | confidence = (score-50)*2
        70-100 → Strong LONG   | confidence = (score-50)*2

        Args:
            df (DataFrame): Price data with columns:
                           [open, high, low, close, volume]

        Returns:
            dict: Standard brain result format
        """
        # ------ Default neutral result ------
        neutral_result = {
            "brain": "VOLUME",
            "direction": "NEUTRAL",
            "confidence": 0,
            "current_volume": 0.0,
            "avg_volume": 0.0,
            "volume_ratio": 0.0,
            "obv_trend": "FLAT",
            "details": {
                "spike": False,
                "trend": "STABLE",
                "climax": "NONE",
                "confirmation": "NEUTRAL",
                "ad_trend": "NEUTRAL",
            },
        }

        try:
            # ============================================
            # STEP 1: Validate input DataFrame
            # ============================================
            if df is None or df.empty:
                print("[VOLUME] ⚠️ No data provided for analysis")
                return neutral_result

            required_cols = ["close", "high", "low", "volume"]
            for col in required_cols:
                if col not in df.columns:
                    print("[VOLUME] ⚠️ '{}' column missing".format(col))
                    return neutral_result

            if len(df) < self.min_data_points:
                print("[VOLUME] ⚠️ Need {} rows, got {}".format(
                    self.min_data_points, len(df)
                ))
                return neutral_result

            # ============================================
            # STEP 2: Volume MA and ratio
            # ============================================
            volume_series = df["volume"].astype(float)
            vol_ma = self.calculate_volume_ma(volume_series)

            current_volume = float(volume_series.iloc[-1])
            avg_volume = 0.0

            if vol_ma is not None:
                valid_ma = vol_ma.dropna()
                if len(valid_ma) > 0:
                    avg_volume = float(valid_ma.iloc[-1])

            vol_ratio = self.calculate_volume_ratio(current_volume, avg_volume)
            volume_above_avg = vol_ratio >= 1.0

            # ============================================
            # STEP 3: Price direction (needed for scoring)
            # ============================================
            close = df["close"].astype(float)
            last_5_close = close.iloc[-5:] if len(close) >= 5 else close

            price_change = float(last_5_close.iloc[-1]) - float(last_5_close.iloc[0])
            price_rising = price_change > 0
            price_falling = price_change < 0

            # ============================================
            # STEP 4: Run all sub-analyses
            # ============================================

            # 4a: Volume spike
            spike_result = self.detect_volume_spike(volume_series)
            is_spike = spike_result["is_spike"]

            # 4b: Volume trend
            vol_trend = self.detect_volume_trend(volume_series, periods=10)

            # 4c: OBV
            obv = self.calculate_obv(df)
            obv_trend = self._get_obv_trend(obv, periods=10)

            # 4d: Accumulation/Distribution
            ad_line = self.calculate_accumulation_distribution(df)
            ad_trend = self._get_ad_trend(ad_line, periods=10)

            # 4e: Volume climax
            climax = self.detect_volume_climax(df)

            # 4f: Volume-price confirmation
            confirmation = self.volume_price_confirmation(df)

            # ============================================
            # STEP 5: Calculate composite score
            # ============================================
            score = 50.0

            # ------ LONG factors (add to score) ------

            # Volume above avg + price rising: +15
            if volume_above_avg and price_rising:
                score += 15.0
                print("[VOLUME] 📈 +15 pts | Volume above avg + price rising")

            # Volume spike + price rising: +20
            if is_spike and price_rising:
                score += 20.0
                print("[VOLUME] 📈 +20 pts | Volume SPIKE + price rising")

            # OBV rising: +10
            if obv_trend == "RISING":
                score += 10.0
                print("[VOLUME] 📈 +10 pts | OBV RISING")

            # Accumulation: +10
            if ad_trend == "ACCUMULATION":
                score += 10.0
                print("[VOLUME] 📈 +10 pts | ACCUMULATION detected")

            # Confirmed bullish: +15
            if confirmation == "CONFIRMED_BULLISH":
                score += 15.0
                print("[VOLUME] 📈 +15 pts | CONFIRMED BULLISH")

            # Selling climax (contrarian → reversal UP): +10
            if climax == "SELLING_CLIMAX":
                score += 10.0
                print("[VOLUME] 📈 +10 pts | SELLING CLIMAX "
                      "(reversal up expected)")

            # ------ SHORT factors (subtract from score) ------

            # Volume above avg + price falling: -15
            if volume_above_avg and price_falling:
                score -= 15.0
                print("[VOLUME] 📉 -15 pts | Volume above avg + price falling")

            # Volume spike + price falling: -20
            if is_spike and price_falling:
                score -= 20.0
                print("[VOLUME] 📉 -20 pts | Volume SPIKE + price falling")

            # OBV falling: -10
            if obv_trend == "FALLING":
                score -= 10.0
                print("[VOLUME] 📉 -10 pts | OBV FALLING")

            # Distribution: -10
            if ad_trend == "DISTRIBUTION":
                score -= 10.0
                print("[VOLUME] 📉 -10 pts | DISTRIBUTION detected")

            # Confirmed bearish: -15
            if confirmation == "CONFIRMED_BEARISH":
                score -= 15.0
                print("[VOLUME] 📉 -15 pts | CONFIRMED BEARISH")

            # Buying climax (contrarian → reversal DOWN): -10
            if climax == "BUYING_CLIMAX":
                score -= 10.0
                print("[VOLUME] 📉 -10 pts | BUYING CLIMAX "
                      "(reversal down expected)")

            # ============================================
            # STEP 6: Clamp score to 0-100
            # ============================================
            score = max(0.0, min(100.0, score))

            # ============================================
            # STEP 7: Determine direction and confidence
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
            # STEP 8: Build result dictionary
            # ============================================
            result = {
                "brain": "VOLUME",
                "direction": direction,
                "confidence": confidence,
                "current_volume": round(current_volume, 2),
                "avg_volume": round(avg_volume, 2),
                "volume_ratio": vol_ratio,
                "obv_trend": obv_trend,
                "details": {
                    "spike": is_spike,
                    "trend": vol_trend,
                    "climax": climax,
                    "confirmation": confirmation,
                    "ad_trend": ad_trend,
                },
            }

            # Store for later reference
            self.results = result

            # ============================================
            # STEP 9: Log the analysis summary
            # ============================================
            print("\n[VOLUME] ═══════════════════════════════════")
            print("[VOLUME]  Volume Analysis Complete")
            print("[VOLUME]  Current Vol  : {:.2f}".format(current_volume))
            print("[VOLUME]  Average Vol  : {:.2f}".format(avg_volume))
            print("[VOLUME]  Vol Ratio    : {:.2f}x".format(vol_ratio))
            print("[VOLUME]  Spike        : {}".format(
                "YES (mag {:.0f})".format(spike_result["spike_magnitude"])
                if is_spike else "No"
            ))
            print("[VOLUME]  Vol Trend    : {}".format(vol_trend))
            print("[VOLUME]  OBV Trend    : {}".format(obv_trend))
            print("[VOLUME]  A/D Trend    : {}".format(ad_trend))
            print("[VOLUME]  Climax       : {}".format(climax))
            print("[VOLUME]  Confirmation : {}".format(confirmation))
            print("[VOLUME]  Raw Score    : {:.1f}/100".format(score))
            print("[VOLUME]  Direction    : {}".format(direction))
            print("[VOLUME]  Confidence   : {:.1f}%".format(confidence))
            print("[VOLUME] ═══════════════════════════════════\n")

            return result

        except Exception as e:
            print("[VOLUME] ❌ Analysis error: {}".format(e))
            return neutral_result


# ==================================================
# MODULE-LEVEL SINGLETON INSTANCE
# ==================================================
# Every module imports this same instance:
#
#   from algorithms.volume import volume_analyzer
#   result = volume_analyzer.analyze(dataframe)
# ==================================================

volume_analyzer = VolumeAnalyzer()

print("[VOLUME] ✅ Volume module loaded and ready")