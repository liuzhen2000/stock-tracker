import json
import os
from datetime import datetime, timezone, timedelta
import streamlit as st

st.set_page_config(page_title="持仓成本看板", layout="centered", page_icon="📈")

# ─── 全局 CSS：亮色/暗色主题适配 ───
st.markdown("""
<style>
/* 暗色主题 */
[data-theme="dark"] .card-bg-0 { background: #1e1e1e !important; }
[data-theme="dark"] .card-bg-1 { background: #2a2a2a !important; }
[data-theme="dark"] .card-text-date { color: #aaa !important; }
[data-theme="dark"] .card-text-label { color: #ccc !important; }
[data-theme="dark"] .card-text-default { color: #f0f0f0 !important; }
[data-theme="dark"] .card-border { border-color: #444 !important; }
[data-theme="dark"] .card-divider { border-top-color: #444 !important; }
[data-theme="dark"] .sym-color { color: #6ab0ff !important; }
[data-theme="dark"] .desc-color { color: #ccc !important; }
[data-theme="dark"] .metric-color,
[data-theme="dark"] .metric-color b { color: #ffffff !important; }

/* 亮色主题 */
[data-theme="light"] .card-bg-0 { background: #F7F9FC !important; }
[data-theme="light"] .card-bg-1 { background: white !important; }
[data-theme="light"] .card-text-date { color: #666 !important; }
[data-theme="light"] .card-text-label { color: #333 !important; }
[data-theme="light"] .card-text-default { color: #000 !important; }
[data-theme="light"] .card-border { border-color: #ddd !important; }
[data-theme="light"] .card-divider { border-top-color: #eee !important; }
[data-theme="light"] .sym-color { color: #1F4E79 !important; }
[data-theme="light"] .desc-color { color: #555 !important; }
[data-theme="light"] .metric-color { color: #000 !important; }

/* 默认（无data-theme时回退） */
.card-bg-0 { background: #F7F9FC; }
.card-bg-1 { background: white; }
.sym-color { color: #1F4E79; }
.metric-color { color: #000; }
.desc-color { color: #555; }

/* 盈亏标签 */
.loss { color: #ef4444 !important; font-weight: bold; }
.profit { color: #22c55e !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ─── 数据路径（相对路径，部署到云端也能用）───
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(DATA_DIR, "position.json")

# ─── 数据解析 ───

def parse_amount(s):
    if s is None or s == '':
        return 0.0
    return float(s.replace('$', '').replace(',', ''))

def parse_quantity(s):
    return float(s.replace(',', '')) if s else 0.0

def parse_price(s):
    if s is None or s == '':
        return 0.0
    return float(s.replace('$', '').replace(',', ''))

def parse_fee(s):
    if s is None or s == '':
        return 0.0
    val = s.replace('$', '').replace(',', '')
    return float(val) if val else 0.0

def parse_date(date_str):
    date_str = date_str.split(' as of')[0].strip()
    parts = date_str.split('/')
    return f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"


@st.cache_data(ttl=0)
def load_data():
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    transactions = data['BrokerageTransactions']
    trade_actions = {'Buy', 'Sell', 'Sell Short'}
    trades = [t for t in transactions if t['Action'] in trade_actions and t['Symbol']]

    # 计算净持仓
    position = {}
    for t in trades:
        symbol = t['Symbol']
        qty = parse_quantity(t['Quantity'])
        net = qty if t['Action'] == 'Buy' else -qty
        position[symbol] = position.get(symbol, 0.0) + net

    held_stocks = {sym: net for sym, net in position.items() if net > 0.001}

    result = []
    for symbol in sorted(held_stocks.keys()):
        symbol_trades = [t for t in trades if t['Symbol'] == symbol]
        # 按日期升序，同天颠倒
        stock_trades = sorted(
            enumerate(symbol_trades),
            key=lambda x: (parse_date(x[1]['Date']), -x[0])
        )

        description = symbol_trades[0]['Description'] if symbol_trades else ''
        records = []
        running_qty = 0.0
        running_cost = 0.0
        cycle_sell_profit = 0.0  # 当前持仓周期内的累计卖出盈亏，清仓时重置

        for _, t in stock_trades:
            date = parse_date(t['Date'])
            action = '买入' if t['Action'] == 'Buy' else '卖出'
            qty = parse_quantity(t['Quantity'])
            price = parse_price(t['Price'])
            fee = parse_fee(t.get('Fees & Comm', ''))

            prev_qty = running_qty

            if action == '买入':
                if running_qty <= 0:
                    running_cost = (qty * price + fee) / qty if qty > 0 else 0
                else:
                    running_cost = (running_cost * running_qty + qty * price + fee) / (running_qty + qty)
                running_qty += qty
            else:  # 卖出
                profit = (price - running_cost) * qty - fee

                if running_qty - qty <= 0:
                    # 清仓：重置周期累计盈亏
                    running_qty = 0
                    cycle_sell_profit = 0.0
                else:
                    # 部分卖出：重新计算持仓成本
                    running_cost = (running_cost * running_qty - qty * price + fee) / (running_qty - qty)
                    running_qty -= qty
                    cycle_sell_profit += profit

                records.append({
                    'date': date,
                    'action': action,
                    'qty': qty,
                    'price': price,
                    'fee': fee,
                    'profit': profit,
                    'cost': running_cost,
                    'holding': running_qty,
                })
                continue

            records.append({
                'date': date,
                'action': action,
                'qty': qty,
                'price': price,
                'fee': fee,
                'profit': None,
                'cost': running_cost,
                'holding': running_qty,
            })

        # 盈亏平衡点 = 持仓成本 - 当前周期累计卖出盈亏 / 当前股数
        if running_qty > 0 and running_cost > 0:
            break_even = running_cost - cycle_sell_profit / running_qty
        else:
            break_even = None

        result.append({
            'symbol': symbol,
            'description': description,
            'holding': running_qty,
            'cost': running_cost,
            'break_even': break_even,
            'records': records,
        })

    return result


# ─── 页面 ───

st.title("📈 持仓成本看板")

# 显示网页生成时间
now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
st.caption(f"🔄 网页生成于 {now}")

try:
    data = load_data()
except Exception as e:
    st.error(f"加载数据失败：{e}")
    st.stop()

st.markdown("### 📌 当前持仓")

# ─── 股票选择器（点击按钮切换股票）───
symbols = [s['symbol'] for s in data]
tabs = st.tabs(symbols)

for idx, stock in enumerate(data):
    with tabs[idx]:
        # ─── 股票头部（手机友好）───
        be_color = "#00B050" if stock['break_even'] and stock['cost'] and stock['break_even'] <= stock['cost'] else "#FF0000"
        be_text = f"${stock['break_even']:.2f}" if stock['break_even'] else "-"
        delta_text = f"({stock['break_even'] - stock['cost']:+.2f})" if stock['break_even'] and stock['cost'] else ""
        
        stock_header = f"""
        <div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;padding:8px 0;">
            <span class="sym-color" style="font-size:22px;font-weight:bold;">{stock['symbol']}</span>
            <span class="desc-color" style="font-size:12px">{stock['description']}</span>
            <span class="metric-color" style="font-size:14px;margin-left:auto"><b>成本</b> ${stock['cost']:.2f}</span>
            <span class="metric-color" style="font-size:14px"><b>持仓</b> {stock['holding']:.2f} 股</span>
            <span style="font-size:14px;color:{be_color}"><b>盈亏平衡</b> {be_text} <span style="font-size:12px;color:{be_color}">{delta_text}</span></span>
        </div>
        """
        st.markdown(stock_header, unsafe_allow_html=True)

        st.markdown("<hr style='margin:6px 0;border-top:2px solid #4472C4'>", unsafe_allow_html=True)

        # ─── 交易记录卡片（手机友好）───
        with st.expander(f"📋 查看交易记录（共 {len(stock['records'])} 条）", expanded=True):
            for i, r in enumerate(reversed(stock['records'])):
                action_color = "#006100" if r['action'] == '买入' else "#9C0006"
                action_bg = "#C6EFCE" if r['action'] == '买入' else "#FFC7CE"
                profit_symbol = "💰" if r['profit'] is not None else ""
                
                # 卡片容器
                card_html = f"""
                <div class="card-border {'card-bg-0' if i%2==0 else 'card-bg-1'}" style="border:1px solid;border-radius:6px;padding:8px 10px;margin-bottom:6px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                        <span class="card-text-date" style="font-size:13px">{r['date']}</span>
                        <span style="background:{action_bg};color:{action_color};font-weight:bold;font-size:13px;
                                    padding:2px 10px;border-radius:4px">{r['action']}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:14px;">
                        <span class="card-text-default"><b>{r['qty']:.2f}</b> 股 × <b>${r['price']:.2f}</b></span>
                        <span class="card-text-default">手续费: {f'${r["fee"]:.2f}' if r["fee"] else '-'}</span>
                    </div>
                    <div class="card-divider" style="display:flex;justify-content:space-between;font-size:13px;margin-top:4px;
                                padding-top:4px;border-top:1px dashed;">
                        <span class="card-text-default"><b>成本</b> ${r['cost']:.2f}</span>
                        <span class="card-text-default"><b>持仓</b> {r['holding']:.2f} 股</span>
                        <span>{f'<span class="profit">盈亏 ${r["profit"]:.2f}</span>' if r['profit'] is not None and r['profit']>=0 else f'<span class="loss">盈亏 ${r["profit"]:.2f}</span>' if r['profit'] is not None else '<span style="color:#999">-</span>'}</span>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)