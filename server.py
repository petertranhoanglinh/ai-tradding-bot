from fastapi import FastAPI, Query, HTTPException
from vnstock import Vnstock, Listing, Quote
import uvicorn
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
import concurrent.futures

app = FastAPI(title="VNStock v3 Standard API Service")

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi tạo đối tượng Vnstock (Sử dụng cho finance/news)
vn = Vnstock()

VN30_SYMBOLS = ['ACB', 'CTG', 'FPT', 'HPG', 'MBB', 'MSN', 'MWG', 'SSI', 'STB', 'TCB', 'VCB', 'VHM', 'VIC', 'VNM', 'VPB'] # Giới hạn 15 mã để tránh Rate Limit API Guest (20 req/min)

cached_vn30_data = {
    'timestamp': 0,
    'data': []
}

def clean_data(obj):
    """Xử lý kiểu dữ liệu numpy/pandas để FastAPI không báo lỗi JSON"""
    try:
        if pd.isna(obj):
            return None
        if isinstance(obj, (np.int64, np.int32, np.int16, np.integer)):
            return int(obj)
        if isinstance(obj, (np.float64, np.float32, np.float16, np.floating)):
            return float(obj)
        if isinstance(obj, (np.ndarray)):
            return obj.tolist()
        if isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        if hasattr(obj, 'item'):
            return obj.item()
        return obj
    except:
        return str(obj)


def safe_to_dict(df):
    if df is None or df.empty:
        return []
    records = df.to_dict('records')
    return [{k: clean_data(v) for k, v in record.items()} for record in records]

def calculate_indicators(df):
    try:
        if df is None or df.empty: return df
        # Ensure column names are clean and flat
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ['_'.join(map(str, col)).strip().lower() for col in df.columns.values]
        else:
            df.columns = [str(c).lower() for c in df.columns]
        
        close_col = 'close' if 'close' in df.columns else None
        if not close_col:
            for c in df.columns:
                if 'đóng' in c: close_col = c; break
        
        if not close_col: return df
        
        # Technical Indicators
        df['sma20'] = df[close_col].rolling(window=20, min_periods=1).mean()
        df['sma50'] = df[close_col].rolling(window=50, min_periods=1).mean()
        df['sma200'] = df[close_col].rolling(window=200, min_periods=1).mean()
        
        # RSI
        delta = df[close_col].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        rs = gain / (loss + 1e-9)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema12 = df[close_col].ewm(span=12, adjust=False).mean()
        ema26 = df[close_col].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        
        return df
    except Exception as e:
        print(f"Error calculating indicators: {e}")
        return df

def fetch_single_symbol_for_screener(symbol: str):
    try:
        start = (datetime.now() - timedelta(days=250)).strftime('%Y-%m-%d')
        end = datetime.now().strftime('%Y-%m-%d')
        q = Quote(symbol=symbol, source='VCI')
        df = q.history(start=start, end=end, interval='1D')
        
        if df is None or df.empty: return None
        
        df_indicators = calculate_indicators(df)
        dict_data = safe_to_dict(df_indicators)
        
        if len(dict_data) >= 3:
            # We only need the last 3 days to evaluate signal: today, yesterday, before
            return {
                'symbol': symbol,
                'today': dict_data[-1],
                'yesterday': dict_data[-2],
                'before': dict_data[-3]
            }
        return None
    except Exception as e:
        print(f"Error fetching {symbol} for screener: {e}")
        return None

@app.get("/api/v3/screener/vn30")
def screener_vn30_cache(symbols: str = Query(None)):
    # ... existing logic ...
    pass

