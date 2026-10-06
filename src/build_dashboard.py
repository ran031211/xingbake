# -*- coding: utf-8 -*-
"""星巴克门店 —— 布局诊断与调整决策看板（v3 决策导向版）

设计原则：
  1. 图表只服务于结论，不做堆砌（4 张分析图 + 1 张地图）
  2. 每张图后紧跟「洞察 → 调整动作」，把数据翻译成业务动作
  3. 渐变一律使用对象写法；使用 echarts.graphic.LinearGradient 类实例做垂直渐变
     会因配置合并丢失颜色而触发 canvas 报错，进而中断整个脚本（历史踩坑）
"""
import json, os
import pandas as pd

# 项目根目录（src/ 的上一级），所有路径由它推导，clone 后可直接运行
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, 'outputs', 'starbucks')
ASSETS = os.path.join(ROOT, 'assets')
clean = pd.read_csv(os.path.join(BASE, 'starbucks_clean.csv'))
summary = json.load(open(os.path.join(BASE, 'summary.json'), encoding='utf-8'))
echarts_js = open(os.path.join(ASSETS, 'echarts.min.js'), encoding='utf-8').read()

# ---------- 地图点位（坐标 + 区域字段均完整） ----------
mask = (clean['geo_ok'] == True) & (clean['prov_ok'] == True) & (clean['city_ok'] == True)
pts = clean[mask].copy()
provs = sorted(pts['省份'].unique().tolist())
cities = sorted(pts['城市'].unique().tolist())
pidx = {p: i for i, p in enumerate(provs)}
cidx = {c: i for i, c in enumerate(cities)}


def h(v):
    return None if pd.isna(v) else round(float(v), 1)


points = [
    [round(float(r['纬度']), 5), round(float(r['经度']), 5), str(r['店铺名称']),
     pidx[r['省份']], cidx[r['城市']], h(r['营业时长_h'])]
    for _, r in pts.iterrows()
]
prov_count = pts['省份'].value_counts().to_dict()

# ---------- 省级下钻详情 ----------
prov_detail = {}
for p, g in pts.groupby('省份'):
    dc = g['城市'].value_counts().head(8)
    hs = g['营业时长_h'].mean()
    prov_detail[p] = {
        'n': int(len(g)),
        'hoursMean': (round(float(hs), 1) if pd.notna(hs) else None),
        'cities': [{'name': k, 'value': int(v)} for k, v in dc.items()],
    }

# ---------- 省域渗透四象限：门店数 × 覆盖城市数 × 平均营业时长 ----------
prov_stats = []
for p, g in pts.groupby('省份'):
    hs = g['营业时长_h'].mean()
    prov_stats.append({
        'name': p,
        'stores': int(len(g)),
        'cities': int(g['城市'].nunique()),
        'hours': (round(float(hs), 2) if pd.notna(hs) else 13.6),
        'density': round(len(g) / max(g['城市'].nunique(), 1), 1),
    })
prov_stats.sort(key=lambda d: -d['stores'])

# ---------- 派生经营指标 ----------
TOTAL_ALL = int(summary['total'])
MUNI = {'上海市', '北京市', '天津市', '重庆市'}
muni_n = int(sum(d['stores'] for d in prov_stats if d['name'] in MUNI))
scene_map = {d['场景']: d for d in summary['scene']}
mall = scene_map.get('商场/购物中心', {}).get('门店数', 0)
hub = sum(scene_map.get(k, {}).get('门店数', 0) for k in ('机场', '高铁/火车站', '交通枢纽/服务区'))
community = scene_map.get('社区/住宅', {}).get('门店数', 0)
med_school = scene_map.get('医院/学校', {}).get('门店数', 0)
open_before_0630 = sum(d['value'] for d in summary['open_slot'] if d['name'] in ('≤06:00', '06:01-06:30'))
peak_open = sum(d['value'] for d in summary['open_slot'] if d['name'] == '06:31-07:00')
long_n = sum(d['value'] for d in summary['hours_hist'] if d['name'] in ('14-15h', '15-16h'))
short_n = sum(d['value'] for d in summary['hours_hist']
              if d['name'] in ('0-1h', '1-2h', '2-3h', '3-4h', '4-5h', '5-6h', '6-7h', '7-8h', '8-9h', '9-10h'))
prof = summary['hours_profile']
peak = max(prof, key=lambda d: d['value'])
valley = min(prof, key=lambda d: d['value'])
# 待加密增长区：覆盖城市 >=11 且门店 <300
growth = [d for d in prov_stats if d['cities'] >= 11 and d['stores'] < 300]
growth_stores = sum(d['stores'] for d in growth)

derived = {
    'muniN': muni_n,
    'muniShare': round(muni_n / len(pts) * 100, 1),
    'mall': int(mall), 'mallShare': scene_map.get('商场/购物中心', {}).get('占比', 0),
    'hub': int(hub), 'hubShare': round(hub / TOTAL_ALL * 100, 1),
    'community': int(community),
    'medSchool': int(med_school),
    'openBefore0630': int(open_before_0630),
    'openBefore0630Share': round(open_before_0630 / TOTAL_ALL * 100, 1),
    'peakOpen': int(peak_open),
    'peakOpenShare': round(peak_open / TOTAL_ALL * 100, 1),
    'longN': int(long_n), 'longShare': round(long_n / TOTAL_ALL * 100, 1),
    'shortN': int(short_n), 'shortShare': round(short_n / TOTAL_ALL * 100, 1),
    'peakName': peak['name'], 'peakVal': int(peak['value']),
    'valleyName': valley['name'], 'valleyVal': int(valley['value']),
    'growthN': len(growth), 'growthStores': int(growth_stores),
    'growthCities': int(sum(d['cities'] for d in growth)),
    'growthNames': '、'.join(d['name'] for d in growth[:8]),
    'shDensity': next((d['density'] for d in prov_stats if d['name'] == '上海市'), 0),
    'bjDensity': next((d['density'] for d in prov_stats if d['name'] == '北京市'), 0),
    'ahStores': next((d['stores'] for d in prov_stats if d['name'] == '安徽省'), 0),
    'ahDensity': next((d['density'] for d in prov_stats if d['name'] == '安徽省'), 0),
    'sdStores': next((d['stores'] for d in prov_stats if d['name'] == '山东省'), 0),
    'sdDensity': next((d['density'] for d in prov_stats if d['name'] == '山东省'), 0),
    'gpStores': next((d['stores'] for d in prov_stats if d['name'] == '广东省'), 0),
    'gpCities': next((d['cities'] for d in prov_stats if d['name'] == '广东省'), 0),
    'zjStores': next((d['stores'] for d in prov_stats if d['name'] == '浙江省'), 0),
    'jsStores': next((d['stores'] for d in prov_stats if d['name'] == '江苏省'), 0),
    'scStores': next((d['stores'] for d in prov_stats if d['name'] == '四川省'), 0),
    'scCities': next((d['cities'] for d in prov_stats if d['name'] == '四川省'), 0),
    'openSlot': summary['open_slot'],
}

DATA = {
    'points': points, 'provs': provs, 'cities': cities,
    'provCount': prov_count, 'provDetail': prov_detail,
    'provStats': prov_stats, 'derived': derived,
    'mapN': len(points), 'summary': summary,
}
data_js = json.dumps(DATA, ensure_ascii=False, separators=(',', ':'))

HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>星巴克中国门店 · 布局诊断与调整决策</title>
<script type="text/javascript">
  window._TMapSecurityConfig = {
    serviceHost: 'http://127.0.0.1:__WB_HTTP_PORT__/_TMapService/_wbt/__WB_TMAP_SECRET__',
  };
