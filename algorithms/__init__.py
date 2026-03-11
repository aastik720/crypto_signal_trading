# ============================================
# ALGORITHMS PACKAGE INITIALIZER
# ============================================
# Brain #1: RSI              ✅
# Brain #2: MACD             ✅
# Brain #3: Bollinger        ✅
# Brain #4: Volume           ✅
# Brain #5: EMA Crossover    ✅
# Brain #6: Support/Resist.  ✅
# Brain #7: Candle Patterns  ✅
# Brain #8: OBV              ✅
# Signal Engine (combiner)   ✅
# ============================================

from algorithms.rsi import rsi_analyzer
from algorithms.macd import macd_analyzer
from algorithms.bollinger import bollinger_analyzer
from algorithms.volume import volume_analyzer
from algorithms.ema_crossover import ema_crossover_analyzer
from algorithms.support_resistance import sr_analyzer
from algorithms.candle_patterns import candle_analyzer
from algorithms.obv import obv_analyzer
from algorithms.signal_engine import signal_engine