@app.get("/api/v3/screener/single-signal")
def get_single_signal(symbol: str):
    """Lấy tín hiệu kỹ thuật chi tiết của 1 mã dành cho Java Server quét ngầm"""
    try:
        res = fetch_single_symbol_for_screener(symbol.upper())
        if not res:
            return {"error": f"Không tìm thấy dữ liệu cho {symbol}"}
        
        # Trả về kết quả sạch sẽ để Java lưu DB
        return {
            "symbol": symbol.upper(),
            "today": res['today'],
            "yesterday": res['yesterday'],
            "before": res['before'],
            "timestamp": time.time()
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/v3/market/equity/ohlcv")

@app.get("/api/v3/market/equity/ohlcv")
def get_ohlcv(symbol: str, start: str = None, end: str = None):
    try:
        if not start:
            start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        if not end:
            end = datetime.now().strftime('%Y-%m-%d')
            
        # Using Quote class as per documentation
        q = Quote(symbol=symbol, source='VCI')
        df = q.history(start=start, end=end, interval='1D')
        return safe_to_dict(df)
    except Exception as e:
        print(f"OHLCV Error for {symbol}: {e}")
        return []

def fetch_robust_quote(symbol: str):
    symbol = symbol.upper()
    try:
        # Nguồn tin cậy nhất được xác nhận bởi lỗi của hệ thống
        for source in ['vci', 'kbs']:
            try:
                q = Quote(symbol=symbol, source=source)
                
                # 1. Thử lấy Price Board (Bảng điện) - Kiểm tra lỗi thuộc tính linh hoạt
                df_board = None
                try:
                    if hasattr(q, 'trading'):
                        df_board = q.trading.price_board()
                    elif hasattr(q, 'price_board'): # Một số phiên bản cũ hơn của v3
                        df_board = q.price_board()
                    elif hasattr(q, 'board'):
                        df_board = q.board()
                except:
                    pass

                if df_board is not None and not df_board.empty:
                    row = safe_to_dict(df_board)[0]
                    price = row.get('last_price', row.get('price', row.get('match_price', 0)))
                    if price and price > 0:
                        return row
                
                # 2. History fallback (Phương án ổn định nhất cho VCB/Chứng khoán)
                start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                end = datetime.now().strftime('%Y-%m-%d')
                df_hist = q.history(start=start, end=end)
                
                if df_hist is not None and not df_hist.empty:
                    last_row = df_hist.iloc[-1].to_dict()
                    # Mapping các cột giá có thể có
                    close_val = 0
                    for col in ['close', 'đóng', 'gia_dong', 'gia_dong_cua', 'close_price']:
                        if col in last_row:
                            close_val = last_row[col]
                            break
                    
                    if not close_val:
                        # Vét cạn: lấy giá trị số đầu tiên không phải vol/time (thường là Open/High/Low/Close)
                        # Dòng này dự phòng cho TH các cột bị đổi tên hoàn toàn
                        numeric_vals = [v for v in last_row.values() if isinstance(v, (int, float))]
                        close_val = numeric_vals[3] if len(numeric_vals) > 3 else (numeric_vals[0] if numeric_vals else 0)

                    if close_val and close_val > 0:
                        return {
                            "symbol": symbol,
                            "price": clean_data(close_val),
                            "last_price": clean_data(close_val),
                            "source": f"{source}_history_v3"
                        }
            except Exception as e:
                print(f"DEBUG: Skipping source {source} for {symbol} due to: {e}")
                continue
        return {"symbol": symbol, "price": 0, "last_price": 0}
    except Exception as e:
        print(f"Fetch Robust Quote Error for {symbol}: {e}")
        return {"symbol": symbol, "price": 0, "last_price": 0}

@app.get("/api/v3/market/equity/quote")
def get_equity_quote(symbol: str):
    return fetch_robust_quote(symbol)

@app.get("/api/v3/market/quote")
def get_multi_quote(symbols: str):
    """Trả về Map {SYMBOL: PRICE} để Java parse trực tiếp"""
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(',')]
        results = {}
        for sym in symbol_list:
            quote = fetch_robust_quote(sym)
            price = quote.get('last_price', quote.get('price', 0))
            results[sym] = price
        return results
    except Exception as e:
        print(f"Multi-quote Error: {e}")
        return {}

@app.get("/api/v3/backtest/data/{symbol}")
def get_backtest_data(symbol: str):
    """
    ULTRA-FAST ENDPOINT: Only fetches raw OHLCV + indicators for the backtest engine page.
    Bypasses Gemini AI entirely.
    """
    try:
        q = Quote(symbol=symbol, source='VCI')
        start_date = (datetime.now() - timedelta(days=2500)).strftime('%Y-%m-%d')
        # Thử nguồn VCI, nếu fail thử TCBS
        try:
            ohlcv_df = q.history(start=start_date, end=datetime.now().strftime('%Y-%m-%d'))
        except Exception:
            q = Quote(symbol=symbol, source='TCBS')
            ohlcv_df = q.history(start=start_date, end=datetime.now().strftime('%Y-%m-%d'))
        
        if ohlcv_df.empty:
            return {"symbol": symbol, "data": []}
            
        ohlcv_df = calculate_indicators(ohlcv_df)
        
        # Lấy 1500 ngày cho Backtest
        daily_data = safe_to_dict(ohlcv_df.tail(1500))
        
        return {
            "symbol": symbol,
            "period": len(daily_data),
            "data": daily_data
        }
    except Exception as e:
        print(f"Backtest Data Error for {symbol}: {e}")
        return {"symbol": symbol, "error": str(e), "data": []}