</script>
<script src="https://map.qq.com/api/gljs?v=1.exp"></script>
<!-- ECharts 已内联，无外部依赖 -->
<script>__ECHARTS__</script>
<style>
  :root{
    --bg:#eef2f4;
    --card:#ffffff;
    --ink:#0f1e26; --ink2:#4d6169; --ink3:#8296a1;
    --line:#e1e9ec; --hair:#eff4f6;
    --brand:#006241; --brand2:#00a862; --brand3:#d6ece1; --brand4:#f0f8f4;
    --gold:#b8893f; --gold2:#e0c48a; --gold3:#fbf4e6;
    --amber:#c96f16; --amber2:#fdf0dd;
    --red:#b3382c; --red2:#fbeceb;
    --shadow-s:0 1px 2px rgba(15,30,38,.04),0 2px 8px rgba(15,30,38,.045);
    --shadow-m:0 2px 6px rgba(15,30,38,.05),0 14px 34px rgba(15,30,38,.075);
    --r:18px;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0;color:var(--ink);
    font-family:"PingFang SC","Microsoft YaHei","Helvetica Neue",Arial,sans-serif;
    -webkit-font-smoothing:antialiased;
    background:
      radial-gradient(1100px 520px at 8% -6%, #e3f2ea 0%, rgba(227,242,234,0) 62%),
      radial-gradient(900px 480px at 96% 2%, #fdf4e4 0%, rgba(253,244,228,0) 58%),
      linear-gradient(180deg,#f3f7f8 0%,#eef2f4 40%,#eaeff2 100%);
    background-attachment:fixed}
  .wrap{max-width:1400px;margin:0 auto;padding:26px 26px 60px}

  /* ---------- Hero ---------- */
  .hero{position:relative;overflow:hidden;border-radius:24px;padding:34px 38px 30px;color:#eafaf2;
    background:linear-gradient(122deg,#01291c 0%,#00402c 42%,#006241 78%,#0a7a56 100%);
    box-shadow:0 20px 48px rgba(1,41,28,.30)}
  .hero::before{content:"";position:absolute;inset:0;
    background:
      radial-gradient(560px 300px at 88% 8%, rgba(0,212,138,.30) 0%, rgba(0,212,138,0) 66%),
      radial-gradient(420px 260px at 6% 108%, rgba(224,196,138,.22) 0%, rgba(224,196,138,0) 70%)}
  .hero::after{content:"";position:absolute;right:-70px;top:-70px;width:290px;height:290px;border-radius:50%;
    border:1px solid rgba(255,255,255,.14);
    box-shadow:0 0 0 36px rgba(255,255,255,.045),0 0 0 74px rgba(255,255,255,.03)}
  .hero>.in{position:relative;z-index:2}
  .hbadge{display:inline-flex;align-items:center;gap:8px;font-size:11.5px;letter-spacing:1.4px;
    text-transform:uppercase;color:#9fe3c4;border:1px solid rgba(159,227,196,.34);
    border-radius:999px;padding:5px 13px;margin-bottom:16px;background:rgba(255,255,255,.05)}
  .hbadge i{width:6px;height:6px;border-radius:50%;background:#3ddc9a;box-shadow:0 0 0 4px rgba(61,220,154,.18)}
  .hero h1{margin:0 0 12px;font-size:31px;line-height:1.32;font-weight:800;letter-spacing:-.3px;color:#fff}
  .hero h1 em{font-style:normal;color:#ffd98a}
  .hero .lead{margin:0;font-size:14.5px;line-height:1.85;color:#c9e9db;max-width:900px}
  .hstats{display:grid;grid-template-columns:repeat(4,1fr);gap:0;margin-top:26px;
    border-top:1px solid rgba(255,255,255,.14);padding-top:20px}
  .hstat{padding-right:20px;border-right:1px solid rgba(255,255,255,.12)}
  .hstat:last-child{border-right:0}
  .hstat .n{font-size:26px;font-weight:800;color:#fff;font-variant-numeric:tabular-nums;letter-spacing:-.5px}
  .hstat .n small{font-size:13px;font-weight:600;color:#9fe3c4;margin-left:4px}
  .hstat .l{font-size:12px;color:#a7d3c1;margin-top:5px;line-height:1.6}

  /* ---------- 章节 ---------- */
  .sec{margin-top:34px}
  .shead{display:flex;align-items:center;gap:12px;margin:0 0 15px}
  .sno{flex:0 0 auto;width:27px;height:27px;border-radius:9px;display:flex;align-items:center;justify-content:center;
    font-size:13px;font-weight:800;color:#fff;background:linear-gradient(135deg,var(--brand) 0%,var(--brand2) 100%);
    box-shadow:0 3px 10px rgba(0,98,65,.26)}
  .shead h2{margin:0;font-size:17.5px;font-weight:800;letter-spacing:-.2px}
  .shead .shsub{font-size:12.5px;color:var(--ink3);font-weight:400;margin-left:2px}
  .shead .rule{flex:1;height:1px;background:linear-gradient(90deg,var(--line) 0%,rgba(225,233,236,0) 100%)}

  /* ---------- 诊断卡 ---------- */
  .diag{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
  .dcard{position:relative;background:var(--card);border:1px solid var(--line);border-radius:var(--r);
    padding:20px 21px 19px;box-shadow:var(--shadow-s);overflow:hidden;transition:.25s}
  .dcard:hover{transform:translateY(-3px);box-shadow:var(--shadow-m)}
  .dcard::before{content:"";position:absolute;left:0;right:0;top:0;height:3px}
  .dcard.r0::before{background:linear-gradient(90deg,#b3382c,#e0705f)}
  .dcard.r1::before{background:linear-gradient(90deg,#b8893f,#e6c78d)}
  .dcard.r2::before{background:linear-gradient(90deg,#006241,#00a862)}
  .dcard .lv{display:inline-block;font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px;margin-bottom:11px}
  .dcard.r0 .lv{background:var(--red2);color:var(--red)}
  .dcard.r1 .lv{background:var(--amber2);color:var(--amber)}
  .dcard.r2 .lv{background:var(--brand4);color:var(--brand)}
  .dcard h3{margin:0 0 9px;font-size:15.5px;font-weight:800;letter-spacing:-.2px}
  .dcard p{margin:0;font-size:12.8px;line-height:1.85;color:var(--ink2)}
  .dcard p b{color:var(--ink);font-weight:700;font-variant-numeric:tabular-nums}
  .dcard .kvrow{display:flex;gap:14px;margin-top:14px;padding-top:13px;border-top:1px dashed var(--line)}
  .dcard .kvrow div{flex:1}
  .dcard .kvrow .k{font-size:11px;color:var(--ink3)}
  .dcard .kvrow .v{font-size:18px;font-weight:800;color:var(--brand);font-variant-numeric:tabular-nums;margin-top:2px}
  .dcard.r0 .kvrow .v{color:var(--red)}
  .dcard.r1 .kvrow .v{color:var(--amber)}

  /* ---------- 面板 ---------- */
  .panel{background:var(--card);border:1px solid var(--line);border-radius:var(--r);
    box-shadow:var(--shadow-s);overflow:hidden}
  .phead{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 20px 14px}
  .phead h3{margin:0;font-size:15px;font-weight:800;letter-spacing:-.2px}
  .phead .tag{font-size:11.5px;color:var(--ink2);background:#f2f6f7;border:1px solid var(--line);
    border-radius:999px;padding:3px 11px;white-space:nowrap;font-weight:600}
  .pbody{padding:0 20px 18px}
  .chart{width:100%;height:340px}
  .chart.tall{height:400px}
  .cerr{height:100%;display:flex;align-items:center;justify-content:center;color:var(--red);
    font-size:12.5px;padding:20px;text-align:center;line-height:1.7}

  /* ---------- 洞察 / 调整 ---------- */
  .ia{display:grid;grid-template-columns:1fr 1fr;gap:0;border-top:1px solid var(--line)}
  .ia>div{padding:15px 20px 16px}
  .ia .ins{border-right:1px solid var(--line);background:#fbfdfd}
  .ia .act{background:linear-gradient(180deg,#f6fbf8 0%,#ffffff 100%)}
  .ia .cap{display:flex;align-items:center;gap:7px;font-size:11.5px;font-weight:800;letter-spacing:.9px;margin-bottom:9px}
  .ia .ins .cap{color:var(--ink2)}
  .ia .act .cap{color:var(--brand)}
  .ia .cap i{width:14px;height:14px;border-radius:5px;display:inline-flex;align-items:center;justify-content:center;
    font-size:9px;font-style:normal;color:#fff;font-weight:800}
  .ia .ins .cap i{background:linear-gradient(135deg,#5d7078,#8296a1)}
  .ia .act .cap i{background:linear-gradient(135deg,var(--brand),var(--brand2))}
  .ia p{margin:0 0 7px;font-size:12.7px;line-height:1.85;color:var(--ink2)}
  .ia p:last-child{margin-bottom:0}
  .ia p b{color:var(--ink);font-weight:700;font-variant-numeric:tabular-nums}
  .ia .act p b{color:var(--brand)}
  .ia .act .num{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:5px;
    background:var(--brand3);color:var(--brand);font-size:10px;font-weight:800;margin-right:6px;vertical-align:1px}

  /* ---------- 目标条 ---------- */
  .goals{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
  .goal{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px 17px;box-shadow:var(--shadow-s)}
  .goal .gt{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:11px}
  .goal .gt .nm{font-size:13px;font-weight:700}
  .goal .gt .vv{font-size:12px;color:var(--ink3);font-variant-numeric:tabular-nums;white-space:nowrap}
  .goal .gt .vv b{font-size:15px;font-weight:800;color:var(--brand)}
  .gbar{position:relative;height:9px;border-radius:999px;background:#eef3f5;overflow:hidden}
  .gbar .now{position:absolute;left:0;top:0;bottom:0;border-radius:999px;background:linear-gradient(90deg,#9fbfb2,#7fae9c)}
  .gbar .to{position:absolute;left:0;top:0;bottom:0;border-radius:999px;
    background:linear-gradient(90deg,var(--brand),var(--brand2))}
  .gbar .mark{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--gold);border-radius:2px;
    box-shadow:0 0 0 2px rgba(184,137,63,.16)}
  .gaxis{display:flex;justify-content:space-between;font-size:10.5px;color:var(--ink3);margin-top:7px;font-variant-numeric:tabular-nums}

  /* ---------- 行动卡 ---------- */
  .acts{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
  .acard{position:relative;background:var(--card);border:1px solid var(--line);border-radius:var(--r);
    padding:19px 20px;box-shadow:var(--shadow-s);transition:.25s;display:flex;flex-direction:column}
  .acard:hover{transform:translateY(-3px);box-shadow:var(--shadow-m)}
  .acard .ah{display:flex;align-items:flex-start;gap:11px;margin-bottom:12px}
  .pri{flex:0 0 auto;font-size:11px;font-weight:800;letter-spacing:.6px;padding:3px 9px;border-radius:7px}
  .pri.p0{background:linear-gradient(135deg,#b3382c,#d9534f);color:#fff}
  .pri.p1{background:linear-gradient(135deg,#c96f16,#e5a04a);color:#fff}
  .pri.p2{background:linear-gradient(135deg,#5d7078,#8296a1);color:#fff}
  .acard h4{margin:0;font-size:14.5px;font-weight:800;line-height:1.45;letter-spacing:-.2px}
  .acard .row{display:flex;gap:9px;font-size:12.6px;line-height:1.8;color:var(--ink2);margin-bottom:9px}
  .acard .row .lb{flex:0 0 auto;font-weight:800;color:var(--ink3);font-size:11.5px;padding-top:2px}
  .acard .row b{color:var(--ink);font-weight:700;font-variant-numeric:tabular-nums}
  .acard .row.target{background:var(--brand4);border:1px solid var(--brand3);border-radius:11px;
    padding:10px 12px;margin-top:auto;margin-bottom:0}
  .acard .row.target .lb{color:var(--brand)}
  .acard .row.target span{color:var(--brand);font-weight:700}

  /* ---------- 地图 ---------- */
  .mapsection{display:grid;grid-template-columns:1fr 306px;gap:16px}
  #map{height:540px;width:100%;position:relative;background:#e9eff2}
  .maptools{padding:13px 18px;border-bottom:1px solid var(--line);display:flex;gap:11px;align-items:center;flex-wrap:wrap;
    background:linear-gradient(180deg,#fbfdfd,#ffffff)}
  .maptools label{font-size:12.5px;color:var(--ink2);font-weight:700}
  .maptools select{flex:1;min-width:160px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;
    background:#fff;color:var(--ink);font-size:13px;outline:none;cursor:pointer;font-weight:700}
  .maptools select:focus{border-color:var(--brand2);box-shadow:0 0 0 3px rgba(0,166,98,.13)}
  .btn{padding:10px 15px;border-radius:10px;border:1px solid var(--brand);background:var(--brand);color:#fff;
    font-size:12.5px;cursor:pointer;white-space:nowrap;font-weight:700}
  .btn.ghost{background:#fff;color:var(--brand)}
  .btn:hover{filter:brightness(1.07)}
  .hintline{padding:10px 18px;font-size:11.5px;color:var(--ink3);border-bottom:1px solid var(--line);background:#fbfcfd;line-height:1.7}
  .side .blk{padding:15px 17px;border-bottom:1px solid var(--line)}
  .side .blk:last-child{border-bottom:0}
  .side h3{margin:0 0 11px;font-size:12.5px;font-weight:800;display:flex;justify-content:space-between;align-items:center;gap:8px}
  .side h3 em{font-style:normal;font-size:11px;color:var(--ink3);font-weight:500}
  .side p{margin:0;font-size:12.2px;color:var(--ink2);line-height:1.8}
  .side p b{color:var(--brand);font-weight:800}
  .rank{padding:0;margin:0;list-style:none;display:flex;flex-direction:column;gap:9px}
  .rank li{display:flex;align-items:flex-start;gap:9px;font-size:12.5px}
  .rank .no{width:19px;height:19px;border-radius:6px;background:#f1f5f6;color:var(--ink2);
    display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;flex:0 0 auto}
  .rank li:nth-child(1) .no{background:var(--brand);color:#fff}
  .rank li:nth-child(2) .no{background:#2c8c68;color:#fff}
  .rank li:nth-child(3) .no{background:#6bb795;color:#fff}
  .rank .nm{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .rank .vv{font-variant-numeric:tabular-nums;color:var(--ink);font-weight:700}
  .rank .bar{height:5px;border-radius:3px;background:var(--brand3);margin-top:5px}
  .rank .bar>i{display:block;height:100%;border-radius:3px;background:linear-gradient(90deg,var(--brand),var(--brand2))}
  .kv{display:flex;gap:10px}
  .kv div{flex:1;background:#f7fafb;border:1px solid var(--line);border-radius:11px;padding:10px 12px}
  .kv .k{font-size:11px;color:var(--ink2)}
  .kv .v{font-size:17px;font-weight:800;color:var(--brand);font-variant-numeric:tabular-nums;margin-top:3px}
  .legend{display:flex;flex-direction:column;gap:9px;font-size:12px;color:var(--ink2);line-height:1.6}
  .legend i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:8px;vertical-align:-1px}
  #info{position:absolute;z-index:20;min-width:190px;max-width:280px;background:#fff;
    border:1px solid var(--line);border-radius:12px;box-shadow:0 10px 32px rgba(15,30,38,.18);
    padding:12px 14px;font-size:12.5px;display:none;pointer-events:none}
  #info .t{font-weight:800;color:var(--brand);margin-bottom:6px;font-size:13px;line-height:1.45}
  #info .r{color:var(--ink2);line-height:1.75}
  #info .r span{color:var(--ink);font-weight:700}
  .mapmsg{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
    flex-direction:column;gap:9px;color:var(--ink3);font-size:13px;text-align:center;padding:30px;line-height:1.8}

  /* ---------- 时段条带 ---------- */
  .strip{margin-top:4px}
  .strip .sbar{display:flex;height:34px;border-radius:9px;overflow:hidden;border:1px solid var(--line)}
  .strip .sbar span{display:flex;align-items:center;justify-content:center;font-size:10.5px;font-weight:700;color:#fff;
    min-width:0;overflow:hidden;white-space:nowrap;transition:.2s}
  .strip .sbar span:hover{filter:brightness(1.1)}
  .strip .saxis{display:flex;justify-content:space-between;font-size:10.5px;color:var(--ink3);margin-top:7px}
  .strip .snote{font-size:11.5px;color:var(--ink3);margin-top:9px;line-height:1.7}

  #alert{display:none;margin-bottom:14px;padding:12px 16px;border-radius:12px;
    background:#fdf6e7;border:1px solid #f0e0b8;color:#8a6d1f;font-size:12.5px;line-height:1.75}

  /* ---------- 页脚 ---------- */
  .quality .qbody{padding:0 20px 18px;display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
  .qitem{font-size:12.4px;color:var(--ink2);line-height:1.85}
  .qitem b{color:var(--ink)}
  .qitem .dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--gold);margin-right:7px;vertical-align:1px}
  footer.foot{margin-top:28px;text-align:center;font-size:11.5px;color:var(--ink3);line-height:2}

  @media (max-width:1180px){
    .diag,.acts{grid-template-columns:1fr}
    .mapsection{grid-template-columns:1fr}
    #map{height:440px}
    .hstats{grid-template-columns:repeat(2,1fr);row-gap:18px}
    .hstat:nth-child(2){border-right:0}
    .goals{grid-template-columns:1fr}
    .ia{grid-template-columns:1fr}
    .ia .ins{border-right:0;border-bottom:1px solid var(--line)}
    .quality .qbody{grid-template-columns:1fr}
  }
  @media (max-width:760px){
    .wrap{padding:16px 13px 40px}
    .hero{padding:24px 20px}
    .hero h1{font-size:23px}
    .hstats{grid-template-columns:1fr}
    .hstat{border-right:0;padding-right:0}
    .shead h2{font-size:15.5px}
  }
</style>
</head>
<body>
<div class="wrap">

  <div id="alert"></div>

  <!-- ========== HERO ========== -->
  <section class="hero">
    <div class="in">
      <div class="hbadge"><i></i>布局诊断 · 调整决策</div>
      <h1>门店不会因为多而增长，<em>只会因为对而增长</em></h1>
      <p class="lead">
        基于全国 <span id="mTotal">—</span> 家门店清单的完整测算，当前网络呈现
        <b style="color:#fff">「单城高密度 · 场景单极化 · 时段极窄」</b> 三重特征：
        总量已具备规模优势，但增长动能正在从「加密」转向「渗透」。
        下文每张图都对应一条明确的调整动作。
      </p>
      <div class="hstats">
        <div class="hstat">
          <div class="n" id="dMuni">—<small>%</small></div>
          <div class="l">门店集中在 4 个直辖市<br>（仅 4 座城市承载）</div>
        </div>
        <div class="hstat">
          <div class="n" id="dMall">—<small>%</small></div>
          <div class="l">门店属商场/购物中心场景<br>高依赖、低抗风险</div>
        </div>
        <div class="hstat">
          <div class="n" id="dOpen">—<small>%</small></div>
          <div class="l">门店 06:30 前开门<br>早高峰供给严重偏窄</div>
        </div>
        <div class="hstat">
          <div class="n" id="dGrowth">—<small>个</small></div>
          <div class="l">广覆盖低密度省份<br>增量主战场</div>
        </div>
      </div>
    </div>
  </section>

  <!-- ========== 01 诊断 ========== -->
  <section class="sec">
    <div class="shead">
      <span class="sno">01</span>
      <h2>三条诊断<span class="shsub">问题定位</span></h2>
      <span class="rule"></span>
    </div>
    <div class="diag">
      <div class="dcard r0">
        <span class="lv">高风险</span>
        <h3>单城密度见顶，加密边际收益递减</h3>
        <p>上海 <b id="dxSh">—</b> 家门店却只分布在 <b>1</b> 座城市，北京 <b id="dxBj">—</b> 家同样是单城网络；
        而安徽覆盖 <b>16</b> 城仅有 <b id="dxAh">—</b> 家、山东覆盖 <b>16</b> 城仅 <b id="dxSd">—</b> 家。
        直辖市单城门店密度已是省份型市场的数十倍，继续加密只会同城内卷，而省域多城渗透率仍处于低位。</p>
        <div class="kvrow">
          <div><div class="k">直辖市门店占比</div><div class="v" id="dxMuni">—</div></div>
          <div><div class="k">上海单城门店密度</div><div class="v" id="dxShD">—</div></div>
        </div>
      </div>
      <div class="dcard r0">
        <span class="lv">高风险</span>
        <h3>场景单极化，商场红利已被摊薄</h3>
        <p>商场/购物中心场景独占 <b id="dxMall">—</b> 家（<b id="dxMallP">—</b>），
        而高频刚需场景近乎空白：交通枢纽类合计仅 <b id="dxHub">—</b> 家（<b id="dxHubP">—</b>）、
        社区 <b id="dxComm">—</b> 家、医院/学校 <b id="dxMed">—</b> 家。
        商场客流红利见顶，且租约与客流高度绑定，抗风险能力弱。</p>
        <div class="kvrow">
          <div><div class="k">商场/购物中心门店</div><div class="v" id="dxMall2">—</div></div>
          <div><div class="k">交通枢纽类门店</div><div class="v" id="dxHub2">—</div></div>
        </div>
      </div>
      <div class="dcard r1">
        <span class="lv">中风险</span>
        <h3>时段极窄，夜间存在结构性空转</h3>
        <p>峰值时段 <b id="dxPeak">—</b> 全国有 <b id="dxPeakV">—</b> 家门店同时营业，
        但在 <b id="dxValley">—</b> 仅剩 <b id="dxValleyV">—</b> 家。
        <b id="dxLongP">—</b> 的门店营业时长 ≥14 小时，多数非枢纽门店在夜间低产出时段
        维持「开着但没人」的状态，持续消耗人力与能耗。</p>
        <div class="kvrow">
          <div><div class="k">≥14h 营业门店</div><div class="v" id="dxLong">—</div></div>
          <div><div class="k">全天谷值门店数</div><div class="v" id="dxValley2">—</div></div>
        </div>
      </div>
    </div>
  </section>

  <!-- ========== 02 格局 ========== -->
  <section class="sec">
    <div class="shead">
      <span class="sno">02</span>
      <h2>格局：门店开在哪<span class="shsub">地理分布与省域渗透</span></h2>
      <span class="rule"></span>
    </div>

    <div class="panel">
      <div class="phead">
        <h3>全国门店分布 · 按省级行政区查看</h3>
        <span class="tag" id="mapTag">—</span>
      </div>
      <div class="maptools">
        <label for="provSel">筛选省级行政区</label>
        <select id="provSel"></select>
        <button class="btn ghost" id="resetBtn">重置视图</button>
      </div>
      <div class="hintline">选择省份后地图自动定位到该省范围，右侧同步切换为该省城市明细 · 缩放可展开聚合点 · 点击单个门店查看详情</div>
      <div class="mapsection" style="gap:0">
        <div style="position:relative">
          <div id="map"></div>
          <div id="info"></div>
        </div>
        <aside class="side" style="border-left:1px solid var(--line)">
          <div class="blk">
            <h3 id="sideTitle">省级行政区 Top 8 <em>门店数</em></h3>
            <ul class="rank" id="sideRank"></ul>
          </div>
          <div class="blk" id="sideDetail" style="display:none">
            <div class="kv">
              <div><div class="k">门店总数</div><div class="v" id="dN">—</div></div>
              <div><div class="k">平均营业时长</div><div class="v" id="dH">—</div></div>
            </div>
          </div>
          <div class="blk">
            <h3>渗透率速览</h3>
            <p id="penNote">—</p>
          </div>
          <div class="blk">
            <h3>图例说明</h3>
            <div class="legend">
              <div><i style="background:#006241"></i>聚合数字＝该区域门店数</div>
              <div><i style="background:#c8a15a"></i>点击单点查看门店详情</div>
              <div><i style="background:#8b9aa1"></i>腾讯位置服务底图 · GCJ-02</div>
            </div>
          </div>
        </aside>
      </div>
    </div>

    <div class="panel" style="margin-top:16px">
      <div class="phead">
        <h3>省域渗透四象限 · 门店数 × 覆盖城市数</h3>
        <span class="tag">气泡大小＝平均营业时长</span>
      </div>
      <div class="pbody"><div class="chart tall" id="c_quad"></div></div>
      <div class="ia">
        <div class="ins">
          <div class="cap"><i>观</i>洞察</div>
          <p>29 个省级行政区清晰地分成三层：<b>右上「双高区」</b>广东（<b id="qGp">—</b> 店 /
          <b id="qGpC">—</b> 城）、浙江（<b id="qZj">—</b>）、江苏（<b id="qJs">—</b>）已进入成熟内卷期；
          <b>左上「单城饱和区」</b>沪京津渝四城合计 <b id="qMuni">—</b> 家，只分布在 4 座城市；
          <b>右下「广覆盖低密度区」</b>有 <b id="qGn">—</b> 个省份，覆盖 <b id="qGc">—</b> 座城市却只有
          <b id="qGs">—</b> 家门店，是唯一还有结构性空间的方向。</p>
        </div>
        <div class="act">
          <div class="cap"><i>调</i>调整动作</div>
          <p><span class="num">1</span>新开门店预算的 <b>60%</b> 投向「覆盖城市 ≥11 且门店 &lt;300」的省份（<span id="qNames">—</span>），由「单城加密」转为「省域多城渗透」。</p>
          <p><span class="num">2</span>沪京不再考核门店数量，改考核单店效率（坪效、客单价、外送占比）。</p>
        </div>
      </div>
    </div>
  </section>

  <!-- ========== 03 场景 ========== -->
  <section class="sec">
    <div class="shead">
      <span class="sno">03</span>
      <h2>场景：门店开在哪种位置<span class="shsub">选址结构风险</span></h2>
      <span class="rule"></span>
    </div>
    <div class="panel">
      <div class="phead">
        <h3>选址场景结构 · 门店名称关键词命中</h3>
        <span class="tag">多标签统计 · 单位：家</span>
      </div>
      <div class="pbody"><div class="chart" id="c_scene"></div></div>
      <div class="ia">
        <div class="ins">
          <div class="cap"><i>观</i>洞察</div>
          <p>结构极度单极：商场/购物中心系 <b id="sMall">—</b> 家占 <b id="sMallP">—</b>，是第二大类
          （写字楼/商务区）的两倍以上。而两类价值最高的场景几乎缺席——
          交通枢纽类（机场 <b id="sAir">—</b>、高铁 <b id="sRail">—</b>、枢纽服务区 <b id="sHub">—</b>）合计
          <b id="sHubAll">—</b> 家占 <b id="sHubP">—</b>；
          社区、医院/学校的合计占比不足 <b>2.3%</b>。</p>
        </div>
        <div class="act">
          <div class="cap"><i>调</i>调整动作</div>
          <p><span class="num">1</span>新增点位中商场系占比从 <b id="sMallNow">—</b> 压降至 <b>25%</b> 以内，优先补交通枢纽、医院、高校、办公园区等「高壁垒 · 高频刚需」场景。</p>
          <p><span class="num">2</span>社区场景推小面积「卫星店」模型，覆盖 3 公里生活圈，与商场大店形成业态分工。</p>
        </div>
      </div>
    </div>
  </section>

  <!-- ========== 04 时段 ========== -->
  <section class="sec">
    <div class="shead">
      <span class="sno">04</span>
      <h2>时段：门店什么时候开<span class="shsub">全天供给窗口与时长结构</span></h2>
      <span class="rule"></span>
    </div>
    <div class="panel">
      <div class="phead">
        <h3>全天供给窗口 · 逐小时营业中门店数</h3>
        <span class="tag">阴影＝建议调整时段</span>
      </div>
      <div class="pbody"><div class="chart" id="c_window"></div></div>
      <div class="pbody" style="padding-top:0">
        <div class="strip">
          <div style="font-size:12.5px;font-weight:800;margin-bottom:10px">开店时间分布 <span style="font-weight:500;color:var(--ink3);font-size:11.5px">· 全部 <span id="stTotal">—</span> 家门店 · 单位：家</span></div>
          <div class="sbar" id="stBar"></div>
          <div class="saxis" id="stAxis"></div>
          <div class="snote" id="stNote">—</div>
        </div>
      </div>
      <div class="ia">
        <div class="ins">
          <div class="cap"><i>观</i>洞察</div>
          <p>需求与供给在早上「错峰」：<b id="wPeakShare">—</b> 的门店挤在
          <b>06:31–07:00</b> 才开门，而办公客流的早高峰 06:30–09:00 恰好落在开门瞬间；
          13:00 峰值为 <b id="wPeak">—</b> 家，01:00–05:00 全国仅 <b>61–63</b> 家营业，
          这 4 小时是全时段最空的窗口。</p>
        </div>
        <div class="act">
          <div class="cap"><i>调</i>调整动作</div>
          <p><span class="num">1</span>早班前置：主力门店开店时间前移至 <b>06:00</b>，早餐档（06:30–09:00）单独配置人力与产能，把「开门时间」从成本项转为收入项。</p>
          <p><span class="num">2</span>非枢纽门店打烊前移，压缩 21:00 后低效时段；仅机场/高铁/医院店保留超长营业。</p>
        </div>
      </div>
    </div>

    <div class="panel" style="margin-top:16px">
      <div class="phead">
        <h3>单店营业时长分布</h3>
        <span class="tag">已剔除全天营业/未标注门店</span>
      </div>
      <div class="pbody"><div class="chart" id="c_dur"></div></div>
      <div class="ia">
        <div class="ins">
          <div class="cap"><i>观</i>洞察</div>
          <p>时长高度集中在 <b>11–16 小时</b>区间：≥14 小时的达 <b id="dLong">—</b> 家（<b id="dLongP">—</b>），
          中位数 <b id="dMed">—</b> 小时，而 ≤10 小时的仅 <b id="dShort">—</b> 家。
          区域差异来自商圈属性而非管理能力——湖南 <b>14.52h</b>、海南 <b>14.55h</b>（旅游与夜经济）
          显著高于山东 <b>13.00h</b>、天津 <b>12.96h</b>（商务办公型）。</p>
        </div>
        <div class="act">
          <div class="cap"><i>调</i>调整动作</div>
          <p><span class="num">1</span>按城市属性分类设定营业时长标准：旅游/夜经济城市维持 <b>14.5h+</b>，商务型城市下探至 <b>13h</b>。</p>
          <p><span class="num">2</span>把缩时省下的人力对冲早高峰加班成本，实现「总工时不变、有效工时提升」。</p>
        </div>
      </div>
    </div>
  </section>

  <!-- ========== 05 优先级 ========== -->
  <section class="sec">
    <div class="shead">
      <span class="sno">05</span>
      <h2>优先级：先做哪一件<span class="shsub">战略影响 × 落地难度</span>
      <span class="rule"></span>
    </div>
    <div class="panel">
      <div class="phead">
        <h3>调整动作优先级矩阵</h3>
        <span class="tag">越靠左上越应优先执行</span>
      </div>
      <div class="pbody" id="matrix"></div>
    </div>
  </section>

  <!-- ========== 06 行动清单 ========== -->
  <section class="sec">
    <div class="shead">
      <span class="sno">06</span>
      <h2>六项调整动作<span class="shsub">依据 → 动作 → 目标</span></h2>
      <span class="rule"></span>
    </div>
    <div class="acts">
      <div class="acard">
        <div class="ah"><span class="pri p0">P0</span><h4>增量下沉到省域多城</h4></div>
        <div class="row"><span class="lb">依据</span><span>直辖市 4 城承载 <b id="a1a">—</b> 家门店；<b id="a1b">—</b> 个省份覆盖 11 城以上但门店不足 300 家。</span></div>
        <div class="row"><span class="lb">动作</span><span>新开店预算 <b>60%</b> 投向广覆盖低密度省份，按「省会—地级市—县域」三级节奏推进。</span></div>
        <div class="row target"><span class="lb">目标</span><span>12 个月内省域多城新增占比 ≥60%，直辖市门店占比降至 22% 以下。</span></div>
      </div>
      <div class="acard">
        <div class="ah"><span class="pri p0">P0</span><h4>早高峰资源前置</h4></div>
        <div class="row"><span class="lb">依据</span><span>仅 <b id="a2a">—</b> 家门店 06:30 前开门，<b id="a2b">—</b> 挤在 06:31–07:00 开门，早高峰供给偏窄。</span></div>
        <div class="row"><span class="lb">动作</span><span>开店时间前移至 <b>06:00</b>，早餐档独立配置人力、产能与预约自提入口。</span></div>
        <div class="row target"><span class="lb">目标</span><span>06:30 前开门门店占比从 <b id="a2c">—</b> 提升至 <b>50%</b>，早餐时段营收占比提升 5pct。</span></div>
      </div>
      <div class="acard">
        <div class="ah"><span class="pri p0">P0</span><h4>场景去单极化</h4></div>
        <div class="row"><span class="lb">依据</span><span>商场/购物中心系占 <b id="a3a">—</b>，交通枢纽类仅 <b id="a3b">—</b>，社区与医院学校不足 2.3%。</span></div>
        <div class="row"><span class="lb">动作</span><span>新增点位商场系占比设上限，优先补交通枢纽（机场/高铁/服务区）、医院、高校、办公园区。</span></div>
        <div class="row target"><span class="lb">目标</span><span>商场系占比降至 <b>25%</b> 以内，枢纽+写字楼+医疗教育合计占比提升至 <b>35%</b>。</span></div>
      </div>
      <div class="acard">
        <div class="ah"><span class="pri p1">P1</span><h4>非枢纽店夜间缩时</h4></div>
        <div class="row"><span class="lb">依据</span><span><b id="a4a">—</b> 门店营业 ≥14h，而 01:00–05:00 全国仅 <b id="a4b">—</b> 家在营，夜间产出极低。</span></div>
        <div class="row"><span class="lb">动作</span><span>非枢纽门店打烊时间由 22:00 前移至 21:00，压缩低效时段人力与能耗。</span></div>
        <div class="row target"><span class="lb">目标</span><span>≥14h 营业门店占比从 <b id="a4c">—</b> 降至 <b>45%</b>，单店月均人力成本下降 3–5%。</span></div>
      </div>
      <div class="acard">
        <div class="ah"><span class="pri p1">P1</span><h4>按城市属性差异化时长</h4></div>
        <div class="row"><span class="lb">依据</span><span>湖南、海南平均营业时长 ≥14.5h，山东、天津仅约 13h，差异来自商圈属性。</span></div>
        <div class="row"><span class="lb">动作</span><span>建立「旅游/夜经济 / 商务办公 / 社区」三类时长标准，替代全国统一营业时间表。</span></div>
        <div class="row target"><span class="lb">目标</span><span>三类城市时长标准全覆盖，旅游型城市晚市营收占比提升 3pct。</span></div>
      </div>
      <div class="acard">
        <div class="ah"><span class="pri p2">P2</span><h4>低效网点转自提/卫星点</h4></div>
        <div class="row"><span class="lb">依据</span><span>部分门店位于低密度区域，坪效低于均值，但周边 3 公里仍有稳定外送需求。</span></div>
        <div class="row"><span class="lb">动作</span><span>将低效大店转为「自提点 / 卫星厨房」，压缩面积与人力，保留外送与自提产能。</span></div>
        <div class="row target"><span class="lb">目标</span><span>首批试点 50 家，单店坪效提升 15% 以上。</span></div>
      </div>
    </div>
  </section>

  <!-- ========== 07 质量 ========== -->
  <section class="sec panel quality">
    <div class="shead" style="padding:18px 20px 0;margin:0">
      <span class="sno">07</span>
      <h2>数据质量与统计口径</h2>
      <span class="rule"></span>
    </div>
    <div class="qbody" style="padding-top:16px">
      <div class="qitem"><span class="dot"></span><b>字段异常处理</b><br>
        原始数据存在系统性列串位：坐标异常 <b id="qGeo">—</b> 行、省份列异常 <b id="qProv">—</b> 行、城市列异常 <b id="qCity">—</b> 行。此类记录已剔除出地图与区域统计，其余分析按可用字段保留。</div>
      <div class="qitem"><span class="dot"></span><b>口径修正</b><br>
        按原始字段直接统计会得出「覆盖 36 个省级行政区」，剔除串位值后真实为 <b id="qProvN">—</b> 个省级行政区（直辖市按省级计）、<b id="qCityN">—</b> 个城市；门店总数 <b id="qTotal">—</b> 家。</div>
      <div class="qitem"><span class="dot"></span><b>时长与场景口径</b><br>
        营业时长＝闭店 − 开店并对跨零点门店加 24 小时；<b id="qSame">—</b> 家门店开店时间等于闭店时间（多为 00:00–00:00）按疑似全天营业处理，不纳入时长均值。场景为门店名称正则匹配的多标签统计，仅反映选址倾向。</div>
    </div>
  </section>

  <footer class="foot">
    本看板由上传的门店清单自动生成 · 全部结论以「数据质量与统计口径」为准<br>
    地图底图 © 腾讯位置服务（合规地图源）· 图表引擎 ECharts（已内联，无外部依赖）
  </footer>
</div>

<script>
const DATA = __DATA__;
const S = DATA.summary;
const D = DATA.derived;
window.__chartErr = [];

function txt(id, v){ var e = document.getElementById(id); if(e) e.textContent = v; }
function showAlert(msg){
  var a = document.getElementById('alert');
  a.innerHTML = msg; a.style.display = 'block';
}

/* ---------- 文案数据绑定 ---------- */
txt('mTotal', S.total.toLocaleString());
txt('dMuni', D.muniShare); txt('dMall', D.mallShare);
txt('dOpen', D.openBefore0630Share); txt('dGrowth', D.growthN);

txt('dxSh', D.shDensity.toLocaleString());
txt('dxBj', D.bjDensity.toLocaleString());
txt('dxAh', D.ahStores); txt('dxSd', D.sdStores);
txt('dxMuni', D.muniShare + '%');
txt('dxShD', D.shDensity.toLocaleString() + ' 家/城');
txt('dxMall', D.mall.toLocaleString()); txt('dxMallP', D.mallShare + '%');
txt('dxHub', D.hub); txt('dxHubP', D.hubShare + '%');
txt('dxComm', D.community); txt('dxMed', D.medSchool);
txt('dxMall2', D.mall.toLocaleString() + ' 家'); txt('dxHub2', D.hub + ' 家');
txt('dxPeak', D.peakName); txt('dxPeakV', D.peakVal.toLocaleString());
txt('dxValley', D.valleyName); txt('dxValleyV', D.valleyVal);
txt('dxLongP', D.longShare + '%'); txt('dxLong', D.longN.toLocaleString() + ' 家');
txt('dxValley2', D.valleyVal + ' 家');

txt('penNote', '上海单城门店密度 ' + D.shDensity.toLocaleString() + ' 家/城，安徽仅 '
  + D.ahDensity + ' 家/城、山东 ' + D.sdDensity + ' 家/城——直辖市与省域市场处于完全不同的渗透阶段。');

txt('qGp', D.gpStores); txt('qGpC', D.gpCities); txt('qZj', D.zjStores); txt('qJs', D.jsStores);
txt('qMuni', D.muniN.toLocaleString());
txt('qGn', D.growthN); txt('qGc', D.growthCities); txt('qGs', D.growthStores.toLocaleString());
txt('qNames', D.growthNames);

var sc = {}; S.scene.forEach(function(d){ sc[d['场景']] = d; });
txt('sMall', (sc['商场/购物中心']||{}).门店数 || 0);
txt('sMallP', ((sc['商场/购物中心']||{}).占比 || 0) + '%');
txt('sAir', (sc['机场']||{}).门店数 || 0);
txt('sRail', (sc['高铁/火车站']||{}).门店数 || 0);
txt('sHub', (sc['交通枢纽/服务区']||{}).门店数 || 0);
txt('sHubAll', D.hub); txt('sHubP', D.hubShare + '%');
txt('sMallNow', D.mallShare + '%');

txt('wPeakShare', D.peakOpenShare + '%'); txt('wPeak', D.peakVal.toLocaleString());
txt('dLong', D.longN.toLocaleString()); txt('dLongP', D.longShare + '%');
txt('dMed', S.median_hours); txt('dShort', D.shortN);

txt('a1a', D.muniN.toLocaleString()); txt('a1b', D.growthN);
txt('a2a', D.openBefore0630.toLocaleString()); txt('a2b', D.peakOpenShare + '%'); txt('a2c', D.openBefore0630Share + '%');
txt('a3a', D.mallShare + '%'); txt('a3b', D.hubShare + '%');
txt('a4a', D.longShare + '%'); txt('a4b', D.valleyVal); txt('a4c', D.longShare + '%');

txt('qGeo', S.geo_bad); txt('qProv', S.prov_bad); txt('qCity', S.city_bad);
txt('qProvN', S.province_n); txt('qCityN', S.city_n); txt('qTotal', S.total.toLocaleString());
txt('qSame', S.same_time_n);

/* ---------- 省份下拉 ---------- */
var selEl = document.getElementById('provSel');
(function(){
  if(!selEl) return;   /* 容器缺失时不影响后续统计与图表 */
  var o0 = document.createElement('option');
  o0.value = ''; o0.textContent = '全部省级行政区（' + DATA.provs.length + ' 个）';
  selEl.appendChild(o0);
  DATA.provs.forEach(function(p){
    var o = document.createElement('option');
    o.value = p; o.textContent = p + '（' + (DATA.provCount[p]||0) + ' 家）';
    selEl.appendChild(o);
  });
})();

/* ---------- 侧栏排行 ---------- */
var PROV_RANK = S.province_all.slice(0,8);
function renderRank(items, maxv){
  return items.map(function(p,i){
    var w = maxv > 0 ? (p.value / maxv * 100).toFixed(1) : 0;
    return '<li><span class="no">' + (i+1) + '</span><span style="flex:1;min-width:0">'
      + '<span style="display:flex;justify-content:space-between;gap:8px">'
      + '<span class="nm">' + p.name + '</span><span class="vv">' + p.value + '</span></span>'
      + '<span class="bar"><i style="width:' + w + '%"></i></span></span></li>';
  }).join('');
}
function renderSide(prov){
  var title = document.getElementById('sideTitle');
  var list  = document.getElementById('sideRank');
  var det   = document.getElementById('sideDetail');
  if(!prov){
    title.innerHTML = '省级行政区 Top 8 <em>门店数</em>';
    list.innerHTML = renderRank(PROV_RANK, PROV_RANK[0].value);
    det.style.display = 'none';
  } else {
    var d = DATA.provDetail[prov];
    if(!d){ return; }
    title.innerHTML = prov + ' 城市 Top 8 <em>门店数</em>';
    list.innerHTML = renderRank(d.cities, d.cities[0].value);
    det.style.display = 'block';
    document.getElementById('dN').textContent = d.n + ' 家';
    document.getElementById('dH').textContent = (d.hoursMean == null ? '—' : d.hoursMean + ' h');
  }
}
renderSide('');

/* ---------- ECharts 基础 ---------- */
var INK='#0f1e26', INK2='#4d6169', INK3='#8296a1', LINE='#e1e9ec', HAIR='#eff4f6';
var BRAND='#006241', BRAND2='#00a862', GOLD='#b8893f', AMBER='#c96f16', RED='#b3382c';
var axisBase = {
  axisLine:{lineStyle:{color:LINE}}, axisTick:{show:false},
  axisLabel:{color:INK2,fontSize:11}, splitLine:{lineStyle:{color:HAIR,type:'dashed'}}
};
/* 渐变必须用对象写法：类实例在配置合并时会丢失颜色 */
function vGrad(c1,c2){ return {type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:c2},{offset:1,color:c1}]}; }
function hGrad(c1,c2){ return {type:'linear',x:0,y:0,x2:1,y2:0,colorStops:[{offset:0,color:c1},{offset:1,color:c2}]}; }
function tipBase(){
  return {trigger:'axis',backgroundColor:'rgba(255,255,255,.97)',borderColor:LINE,
    borderWidth:1,padding:[9,12],textStyle:{color:INK,fontSize:12},
    extraCssText:'border-radius:10px;box-shadow:0 8px 26px rgba(15,30,38,.13)'};
}

var CHARTS = [];
function safeChart(id, fn){
  var el = document.getElementById(id);
  if(!el){ window.__chartErr.push(id + '：容器不存在'); return null; }
  try{
    var c = fn(el);
    if(c) CHARTS.push(c);
    return c;
  }catch(e){
    window.__chartErr.push(id + '：' + e.message);
    el.innerHTML = '<div class="cerr">图表渲染失败<br>' + e.message + '</div>';
    return null;
  }
}

/* ---------- 图 1：省域渗透四象限（气泡散点） ---------- */
safeChart('c_quad', function(el){
  var rows = DATA.provStats;
  var NAMED = {'上海市':1,'北京市':1,'广东省':1,'浙江省':1,'江苏省':1,'四川省':1,'山东省':1,
               '安徽省':1,'湖北省':1,'天津市':1,'重庆市':1};
  var data = rows.map(function(d){
    return {
      name: d.name, value: [d.cities, d.stores, d.hours, d.density],
      symbolSize: Math.max(11, Math.min(46, Math.sqrt(d.stores) * 1.15)),
      label:{show: !!NAMED[d.name]}
    };
  });
  var chart = echarts.init(el);
  chart.setOption({
    grid:{left:16,right:64,top:44,bottom:36,containLabel:true},
    legend:{show:false},
    tooltip:Object.assign(tipBase(), {trigger:'item',
      formatter:function(p){
        var v = p.value;
        return '<b style="font-size:13px">' + p.name + '</b><br/>'
          + '门店数：<b>' + v[1].toLocaleString() + '</b> 家<br/>'
          + '覆盖城市：<b>' + v[0] + '</b> 个<br/>'
          + '单城门店密度：<b>' + v[3] + '</b> 家/城<br/>'
          + '平均营业时长：<b>' + v[2] + '</b> 小时';
      }}),
    xAxis:Object.assign({type:'value',name:'覆盖城市数（个）',
      nameLocation:'middle',nameGap:22,
      nameTextStyle:{color:INK3,fontSize:11},
      min:0,max:23,interval:5}, axisBase, {splitLine:{lineStyle:{color:HAIR,type:'dashed'}}}),
    yAxis:Object.assign({type:'value',name:'门店数（家）',
      nameLocation:'end',nameGap:16,
      nameTextStyle:{color:INK3,fontSize:11,align:'left'}}, axisBase),
    series:[{
      type:'scatter', data:data,
      labelLayout:{hideOverlap:true},
      itemStyle:{
        color:function(p){
          var c = p.value[0], s = p.value[1];
          if(s >= 300 && c >= 11) return {type:'radial',x:.5,y:.4,r:.7,
            colorStops:[{offset:0,color:'#3fd39a'},{offset:1,color:'#00774f'}]};
          if(c <= 3 && s >= 140) return {type:'radial',x:.5,y:.4,r:.7,
            colorStops:[{offset:0,color:'#e88574'},{offset:1,color:'#b3382c'}]};
          if(c >= 11) return {type:'radial',x:.5,y:.4,r:.7,
            colorStops:[{offset:0,color:'#f0cf94'},{offset:1,color:'#c08b34'}]};
          return {type:'radial',x:.5,y:.4,r:.7,
            colorStops:[{offset:0,color:'#a9bcc5'},{offset:1,color:'#6c8189'}]};
        },
        opacity:.9, shadowBlur:10, shadowColor:'rgba(15,30,38,.14)'
      },
      label:{color:INK,fontSize:11,fontWeight:700,position:'top',distance:5,
        formatter:function(p){ return p.name.replace(/(省|市|自治区|壮族|回族|维吾尔)/g,''); }},
      emphasis:{scale:1.12, itemStyle:{borderColor:'#fff',borderWidth:2}},
      markLine:{
        silent:true, symbol:'none',
        lineStyle:{color:'#c8d3d8',type:'dashed',width:1},
        data:[
          {xAxis:11, name:'覆盖广度线 11 城',
           label:{formatter:'覆盖广度线 11 城',position:'end',color:'#a2b3bb',fontSize:10}},
          {yAxis:300, name:'规模线 300 家',
           label:{formatter:'规模线 300 家',position:'insideEndRight',color:'#a2b3bb',fontSize:10}}
        ]
      },
      markArea:{silent:true, itemStyle:{opacity:1}, data:[
        [{name:'双高成熟区', xAxis:11, yAxis:300, itemStyle:{color:'rgba(0,166,98,.05)'},
          label:{show:true,position:'insideTopRight',color:'#7fae9c',fontSize:11,fontWeight:700,padding:[4,8,0,0]}},
         {xAxis:23, yAxis:1200}],
        [{name:'单城饱和区', xAxis:0, yAxis:300, itemStyle:{color:'rgba(179,56,44,.05)'},
          label:{show:true,position:'insideTop',color:'#cf8f86',fontSize:11,fontWeight:700,padding:[4,0,0,0]}},
         {xAxis:11, yAxis:1200}],
        [{name:'广覆盖 · 待加密增长区', xAxis:11, yAxis:0, itemStyle:{color:'rgba(184,137,63,.07)'},
          label:{show:true,position:'insideBottomRight',color:'#c9a56b',fontSize:11,fontWeight:700,padding:[0,8,4,0]}},
         {xAxis:23, yAxis:300}]
      ]}
    }]
  });
  return chart;
});

/* ---------- 图 2：选址场景结构 ---------- */
safeChart('c_scene', function(el){
  var rows = S.scene.slice().sort(function(a,b){ return a.门店数 - b.门店数; });
  var chart = echarts.init(el);
  chart.setOption({
    grid:{left:6,right:96,top:16,bottom:8,containLabel:true},
    tooltip:Object.assign(tipBase(), {axisPointer:{type:'shadow'},
      formatter:function(p){
        var d = rows.filter(function(r){ return r.场景 === p[0].name; })[0] || {};
        return '<b>' + p[0].name + '</b><br/>门店数：<b>' + p[0].value + '</b> 家<br/>占比：<b>' + (d.占比||0) + '%</b>';
      }}),
    xAxis:Object.assign({type:'value',axisLine:{show:false}},axisBase,{splitLine:{lineStyle:{color:HAIR,type:'dashed'}}}),
    yAxis:Object.assign({type:'category',data:rows.map(function(r){return r.场景;})},
      axisBase,{splitLine:{show:false},axisLabel:{color:INK,fontSize:11.5,fontWeight:600}}),
    series:[{
      type:'bar', barWidth:'56%',
      data:rows.map(function(r,i){
        var isMall = r.场景 === '商场/购物中心';
        return {value:r.门店数, itemStyle:{borderRadius:[0,5,5,0],
          color: isMall ? hGrad('#b8893f','#f0cf94') : hGrad('#0a7a56','#63d3a6')}};
      }),
      label:{show:true,position:'right',color:INK2,fontSize:11,fontWeight:700,
        formatter:function(p){
          var d = rows[p.dataIndex] || {};
          return p.value + ' 家 · ' + (d.占比||0) + '%';
        }}
    }]
  });
  return chart;
});

/* ---------- 图 3：全天供给窗口 ---------- */
safeChart('c_window', function(el){
  var prof = S.hours_profile;
  var chart = echarts.init(el);
  chart.setOption({
    grid:{left:16,right:26,top:34,bottom:10,containLabel:true},
    tooltip:Object.assign(tipBase(), {
      formatter:function(p){ return p[0].name + '<br/>营业中门店 <b>' + p[0].value.toLocaleString() + '</b> 家'; }}),
    xAxis:Object.assign({type:'category',boundaryGap:false,data:prof.map(function(r){return r.name;})},
      axisBase,{axisLabel:{color:INK2,fontSize:10,interval:1,formatter:function(v){return v.slice(0,2);}}}),
    yAxis:Object.assign({type:'value',name:'营业中门店（家）',
      nameTextStyle:{color:INK3,fontSize:11,padding:[0,0,8,0]}},axisBase),
    series:[{
      type:'line', data:prof.map(function(r){return r.value;}), smooth:true,
      symbol:'circle', symbolSize:6, showSymbol:false,
      lineStyle:{color:BRAND,width:2.8}, itemStyle:{color:BRAND},
      areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[
        {offset:0,color:'rgba(0,166,98,.34)'},{offset:1,color:'rgba(0,166,98,.02)'}]}},
      label:{show:true,color:BRAND,fontSize:10,fontWeight:700,position:'top',
        formatter:function(p){ return (p.dataIndex % 3 === 0) ? p.value.toLocaleString() : ''; }},
      markArea:{silent:true, data:[
        [{name:'早高峰供给缺口 · 建议前置开门', xAxis:'05:00', itemStyle:{color:'rgba(201,111,22,.09)'},
          label:{show:true,position:'insideTop',color:'#b3771f',fontSize:11,fontWeight:700,padding:[6,0,0,0]}},
         {xAxis:'09:00'}],
        [{name:'夜间空转时段 · 建议缩时', xAxis:'01:00', itemStyle:{color:'rgba(130,150,161,.10)'},
          label:{show:true,position:'insideTop',color:'#7b8e98',fontSize:11,fontWeight:700,padding:[6,0,0,0]}},
         {xAxis:'05:00'}]
      ]},
      markPoint:{symbol:'circle',symbolSize:9,data:[
        {name:'峰值',coord:[D.peakName, D.peakVal],
         itemStyle:{color:GOLD},label:{show:true,position:'top',color:'#9a7229',fontSize:11,fontWeight:700,
           formatter:'峰值 ' + D.peakName + ' · ' + D.peakVal.toLocaleString() + ' 家'}},
        {name:'谷值',coord:[D.valleyName, D.valleyVal],
         itemStyle:{color:'#8296a1'},label:{show:true,position:'bottom',color:'#5d7078',fontSize:11,fontWeight:700,
           formatter:'谷值 ' + D.valleyName + ' · ' + D.valleyVal + ' 家'}}
      ]}
    }]
  });
  return chart;
});

/* ---------- 图 4：营业时长分布 ---------- */
safeChart('c_dur', function(el){
  var rows = S.hours_hist;
  var chart = echarts.init(el);
  chart.setOption({
    grid:{left:16,right:26,top:40,bottom:10,containLabel:true},
    tooltip:Object.assign(tipBase(), {
      formatter:function(p){ return p[0].name + '<br/>门店 <b>' + p[0].value.toLocaleString() + '</b> 家'; }}),
    xAxis:Object.assign({type:'category',data:rows.map(function(r){return r.name;})},
      axisBase,{axisLabel:{color:INK2,fontSize:10,interval:0,rotate:38}}),
    yAxis:Object.assign({type:'value',name:'门店数（家）',
      nameTextStyle:{color:INK3,fontSize:11,padding:[0,0,8,0]}},axisBase),
    series:[{
      type:'bar', barWidth:'58%',
      data:rows.map(function(r){
        var v = parseInt(r.name, 10);
        var strong = (r.name === '15-16h' || r.name === '14-15h');
        return {value:r.value, itemStyle:{borderRadius:[4,4,0,0],
          color: strong ? vGrad('#006241','#4ecb9b') : vGrad('#8fbcac','#cfe5db')}};
      }),
      label:{show:true,position:'top',color:INK2,fontSize:10,fontWeight:700,
        formatter:function(p){ return p.value >= 200 ? p.value.toLocaleString() : ''; }},
      markLine:{silent:true, symbol:'none', data:[
        {xAxis:'13-14h', name:'中位 14h', lineStyle:{color:GOLD,type:'dashed',width:1.4},
         label:{formatter:'中位 ' + S.median_hours + 'h',color:'#9a7229',fontSize:11,fontWeight:700,position:'end'}}
      ]}
    }]
  });
  return chart;
});

/* ---------- 开店时间条带（CSS） ---------- */
(function(){
  var rows = D.openSlot;
  var sum = rows.reduce(function(a, b){ return a + b.value; }, 0) || 1;   /* 宽度按条带内部合计归一 */
  var tot = S.total || sum;                                              /* 占比统一以门店总数为分母 */
  var COL = ['#cfe3da','#9fcdb8','#006241','#2f9c74','#63cba1','#9bcdb9','#bcd9cd','#d9e6e0'];
  var widths = rows.map(function(r){ return r.value / sum * 100; });
  var pcts   = rows.map(function(r){ return r.value / tot * 100; });
  document.getElementById('stBar').innerHTML = rows.map(function(r, i){
    return '<span style="flex:0 0 ' + widths[i].toFixed(3) + '%;background:' + COL[i % COL.length]
      + '" title="' + r.name + '：' + r.value + ' 家（' + pcts[i].toFixed(1) + '%）">'
      + (widths[i] >= 11 ? r.value.toLocaleString() + ' 家 · ' + pcts[i].toFixed(1) + '%' : '') + '</span>';
  }).join('');
  document.getElementById('stAxis').innerHTML = rows.map(function(r, i){
    return '<span style="flex:0 0 ' + widths[i].toFixed(3) + '%;text-align:center;white-space:nowrap;'
      + (widths[i] < 4.5 ? 'visibility:hidden' : '') + '">' + r.name + '</span>';
  }).join('');
  txt('stTotal', S.total.toLocaleString());
  txt('stNote', '06:30 前开门的门店仅 ' + D.openBefore0630.toLocaleString() + ' 家（'
    + D.openBefore0630Share + '%），而 06:31–07:00 一个半小时内集中了 ' + D.peakOpenShare + '% 的门店开门——'
    + '供给窗口与办公客流早高峰几乎同时打开，早餐档产能与人力的前置空间是最大的确定性增量。');
})();

/* ---------- 优先级矩阵（SVG） ---------- */
(function(){
  var W = 680, PL = 96, PR = 26, PT = 60, PB = 44;
  var X0 = PL, X1 = W - PR, Y0 = PT, Y1 = 314;
  var px = function(v){ return X0 + v * (X1 - X0); };
  var py = function(v){ return Y1 - v * (Y1 - Y0); };
  var items = [
    {n:'增量下沉省域多城', d:.62, i:.96, p0:true},
    {n:'早高峰资源前置',   d:.25, i:.85, p0:true},
    {n:'场景去单极化',     d:.76, i:.78, p0:true},
    {n:'非枢纽店夜间缩时', d:.26, i:.58, p0:false},
    {n:'分城市差异时长',   d:.48, i:.40, p0:false},
    {n:'低效店转自提点',   d:.82, i:.60, p0:false}
  ];
  var CX = 0.5, CY = 0.5, mx = px(CX), my = py(CY);
  var s = [];
  s.push('<svg viewBox="0 0 ' + W + ' 384" width="100%" height="auto" role="img" aria-label="调整动作优先级矩阵" '
       + 'style="display:block;font-family:PingFang SC,Microsoft YaHei,sans-serif">');
  s.push('<defs>'
    + '<linearGradient id="qg1" x1="0" y1="0" x2="1" y2="1">'
    + '<stop offset="0" stop-color="#eafaef"/><stop offset="1" stop-color="#ffffff"/></linearGradient>'
    + '<linearGradient id="qg2" x1="0" y1="0" x2="1" y2="1">'
    + '<stop offset="0" stop-color="#fdf7ea"/><stop offset="1" stop-color="#ffffff"/></linearGradient>'
    + '<linearGradient id="chip0" x1="0" y1="0" x2="1" y2="0">'
    + '<stop offset="0" stop-color="#00402c"/><stop offset="1" stop-color="#0a7a56"/></linearGradient>'
    + '<linearGradient id="chip1" x1="0" y1="0" x2="1" y2="0">'
    + '<stop offset="0" stop-color="#5d7078"/><stop offset="1" stop-color="#8296a1"/></linearGradient>'
    + '<linearGradient id="axg" x1="0" y1="0" x2="1" y2="0">'
    + '<stop offset="0" stop-color="#c8d3d8"/><stop offset="1" stop-color="#006241"/></linearGradient>'
    + '<linearGradient id="ayg" x1="0" y1="1" x2="0" y2="0">'
    + '<stop offset="0" stop-color="#c8d3d8"/><stop offset="1" stop-color="#006241"/></linearGradient>'
    + '</defs>');
  /* 象限底色 */
  s.push('<rect x="' + X0 + '" y="' + Y0 + '" width="' + (mx - X0) + '" height="' + (my - Y0) + '" fill="url(#qg1)"/>');
  s.push('<rect x="' + mx + '" y="' + Y0 + '" width="' + (X1 - mx) + '" height="' + (my - Y0) + '" fill="url(#qg2)"/>');
  s.push('<rect x="' + X0 + '" y="' + my + '" width="' + (mx - X0) + '" height="' + (Y1 - my) + '" fill="#fbfcfd"/>');
  s.push('<rect x="' + mx + '" y="' + my + '" width="' + (X1 - mx) + '" height="' + (Y1 - my) + '" fill="#fafbfc"/>');
  /* 网格 */
  for(var g = 1; g <= 4; g++){
    var gx = px(g / 5), gy = py(g / 5);
    s.push('<line x1="' + gx + '" y1="' + Y0 + '" x2="' + gx + '" y2="' + Y1 + '" stroke="#eef3f5" stroke-width="1"/>');
    s.push('<line x1="' + X0 + '" y1="' + gy + '" x2="' + X1 + '" y2="' + gy + '" stroke="#eef3f5" stroke-width="1"/>');
  }
  /* 象限标签（置于绘图区上方，避免与动作标签重叠） */
  s.push('<text x="' + X0 + '" y="' + (Y0 - 13) + '" font-size="11.5" font-weight="700" fill="#3f9c74">优先执行区 · 高影响 / 低难度</text>');
  s.push('<text x="' + X1 + '" y="' + (Y0 - 13) + '" font-size="11.5" font-weight="700" fill="#c2a068" text-anchor="end">战略投入区 · 高影响 / 高难度</text>');
  s.push('<text x="' + (X0 + 12) + '" y="' + (Y1 - 12) + '" font-size="11.5" font-weight="700" fill="#a6b6bd">可延后区</text>');
  s.push('<text x="' + (X1 - 12) + '" y="' + (Y1 - 12) + '" font-size="11.5" font-weight="700" fill="#a6b6bd" text-anchor="end">资源受限 · 观察区</text>');
  /* 分隔线 */
  s.push('<line x1="' + mx + '" y1="' + Y0 + '" x2="' + mx + '" y2="' + Y1 + '" stroke="#dbe5e9" stroke-width="1.2" stroke-dasharray="5 4"/>');
  s.push('<line x1="' + X0 + '" y1="' + my + '" x2="' + X1 + '" y2="' + my + '" stroke="#dbe5e9" stroke-width="1.2" stroke-dasharray="5 4"/>');
  /* 坐标轴 */
  s.push('<line x1="' + X0 + '" y1="' + Y1 + '" x2="' + X1 + '" y2="' + Y1 + '" stroke="url(#axg)" stroke-width="1.6"/>');
  s.push('<line x1="' + X0 + '" y1="' + Y1 + '" x2="' + X0 + '" y2="' + Y0 + '" stroke="url(#ayg)" stroke-width="1.6"/>');
  s.push('<text x="' + ((X0 + X1) / 2) + '" y="' + (Y1 + 34) + '" font-size="12" font-weight="700" fill="#4d6169" text-anchor="middle">落地难度 →</text>');
  s.push('<text x="' + (X0 - 58) + '" y="' + ((Y0 + Y1) / 2) + '" font-size="12" font-weight="700" fill="#4d6169" '
       + 'text-anchor="middle" transform="rotate(-90 ' + (X0 - 58) + ' ' + ((Y0 + Y1) / 2) + ')">战略影响 →</text>');
  s.push('<text x="' + (X0 - 12) + '" y="' + (Y0 + 12) + '" font-size="10.5" fill="#8296a1" text-anchor="end">高</text>');
  s.push('<text x="' + (X0 - 12) + '" y="' + (Y1 - 2) + '" font-size="10.5" fill="#8296a1" text-anchor="end">低</text>');
  s.push('<text x="' + (X0 + 2) + '" y="' + (Y1 + 18) + '" font-size="10.5" fill="#8296a1">低</text>');
  s.push('<text x="' + (X1 - 2) + '" y="' + (Y1 + 18) + '" font-size="10.5" fill="#8296a1" text-anchor="end">高</text>');
  /* 动作标签 */
  items.forEach(function(it, idx){
    var cx = px(it.d), cy = py(it.i), w = 122, h = 27;
    var left = Math.max(X0 + 3, Math.min(X1 - w - 3, cx - w / 2));
    var top  = Math.max(Y0 + 2, Math.min(Y1 - h - 3, cy - h / 2));
    s.push('<rect x="' + left.toFixed(1) + '" y="' + top.toFixed(1) + '" width="' + w + '" height="' + h
      + '" rx="8" fill="url(#' + (it.p0 ? 'chip0' : 'chip1') + ')" opacity="0.95"/>');
    s.push('<text x="' + (left + w / 2).toFixed(1) + '" y="' + (top + 17.5).toFixed(1)
      + '" font-size="11.5" font-weight="700" fill="#ffffff" text-anchor="middle">' + it.n + '</text>');
  });
  s.push('</svg>');
  document.getElementById('matrix').innerHTML = s.join('');
})();

/* ---------- 地图 ---------- */
var map = null, cluster = null, GEOMS = null;
function applyProvince(v){
  var infoEl = document.getElementById('info');
  if(map && cluster && GEOMS){
    var list = v ? GEOMS.filter(function(g){ return g.properties.prov === v; }) : GEOMS;
    cluster.setGeometries(list);
    if(v && list.length){
      try{
        var lonMin=1e9, lonMax=-1e9, latMin=1e9, latMax=-1e9;
        list.forEach(function(g){
          var lo=g.position.getLng(), la=g.position.getLat();
          if(lo<lonMin)lonMin=lo; if(lo>lonMax)lonMax=lo;
          if(la<latMin)latMin=la; if(la>latMax)latMax=la;
        });
        map.fitBounds(new TMap.LatLngBounds(new TMap.LatLng(latMin,lonMin), new TMap.LatLng(latMax,lonMax)), {padding:60});
      }catch(e){ map.setCenter(new TMap.LatLng(34.6,107.5)); map.setZoom(5); }
    } else {
      map.setCenter(new TMap.LatLng(34.6,107.5)); map.setZoom(5);
    }
  }
  if(infoEl) infoEl.style.display = 'none';
  var n = v ? (DATA.provCount[v] || 0) : DATA.mapN;
  var tagEl = document.getElementById('mapTag');
  if(tagEl) tagEl.textContent = n.toLocaleString() + ' 家门店' + (v ? (' · ' + v) : '');
  renderSide(v);
}
function initMap(){
  var infoEl = document.getElementById('info');
  map = new TMap.Map('map', { center:new TMap.LatLng(34.6, 107.5), zoom:5, pitch:0, viewMode:'2D' });
  GEOMS = DATA.points.map(function(p, i){
    return { id:'s' + i, position:new TMap.LatLng(p[0], p[1]),
      properties:{ name:p[2], prov:DATA.provs[p[3]], city:DATA.cities[p[4]], hours:p[5] } };
  });
  cluster = new TMap.MarkerCluster({
    id:'stores', map:map, enableDefaultStyle:true, minimumClusterSize:3,
    gridSize:72, averageCenter:true, zoomOnClick:true, maxZoom:17, geometries:GEOMS
  });
  cluster.on('click', function(evt){
    if(evt.geometry && evt.geometry.properties){
      var q = evt.geometry.properties;
      infoEl.innerHTML = '<div class="t">' + q.name + '</div>'
        + '<div class="r">省/市：<span>' + q.prov + ' · ' + q.city + '</span><br>'
        + '营业时长：<span>' + (q.hours == null ? '全天营业/未标注' : q.hours + ' 小时') + '</span></div>';
      infoEl.style.display = 'block';
      try{
        var pt = map.projectToContainer(evt.geometry.position);
        var w = document.getElementById('map').clientWidth;
        infoEl.style.left = Math.min(pt.x + 14, Math.max(w - 290, 8)) + 'px';
        infoEl.style.top  = Math.max(pt.y - 70, 8) + 'px';
      }catch(e){ infoEl.style.left = '14px'; infoEl.style.top = '14px'; }
    }
  });
  window.__mapReady = true;
  applyProvince(selEl ? selEl.value : '');
}
function bootMap(){
  var box = document.getElementById('map');
  if(!box) return;
  if(typeof TMap === 'undefined'){
    box.innerHTML = '<div class="mapmsg"><div>地图底图未加载</div>'
      + '<div style="font-size:12px">需在可访问腾讯位置服务的预览环境中打开；'
      + '省份筛选、右侧明细与全部图表不受影响。</div></div>';
    return;
  }
  try{ initMap(); }
  catch(e){
    window.__chartErr.push('地图：' + e.message);
    box.innerHTML = '<div class="mapmsg"><div>地图初始化失败</div><div style="font-size:12px">' + e.message + '</div></div>';
  }
}

/* ---------- 事件 ---------- */
if(selEl) selEl.addEventListener('change', function(){ applyProvince(selEl.value); });
var resetBtn = document.getElementById('resetBtn');
if(resetBtn) resetBtn.addEventListener('click', function(){
  if(selEl) selEl.value = ''; applyProvince('');
});
window.addEventListener('load', function(){
  bootMap();
  setTimeout(function(){
    if(!window.__mapReady && typeof TMap !== 'undefined'){
      var box = document.getElementById('map');
      if(box && !box.querySelector('.mapmsg')){
        box.innerHTML = '<div class="mapmsg"><div>地图加载超时</div>'
          + '<div style="font-size:12px">请确认当前预览环境可访问腾讯位置服务；统计图表不受影响。</div></div>';
      }
    }
    if(window.__chartErr.length){
      showAlert('<b>部分模块渲染异常：</b>' + window.__chartErr.join('；'));
    }
  }, 9000);
});
window.addEventListener('resize', function(){
  CHARTS.forEach(function(c){ try{ c.resize(); }catch(e){} });
});
</script>
</body>
</html>
'''

html = HTML.replace('__ECHARTS__', echarts_js).replace('__DATA__', data_js)
out = os.path.join(BASE, '星巴克门店数据看板.html')
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print('已生成:', out)
print('文件大小: %.2f MB' % (os.path.getsize(out) / 1024 / 1024))
print('点位数:', len(points), '| 省级:', len(provs), '| 城市:', len(cities))
print('待加密增长区:', derived['growthN'], '个省份,', derived['growthStores'], '家门店')
print('直辖市:', derived['muniN'], '家 (', derived['muniShare'], '% )')
print('商场系:', derived['mall'], '家 (', derived['mallShare'], '% ) | 枢纽类:', derived['hub'], '家')
