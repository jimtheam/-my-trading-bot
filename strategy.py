import pandas as pd
import ta
import math

class TradingEngine:
    def __init__(self, capital, risk_pct):
        self.capital = capital
        self.risk_pct = risk_pct

    def calculate_indicators(self, close_prices):
        """
        一次性计算 MACD, RSI, EMA
        """
        df = pd.DataFrame(close_prices, columns=['close'])
        
        # 1. 计算 MACD (12, 26, 9)
        macd_obj = ta.trend.MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
        
        # 2. 计算 RSI (14)
        rsi_val = ta.momentum.rsi(close=df['close'], window=14)
        
        # 3. 计算 EMA (200) - 趋势生命线
        ema_200 = ta.trend.ema_indicator(close=df['close'], window=200)

        # 打包返回最新数据
        return {
            "close": df['close'].iloc[-1],
            "macd": macd_obj.macd().iloc[-1],
            "signal": macd_obj.macd_signal().iloc[-1],
            "hist": macd_obj.macd_diff().iloc[-1],
            "rsi": rsi_val.iloc[-1],
            "ema200": ema_200.iloc[-1]
        }

    def check_signal(self, data):
        """
        【最强策略逻辑】
        """
        # 解包数据
        close = data['close']
        macd = data['macd']
        signal = data['signal']
        hist = data['hist']
        rsi = data['rsi']
        ema200 = data['ema200']

        # 容错：如果数据不足计算 EMA200（比如新股），则返回中立
        if pd.isna(ema200):
            return "NEUTRAL"

        # === 🟢 做多 (BUY) 条件 ===
        # 1. 趋势：价格在 EMA 200 之上 (处于上升趋势)
        # 2. 动能：RSI < 70 (没有严重超买，还有上涨空间) 且 RSI > 45 (有动能)
        # 3. 触发：MACD 金叉 (MACD线 上穿 信号线) 且 柱状图 > 0
        if (close > ema200) and (45 < rsi < 70) and (macd > signal) and (hist > 0):
            # 过滤微弱的金叉：要求 MACD 线也是正的，或者刚突破零轴
            return "BUY"

        # === 🔴 做空 (SELL) 条件 ===
        # 1. 趋势：价格在 EMA 200 之下 (处于下降趋势)
        # 2. 动能：RSI > 30 (没有严重超卖) 且 RSI < 55 (空头动能)
        # 3. 触发：MACD 死叉 (MACD线 下穿 信号线)
        elif (close < ema200) and (30 < rsi < 55) and (macd < signal) and (hist < 0):
            return "SELL"
        
        return "NEUTRAL"

    def get_option_suggestion(self, symbol, signal, current_price):
        if signal == "NEUTRAL": return None
        
        direction = "CALL" if signal == "BUY" else "PUT"
        strike = round(current_price)
        # 这里的 expiry 只是建议，实际交易需要人去看期权链
        expiry = "0-7 DAYS" # 1分钟策略通常做末日轮或周权
        
        return {
            "type": "OPTION",
            "symbol": symbol,
            "direction": direction,
            "strike": strike,
            "expiry": expiry
        }

    def position_sizing(self, entry_price, stop_loss):
        # 简单的风险模型
        risk_amount = self.capital * self.risk_pct
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share == 0: return 0
        shares = math.floor(risk_amount / risk_per_share)
        return shares