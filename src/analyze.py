# -*- coding: utf-8 -*-
"""星巴克门店数据 - 清洗与多维分析 (v2: 增加省份/城市列完整性校验)"""
import pandas as pd
import numpy as np
import json, os, re

# 项目根目录（src/ 的上一级），所有路径由它推导，clone 后可直接运行
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data', '星巴克门店.xlsx')
OUT = os.path.join(ROOT, 'outputs', 'starbucks')
os.makedirs(OUT, exist_ok=True)

raw = pd.read_excel(SRC)
n_raw = len(raw)
df = raw.copy()

# --- 1. 经纬度清洗 ---
df['经度_num'] = pd.to_numeric(df['经度'], errors='coerce')
df['纬度_num'] = pd.to_numeric(df['纬度'], errors='coerce')
lon, lat = df['经度_num'], df['纬度_num']
valid_geo = lon.between(73, 136) & lat.between(3, 54)
swapped = (~valid_geo) & (lon.between(3, 54)) & (lat.between(73, 136))
df['geo_ok'] = valid_geo
df.loc[swapped, ['经度_num', '纬度_num']] = df.loc[swapped, ['纬度_num', '经度_num']].values
df.loc[swapped, 'geo_ok'] = True

# --- 2. 省份 / 城市 列完整性校验(存在时间值、坐标值串入) ---
PROV_RE = re.compile(r'^[\u4e00-\u9fa5]{2,}(省|市|自治区)$')
CITY_RE = re.compile(r'^[\u4e00-\u9fa5]{2,}(市|地区|自治州|盟|区)$')
# 用纯 Python 逐个匹配，不用 Series.str.match()：
# pandas >= 2.1 在 pyarrow 字符串后端下对 `\uXXXX` 转义会抛 ArrowInvalid，
# 逐值 re.match 与后端无关，结果一致（re.match 同样是从字符串开头匹配）。
df['prov_ok'] = [bool(PROV_RE.match(str(x))) for x in df['省份']]
df['city_ok'] = [bool(CITY_RE.match(str(x))) for x in df['城市']]
df['region_ok'] = df['prov_ok'] & df['city_ok']

n_bad_prov = int((~df['prov_ok']).sum())
n_bad_city = int((~df['city_ok']).sum())
n_bad_geo = int((~df['geo_ok']).sum())
print(f'原始 {n_raw} 行')
print(f'  坐标异常行: {n_bad_geo}')
print(f'  省份列异常行: {n_bad_prov}')
print(f'  城市列异常行: {n_bad_city}')
print(f'  省份异常值: {sorted(set(df.loc[~df["prov_ok"],"省份"].astype(str)))}')

# 有效区域样本
reg = df[df['region_ok']]
prov = reg['省份'].value_counts()
city = reg['城市'].value_counts()
print(f'\n有效省级行政区: {reg["省份"].nunique()} 个 | 有效城市: {reg["城市"].nunique()} 个')
print(f'Top5省份占比: {prov.head(5).sum()/n_raw*100:.1f}%  Top10: {prov.head(10).sum()/n_raw*100:.1f}%')
print(f'Top5城市占比: {city.head(5).sum()/n_raw*100:.1f}%  Top10: {city.head(10).sum()/n_raw*100:.1f}%')

# --- 3. 时间清洗 ---
def to_min(t):
    m = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', str(t).strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else np.nan

df['开店分钟'] = df['开始营业时间'].apply(to_min)
df['闭店分钟'] = df['停止营业时间'].apply(to_min)
df['营业时长_h'] = (df['闭店分钟'] - df['开店分钟']) / 60.0
df.loc[df['营业时长_h'] < 0, '营业时长_h'] += 24
df.loc[df['营业时长_h'] > 24, '营业时长_h'] = np.nan
same = (df['开店分钟'] == df['闭店分钟']) & df['开店分钟'].notna()
df['疑似全天'] = same
df.loc[same, '营业时长_h'] = np.nan
print(f'\n开店=闭店(疑似全天/未标注): {int(same.sum())} 家')
print('营业时长(h):'); print(df['营业时长_h'].describe().round(2).to_string())
raw_avg = df['营业时长_h'].sum() / (df['营业时长_h'].notna().sum() + int(same.sum()))

# --- 4. 场景关键词 ---
kw = {
    '商场/购物中心': r'广场|购物中心|商场|百货|万象|印象城|大悦城|银泰|天街|MALL|茂|万达|来福士|恒隆|太古里|荟聚',
    '写字楼/商务区': r'大厦|中心|国际|金融|科技|科创|产业园|园区|总部|软件园|商务',
    '景区/公园': r'景区|公园|古镇|老街|步行街|乐园|博物|湿地|古城|水乡|度假|动物|植物园|海洋|名胜',
    '机场': r'机场|航站楼|T\d航站|候机',
    '高铁/火车站': r'高铁|火车站|车站|虹桥|南站|北站|东站|西站',
    '社区/住宅': r'小区|花园|家园|苑|新村|公寓',
    '医院/学校': r'医院|大学|学院|学校|校区',
    '交通枢纽/服务区': r'服务区|客运站|汽车站|港口|码头|地铁',
    '涉外/口岸': r'口岸|边检|免税|自贸|保税',
}
scene_df = pd.DataFrame([{
    '场景': k, '门店数': int(df['店铺名称'].str.contains(p, case=False, na=False, regex=True).sum())
} for k, p in kw.items()])
scene_df['占比'] = (scene_df['门店数'] / n_raw * 100).round(2)
scene_df = scene_df.sort_values('门店数', ascending=False)
print('\n场景关键词:'); print(scene_df.to_string(index=False))