@app.get("/api/v3/analysis/{symbol}")
def get_comprehensive_analysis(symbol: str):
    symbol = symbol.upper()
    try:
        # Use Quote and Vnstock modules
        q = Quote(symbol=symbol, source='VCI')
        
        # 1. Price Board & OHLCV ...
        current_price = 0
        quote_df = pd.DataFrame()
        try:
            quote_df = q.trading.price_board()
            if not quote_df.empty:
                current_price = clean_data(quote_df.iloc[0].get('last_price', quote_df.iloc[0].get('price', 0)))
        except: pass

        # 2. Daily Data
        start_date = (datetime.now() - timedelta(days=2000)).strftime('%Y-%m-%d')
        daily_data = []
        latest_indicators = {}
        try:
            ohlcv_df = q.history(start=start_date, end=datetime.now().strftime('%Y-%m-%d'))
            ohlcv_df = calculate_indicators(ohlcv_df)
            if not ohlcv_df.empty:
                daily_data = safe_to_dict(ohlcv_df.tail(1500))
                latest = ohlcv_df.iloc[-1]
                latest_indicators = {
                    "rsi": clean_data(latest.get('rsi', 0)),
                    "sma20": clean_data(latest.get('sma20', 0)),
                    "sma50": clean_data(latest.get('sma50', 0)),
                    "sma200": clean_data(latest.get('sma200', 0))
                }
        except: pass

        # 3. Finance
        finance_data = {}
        for src in ['TCBS', 'SSI', 'VCI']:
            try:
                stock = vn.stock(symbol=symbol, source=src)
                fin = stock.finance.ratio(period='year', lang='vi') if src == 'TCBS' else stock.finance.ratio(period='year')
                if not fin.empty:
                    d = {k: clean_data(v) for k, v in fin.iloc[0].to_dict().items()}
                    for k, v in d.items():
                        kl = str(k).lower()
                        if 'p/e' in kl: finance_data['pe'] = v
                        elif 'p/b' in kl: finance_data['pb'] = v
                        elif 'roe' in kl: finance_data['roe'] = v
                        elif 'roa' in kl: finance_data['roa'] = v
                        elif 'eps' in kl: finance_data['eps'] = v
                    if finance_data: break
            except: pass
        
        # 4. Overview, Shareholders & Insiders
        overview = {}
        for src in ['TCBS', 'SSI', 'VCI']:
            try:
                stock = vn.stock(symbol=symbol, source=src)
                p = stock.company.overview() if hasattr(stock.company.overview, '__call__') else stock.company.overview
                if not p.empty:
                    d = p.iloc[0].to_dict()
                    overview = {k: clean_data(v) for k, v in d.items()}
                    break
            except: pass

        shareholders = []
        for src in ['TCBS', 'SSI', 'VCI']:
            try:
                stock = vn.stock(symbol=symbol, source=src)
                sh = stock.company.shareholders() if hasattr(stock.company.shareholders, '__call__') else stock.company.shareholders
                if not sh.empty:
                    shareholders = []
                    for _, r in sh.head(10).iterrows():
                        d = r.to_dict()
                        # Find name
                        name = d.get('share_holder', d.get('name', d.get('shareHolder', d.get('organName', d.get('shareholderName', list(d.values())[1] if len(d)>1 else "")))))
                        # Find pct
                        pct = d.get('share_own_percent', d.get('percentage', d.get('ownPercent', d.get('holdRatio', list(d.values())[2] if len(d)>2 else 0))))
                        shareholders.append({"name": clean_data(name), "percentage": clean_data(pct)})
                    break
            except: pass

        insider_deals = []
        for src in ['TCBS', 'SSI', 'VCI']:
            try:
                stock = vn.stock(symbol=symbol, source=src)
                id_deals = stock.company.insider_deals() if hasattr(stock.company.insider_deals, '__call__') else stock.company.insider_deals
                if not id_deals.empty:
                    insider_deals = []
                    for _, r in id_deals.head(10).iterrows():
                        d = r.to_dict()
                        name = d.get('insider_name', d.get('name', d.get('insiderName', list(d.values())[2] if len(d)>2 else "")))
                        type_str = d.get('deal_type', d.get('type', d.get('dealType', d.get('dealAction', list(d.values())[3] if len(d)>3 else ""))))
                        vol = d.get('deal_volume', d.get('volume', d.get('dealVolume', list(d.values())[5] if len(d)>5 else 0)))
                        date = d.get('update_date', d.get('date', d.get('dealAnnounceDate', list(d.values())[1] if len(d)>1 else "")))
                        insider_deals.append({"name": clean_data(name), "type": clean_data(type_str), "volume": clean_data(vol), "date": clean_data(date)})
                    break
            except: pass

        # 5. News
        news_data = []
        for src in ['TCBS', 'SSI', 'VCI']:
            try:
                stock = vn.stock(symbol=symbol, source=src)
                news = stock.company.news()
                if not news.empty:
                    news_data = safe_to_dict(news.head(10))
                    break
            except: pass

        # 5. Foreign Flow
        foreign_net_buy = "0 CP"
        try:
            if not quote_df.empty:
                flow = quote_df.iloc[0]
                buy_vol = flow.get('foreign_buy_vol', 0)
                sell_vol = flow.get('foreign_sell_vol', flow.get('foreign_selling_volume', 0))
                net = buy_vol - sell_vol
                foreign_net_buy = f"{net:,.0f} CP"
        except: pass

        macro_context = {
            "gdp_growth_2024": "6.5% - 7% (Mục tiêu)",
            "inflation_cpi": "3.5% - 4.5%",
            "exchange_rate_trend": "Áp lực tăng từ USD Index, NHNN can thiệp ổn định",
            "interest_rate_avg": "Lãi suất huy động 4.5-6%, Lãi suất cho vay 7-9% (Đang ổn định thấp)",
            "political_sentiment": "Ổn định chiến lược, Đẩy mạnh đầu tư công, Chỉnh đốn thị trường tài chính",
            "fdi_inflow": "Tăng trưởng mạnh mẽ, trọng tâm Bán dẫn & Năng lượng xanh",
            "market_sentiment": "Thanh khoản cải thiện, kỳ vọng nâng hạng thị trường FTSE/MSCI"
        }

        return {
            "symbol": symbol,
            "current_price": current_price,
            "daily": daily_data,
            "latest_indicators": latest_indicators,
            "finance": finance_data,
            "overview": overview,
            "shareholders": shareholders,
            "insider_deals": insider_deals,
            "news": news_data,
            "foreign_net_buy": foreign_net_buy,
            "macro_context": macro_context,
            "analysis_time": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Comprehensive Analysis Error for {symbol}: {e}")
        return {"error": str(e), "symbol": symbol}

@app.get("/api/v3/validate/{symbol}")
def validate_ticker(symbol: str):
    try:
        q = Quote(symbol=symbol, source='VCI')
        df = q.trading.price_board()
        return {"isValid": not df.empty, "symbol": symbol}
    except:
        return {"isValid": False, "symbol": symbol}

@app.get("/api/v3/market/listing")
def get_listing(type: str = "ALL"):
    try:
        # Thử lấy dữ liệu từ cả 2 nguồn để đảm bảo đầy đủ (VCI và KBS)
        df = pd.DataFrame()
        sources = ['VCI', 'KBS']
        
        for src in sources:
            try:
                temp_df = Listing(source=src).all_symbols()
                if temp_df is not None and not temp_df.empty:
                    df = temp_df
                    print(f"DEBUG: Đã lấy thành công {len(df)} mã từ nguồn {src}")
                    break
            except Exception as e:
                print(f"DEBUG: Nguồn {src} lỗi: {e}")
                continue
        
        if df.empty:
            print("ERROR: Không lấy được danh sách chứng khoán từ bất kỳ nguồn nào!")
            return []
            
        results = []
        for _, row in df.iterrows():
            # Kiểm tra linh hoạt các tên cột có thể có (symbol, ticker, organ_name, organName)
            sym = row.get('symbol', row.get('ticker'))
            name = row.get('organ_name', row.get('organName', row.get('organ_short_name', sym)))
            
            if sym:
                results.append({
                    "symbol": clean_data(sym),
                    "shortName": clean_data(name),
                    "type": "STOCK",
                    "exchange": clean_data(row.get('exchange', row.get('com_group_code', 'HSX')))
                })
        
        return results
    except Exception as e:
        print(f"Listing critical error: {e}")
        return []

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)