from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from alpaca_trade_api.rest import REST, TimeFrame
import pandas as pd
from datetime import datetime
import asyncio
from config import *
from strategy import TradingEngine

# --- 1. 初始化 ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = REST(API_KEY, SECRET_KEY, BASE_URL)
engine = TradingEngine(TOTAL_CAPITAL, RISK_PER_TRADE)

scan_results = []
is_running = False # 控制开关

# --- 2. 监控列表 ---
WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
    "AMD", "INTC", "QCOM", "MU", "TSM", "SPY", "QQQ", "IWM",
    "TQQQ", "SQQQ", "SOXL", "BABA", "PDD", "NIO", "COIN", "MSTR",
    "GME", "AMC", "PLTR", "HOOD"
]

# --- 3. 核心扫描逻辑 ---
async def run_analysis():
    """执行一次完整的扫描"""
    global scan_results
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] 🔄 正在刷新最新价格与信号...")
    
    new_results = []
    
    for symbol in WATCHLIST:
        try:
            # 获取 300 根 1分钟 K线
            bars = api.get_bars(symbol, TimeFrame.Minute, limit=300).df
            
            if bars.empty or len(bars) < 200: continue

            # 获取最新价格
            current_price = bars.iloc[-1]['close']
            
            # 计算指标
            indicators = engine.calculate_indicators(bars['close'])
            signal = engine.check_signal(indicators)
            
            # 无论有没有信号，我们都把价格存进去，这样网页上能看到价格在动
            # 但只有有信号时，才标记 Signal 字段
            
            trade_setup = {
                "symbol": symbol,
                "price": current_price,
                "signal": signal, # 可能是 BUY, SELL 或 NEUTRAL
                "macd_val": indicators['macd'],
                "rsi": indicators['rsi'],
                "ema": indicators['ema200'],
                "suggested_shares": 0,
                "option_suggest": {"direction": "-", "strike": "-", "expiry": "-"},
                "timestamp": timestamp
            }

            # 如果有信号，才计算仓位和期权
            if signal != "NEUTRAL":
                stop_loss = current_price * 0.99 if signal == "BUY" else current_price * 1.01
                size = engine.position_sizing(current_price, stop_loss)
                opt = engine.get_option_suggestion(symbol, signal, current_price)
                
                trade_setup["suggested_shares"] = size
                trade_setup["option_suggest"] = opt
                
                print(f"🚀 信号触发: {symbol} {signal} @ {current_price}")

            new_results.append(trade_setup)

        except Exception as e:
            continue

    scan_results = new_results
    print(f"[{timestamp}] ✅ 更新完成")

# --- 4. 自动循环任务 ---
async def background_loop():
    """每隔 60 秒自动运行一次"""
    global is_running
    is_running = True
    while is_running:
        await run_analysis()
        # 等待 60 秒 (1分钟K线没必要刷太快)
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    # 程序启动时，自动开启后台循环
    asyncio.create_task(background_loop())

# --- 5. 接口 ---
@app.get("/")
async def read_index():
    return FileResponse('index.html')

@app.get("/results")
async def get_results():
    return {"data": scan_results}

# 启动: start.bat