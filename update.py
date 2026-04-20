#!/usr/bin/env python3
"""
福福资产日报 - 每日数据更新脚本
从 fufu-portfolio.json + 实时行情API 生成 data.json
"""
import json, urllib.request, subprocess, datetime, os
from pathlib import Path

BASE = Path(__file__).parent
ROOT = BASE.parent
PORTFOLIO = ROOT / 'fufu-portfolio.json'
OUT = BASE / 'data.json'

def get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

# 加载持仓
with open(PORTFOLIO, 'r', encoding='utf-8') as f:
    p = json.load(f)

# 拉实时行情
btc = get_json("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=cny,usd")
fx = get_json("https://api.exchangerate-api.com/v4/latest/USD")
usdcny = fx['rates']['CNY']
hkdcny = usdcny / fx['rates']['HKD']

try:
    gold = get_json("https://api.gold-api.com/price/XAU")
    gold_usd_oz = gold.get('price', 4700)
except Exception:
    gold_usd_oz = 4700
gold_cny_g = gold_usd_oz / 31.1035 * usdcny

# A股+港股：腾讯qt.gtimg.cn
qt_raw = subprocess.run(
    ['curl', '-s', 'https://qt.gtimg.cn/q=sz300750,sh600519,hk00700'],
    capture_output=True
).stdout.decode('gbk', errors='ignore')

def parse_qt(text, prefix):
    for line in text.split(';'):
        if prefix in line and '=' in line:
            parts = line.split('~')
            if len(parts) > 3:
                return float(parts[3])
    return 0

catl = parse_qt(qt_raw, 'sz300750')
mt = parse_qt(qt_raw, 'sh600519')
tx = parse_qt(qt_raw, 'hk00700')

btc_cny = btc['bitcoin']['cny']
btc_usd = btc['bitcoin']['usd']

# 福福年龄（X岁X个月）
bday = datetime.date(2023, 7, 31)
today = datetime.date.today()
months = (today.year - bday.year) * 12 + (today.month - bday.month)
if today.day < bday.day:
    months -= 1
years = months // 12
mm = months % 12
age = f"{years}岁{mm}个月"

# 计算每个资产
assets = []
EMOJI = {"比特币": "₿", "黄金": "🥇", "宁德时代": "🔋", "贵州茅台": "🍷",
         "腾讯控股": "🐧", "现金": "💵"}

for a in p['assets']:
    name = a['name']
    qty = a['quantity']
    unit = a['unit']
    emoji = EMOJI.get(name, "•")

    if name == "比特币":
        price = btc_cny
        val = qty * price
        price_display = f"¥{price:,.0f}/{unit}"
        qty_display = f"{qty} {unit}"
    elif name == "黄金":
        price = gold_cny_g
        val = qty * price
        price_display = f"¥{price:,.2f}/{unit}"
        qty_display = f"{qty} {unit}"
    elif name == "宁德时代":
        price = catl
        val = qty * price
        price_display = f"¥{price:,.2f}/{unit}"
        qty_display = f"{qty} {unit}"
    elif name == "贵州茅台":
        price = mt
        val = qty * price
        price_display = f"¥{price:,.2f}/{unit}"
        qty_display = f"{qty} {unit}"
    elif name == "腾讯控股":
        price = tx
        val = qty * price * hkdcny
        price_display = f"HK${price:,.2f}"
        qty_display = f"{qty} {unit}"
    elif name == "现金":
        val = qty
        price_display = ""
        qty_display = "–"
    else:
        val = 0
        price_display = ""
        qty_display = ""

    assets.append({
        "name": name,
        "emoji": emoji,
        "qty_display": qty_display,
        "price_display": price_display,
        "value_cny": round(val),
    })

total = sum(a['value_cny'] for a in assets)
for a in assets:
    a['pct'] = round(a['value_cny'] / total * 100, 1) if total > 0 else 0

# 按估值降序
assets.sort(key=lambda x: x['value_cny'], reverse=True)

# 今日要点（简单规则生成）
highlights = []
btc_usd_fmt = f"${btc_usd:,.0f}"
highlights.append(f"BTC 报 {btc_usd_fmt}（¥{btc_cny:,.0f}/枚），占组合 {next(a['pct'] for a in assets if a['name']=='比特币'):.1f}%")
gold_pct = next(a['pct'] for a in assets if a['name']=='黄金')
highlights.append(f"国际金价 ${gold_usd_oz:,.0f}/盎司，折合 ¥{gold_cny_g:,.2f}/克，黄金持仓占 {gold_pct:.1f}%")
try:
    catl_pct = next(a['pct'] for a in assets if a['name']=='宁德时代')
    highlights.append(f"宁德时代 ¥{catl:,.2f}，持仓占 {catl_pct:.1f}%")
except StopIteration: pass
try:
    tx_pct = next(a['pct'] for a in assets if a['name']=='腾讯控股')
    highlights.append(f"腾讯控股 HK${tx:,.2f}，持仓占 {tx_pct:.1f}%")
except StopIteration: pass

now = datetime.datetime.now()
weekdays = ['周一','周二','周三','周四','周五','周六','周日']
data = {
    "date": f"{now.year}年{now.month}月{now.day}日 {weekdays[now.weekday()]}",
    "age": age,
    "total_cny": total,
    "assets": assets,
    "highlights": highlights,
    "updated_at": now.strftime("%Y-%m-%d %H:%M CST"),
    "prices": {
        "btc_usd": btc_usd,
        "btc_cny": btc_cny,
        "gold_usd_oz": gold_usd_oz,
        "gold_cny_g": round(gold_cny_g, 2),
        "usd_cny": round(usdcny, 4),
        "hkd_cny": round(hkdcny, 4),
        "catl_cny": catl,
        "moutai_cny": mt,
        "tencent_hkd": tx,
    },
}

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✅ 更新完成：总资产 ¥{total:,} | {now.strftime('%Y-%m-%d %H:%M')}")
print(f"   BTC ${btc_usd:,.0f} | 宁德 ¥{catl:.2f} | 茅台 ¥{mt:.2f} | 腾讯 HK${tx:.2f}")