# --- 5. 营业时间维度 ---
open_slot = pd.cut(df['开店分钟'].dropna(),
                   bins=[0,360,390,420,450,480,540,600,1440],
                   labels=['≤06:00','06:01-06:30','06:31-07:00','07:01-07:30',
                           '07:31-08:00','08:01-09:00','09:01-10:00','>10:00'])
print('\n开店时间分布:'); print(open_slot.value_counts().sort_index().to_string())

# 逐小时营业门店数
hours_profile = []
for hmin in range(24):
    t = hmin * 60; cnt = 0
    for o, c in zip(df['开店分钟'], df['闭店分钟']):
        if pd.isna(o) or pd.isna(c): continue
        if o == c: cnt += 1                      # 疑似全天
        elif c > o: cnt += (o <= t < c)
        else: cnt += (t >= o or t < c)           # 跨零点
    hours_profile.append({'name': f'{hmin:02d}:00', 'value': cnt})

# 覆盖城市数
prov_city = reg.groupby('省份')['城市'].nunique().sort_values(ascending=False)
print('\n覆盖城市数 Top10:'); print(prov_city.head(10).to_string())

# --- 6. 导出 ---
clean = df[['店铺名称','城市','省份','详细地址','经度_num','纬度_num','geo_ok',
            'prov_ok','city_ok','开店分钟','闭店分钟','营业时长_h','疑似全天']].rename(
    columns={'经度_num':'经度','纬度_num':'纬度'})
clean.to_csv(os.path.join(OUT,'starbucks_clean.csv'), index=False, encoding='utf-8-sig')
clean[clean['geo_ok']].to_csv(os.path.join(OUT,'starbucks_points.csv'), index=False, encoding='utf-8-sig')

h = df['营业时长_h'].dropna()
bins = np.arange(0, 17, 1); hist, edges = np.histogram(h, bins=bins)

summary = {
    'total': int(n_raw),
    'geo_valid': int(df['geo_ok'].sum()),
    'geo_bad': n_bad_geo,
    'prov_bad': n_bad_prov,
    'city_bad': n_bad_city,
    'province_n': int(reg['省份'].nunique()),
    'city_n': int(reg['城市'].nunique()),
    'province_geo_n': int(df[df['geo_ok']]['省份'].nunique()),
    'avg_hours': round(float(df['营业时长_h'].mean()), 2),
    'median_hours': round(float(df['营业时长_h'].median()), 2),
    'avg_hours_raw': round(float(raw_avg), 2),
    'same_time_n': int(same.sum()),
    'overnight': int((df['营业时长_h'] >= 18).sum()),
    'top5_prov_share': round(float(prov.head(5).sum()/n_raw*100), 1),
    'top10_prov_share': round(float(prov.head(10).sum()/n_raw*100), 1),
    'top5_city_share': round(float(city.head(5).sum()/n_raw*100), 1),
    'top10_city_share': round(float(city.head(10).sum()/n_raw*100), 1),
    'province_top': [{'name':k,'value':int(v)} for k,v in prov.head(15).items()],
    'province_all': [{'name':k,'value':int(v)} for k,v in prov.items()],
    'city_top': [{'name':k,'value':int(v)} for k,v in city.head(20).items()],
    'city_all': [{'name':k,'value':int(v)} for k,v in city.items()],
    'scene': scene_df.to_dict('records'),
    'open_slot': [{'name':str(k),'value':int(v)} for k,v in open_slot.value_counts().sort_index().items()],
    'hours_hist': [{'name':f'{int(edges[i])}-{int(edges[i+1])}h','value':int(hist[i])} for i in range(len(hist))],
    'hours_profile': hours_profile,
    'province_coverage': [{'name':k,'value':int(v)} for k,v in prov_city.head(12).items()],
    'hours_by_province': (df[df['region_ok']].groupby('省份')['营业时长_h'].mean().round(2).sort_values(ascending=False).head(15)
                          .reset_index().rename(columns={'省份':'name','营业时长_h':'value'}).to_dict('records')),
}
json.dump(summary, open(os.path.join(OUT,'summary.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=2)
print('\n=== 核心指标 ===')
print(json.dumps({k:v for k,v in summary.items() if not isinstance(v,(list,))}, ensure_ascii=False, indent=2))
