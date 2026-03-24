import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta

# --- 1. THE BACKEND LOGIC ---
class SaDevTradingBot:
    def __init__(self, ticker, interval='4h', rr_ratio=3):
        self.ticker = ticker
        self.interval = interval
        self.rr_ratio = rr_ratio
        self.df = pd.DataFrame()

    def fetch_data(self, period='2y'):
        try:
            self.df = yf.download(self.ticker, period=period, interval=self.interval)
            if self.df.empty:
                return pd.DataFrame()
            if isinstance(self.df.columns, pd.MultiIndex):
                self.df.columns = self.df.columns.get_level_values(0)
            return self.df
        except Exception:
            return pd.DataFrame()

    def identify_trend(self):
        self.df['EMA_50'] = ta.ema(self.df['Close'], length=50)
        self.df['EMA_200'] = ta.ema(self.df['Close'], length=200)
        
        if len(self.df) < 200:
            return "NEUTRAL (Low Data)"

        last_close = float(self.df['Close'].iloc[-1])
        ema_50 = float(self.df['EMA_50'].iloc[-1])
        ema_200 = float(self.df['EMA_200'].iloc[-1])

        if ema_50 > ema_200 and last_close > ema_50:
            return "BULLISH"
        elif ema_50 < ema_200 and last_close < ema_50:
            return "BEARISH"
        return "NEUTRAL"

    def find_zones(self, window=20):
        self.df['Support'] = self.df['Low'].rolling(window=window).min()
        self.df['Resistance'] = self.df['High'].rolling(window=window).max()
        return float(self.df['Support'].iloc[-1]), float(self.df['Resistance'].iloc[-1])

    def generate_trade_plan(self):
        trend = self.identify_trend()
        sup, res = self.find_zones()
        plan = {"Trend": trend, "Signal": "WAIT"}

        if trend == "BULLISH":
            entry = sup
            stop_loss = entry * 0.98
            risk = entry - stop_loss
            take_profit = entry + (risk * self.rr_ratio)
            plan.update({"Signal": "BUY LIMIT", "Entry": entry, "SL": stop_loss, "TP": take_profit})
        elif trend == "BEARISH":
            entry = res
            stop_loss = entry * 1.02
            risk = stop_loss - entry
            take_profit = entry - (risk * self.rr_ratio)
            plan.update({"Signal": "SELL LIMIT", "Entry": entry, "SL": stop_loss, "TP": take_profit})
        return plan

# --- 2. THE FRONTEND SETUP ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
server = app.server

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H3("SaDev Bot UI", className="text-primary mt-3"),
                html.Hr(),
                html.Label("Ticker (e.g., BTC-USD)"),
                dbc.Input(id="ticker-input", value="BTC-USD", type="text", className="mb-3"),
                
                html.Label("Timeframe"),
                dcc.Dropdown(
                    id="tf-dropdown",
                    options=[
                        {"label": "15m", "value": "15m"},
                        {"label": "1h", "value": "1h"},
                        {"label": "4h", "value": "4h"},
                        {"label": "1d", "value": "1d"},
                    ],
                    value="4h", className="mb-3 text-dark"
                ),
                
                dbc.Button("Run Analysis", id="run-btn", color="primary", className="w-100 mb-4"),
                html.Div(id="plan-card")
            ], className="p-3 bg-dark rounded border border-secondary")
        ], md=3),

        dbc.Col([
            dcc.Loading(id="loading", children=dcc.Graph(id="main-chart", style={"height": "85vh"}))
        ], md=9)
    ], className="mt-4")
], fluid=True)

# --- 3. THE INTERACTIVITY (CALLBACK) ---
@app.callback(
    [Output("main-chart", "figure"), Output("plan-card", "children")],
    [Input("run-btn", "n_clicks")],
    [State("ticker-input", "value"), State("tf-dropdown", "value")]
)
def update_ui(n_clicks, ticker, interval):
    if not n_clicks:
        return go.Figure().update_layout(template="plotly_dark"), "Enter ticker and click Run."

    bot = SaDevTradingBot(ticker, interval=interval)
    period = "60d" if interval in ["15m", "1h", "4h"] else "2y"
    df = bot.fetch_data(period=period)

    if df.empty:
        return go.Figure(), dbc.Alert("No data found! Check symbol.", color="danger")

    plan = bot.generate_trade_plan()

    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"
    )])
    
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], name="EMA 50", line=dict(color='cyan')))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_200'], name="EMA 200", line=dict(color='magenta')))
    fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False)

    color = "success" if "BUY" in plan['Signal'] else "danger" if "SELL" in plan['Signal'] else "info"
    
    plan_display = dbc.Card([
        dbc.CardBody([
            html.H4(plan['Signal'], className=f"text-{color}"),
            html.P(f"Trend: {plan['Trend']}"),
            html.Hr(),
            html.P(f"Entry: {plan.get('Entry', 0):.4f}"),
            html.P(f"SL: {plan.get('SL', 0):.4f}"),
            html.P(f"TP: {plan.get('TP', 0):.4f}"),
        ])
    ], color="secondary", outline=True)

    return fig, plan_display

# --- 4. START THE SERVER ---
if __name__ == "__main__":
    app.run(debug=True, port=8050)
   
