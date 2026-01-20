# @title 台灣電力即時戰情地圖 V9 (抽蓄獨立 & 風光分家版)
import requests
import pandas as pd
import folium
import urllib3
import json
from datetime import datetime
import pytz

# 關閉 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# 1. 座標字典 (新增苗栗大鵬、桃園觀園)
# ---------------------------------------------------------
location_dict = {
    # === 核能 (Nuclear) ===
    "核一": [25.289, 121.589], "核二": [25.201, 121.666], "核三": [21.958, 120.752],

    # === 燃煤 (Coal) ===
    "台中": [24.213, 120.483], "麥寮": [23.793, 120.199], "和平": [24.307, 121.760],
    "林口": [25.122, 121.298], "大林": [22.535, 120.336], "興達": [22.856, 120.198],

    # === 燃氣 (Gas) ===
    "大潭": [25.027, 121.047], "通霄": [24.491, 120.675], "協和": [25.155, 121.745],
    "南部": [22.607, 120.294], "國光": [25.042, 121.341], "新桃": [24.814, 121.197],
    "海湖": [25.116, 121.278], "長生": [25.116, 121.278],
    "星元": [24.079, 120.412], "嘉惠": [23.533, 120.475],
    "森霸": [23.083, 120.366], "豐德": [23.083, 120.366], 

    # === 抽蓄/儲能 (Pumped Storage) ===
    "明潭": [23.839, 120.890], "大觀": [23.837, 120.898],

    # === 一般水力 (Hydro) ===
    "德基": [24.256, 121.161], "青山": [24.223, 121.139], "谷關": [24.204, 121.082], 
    "天輪": [24.185, 121.026], "馬鞍": [24.175, 120.941], "萬大": [23.977, 121.127], 
    "卓蘭": [24.318, 120.835], "碧海": [24.293, 121.613], "立霧": [24.166, 121.637], 
    "翡翠": [24.903, 121.564], "石門": [24.813, 121.246], "曾文": [23.250, 120.528], 
    "烏山頭": [23.193, 120.460], "粗坑": [24.845, 121.189], "桂山": [24.916, 121.558],

    # === 風力 (Wind) ===
    # 修正：觀園 (桃園觀音/大園)、大鵬 (苗栗後龍)
    "觀園": [25.039, 121.060], "觀園風力": [25.039, 121.060],
    "大鵬": [24.606, 120.735], "大鵬風力": [24.606, 120.735],
    "石門風力": [25.295, 121.565], "大潭風力": [25.030, 121.045], "蘆竹風力": [25.107, 121.272],
    "大園風力": [25.077, 121.202], "香山風力": [24.757, 120.909],
    "台中風力": [24.256, 120.505], "台中港": [24.256, 120.505], "彰工風力": [24.128, 120.422],
    "王功風力": [23.971, 120.334], "彰濱風力": [24.062, 120.395], "永安風力": [22.822, 120.218],
    "恆春風力": [21.954, 120.743], "中屯": [23.613, 119.605], "湖西": [23.582, 119.671],
    "四湖風力": [23.635, 120.225], "雲麥風力": [23.766, 120.231],
    "GENERIC_WIND": [24.05, 120.30], # 彰化外海示意

    # === 太陽能 (Solar) ===
    "彰濱光": [24.062, 120.395], "彰濱太陽": [24.062, 120.395],
    "南鹽光": [23.189, 120.119], "台南鹽田": [23.189, 120.119],
    "七美": [23.208, 119.428], "望安": [23.369, 119.502],
    "高訓光": [22.605, 120.310], "豐德光": [23.083, 120.366],
    "大潭光": [25.027, 121.047], "台中光": [24.213, 120.483], 
    "興達光": [22.856, 120.198], "林口光": [25.122, 121.298],
    "GENERIC_SOLAR": [23.15, 120.10], # 台南示意

    # === 離島 ===
    "金門": [24.426, 118.396], "塔山": [24.426, 118.396],
    "珠山": [26.155, 119.927], "馬祖": [26.155, 119.927],
    "蘭嶼": [22.036, 121.556], "綠島": [22.663, 121.493]
}

def get_location_and_fix(name, p_type):
    name_clean = name.replace("(", "").replace(")", "").replace(" ", "")
    
    # 精確比對
    for key, coords in location_dict.items():
        if key in name_clean:
            return coords, key
            
    # 模糊歸戶
    if "風" in str(p_type) or "Wind" in str(p_type):
        return location_dict["GENERIC_WIND"], "其他風力(彰化外海示意)"
    if "光" in str(p_type) or "太陽" in str(p_type) or "Solar" in str(p_type):
        return location_dict["GENERIC_SOLAR"], "其他光電(南部示意)"
        
    return None, name

# ---------------------------------------------------------
# 2. 定義顏色樣式 (V9: 抽蓄獨立/風光分色)
# ---------------------------------------------------------
def get_style(row):
    ft = str(row['type'])
    name = str(row['name'])
    
    # 優先權邏輯
    # 1. 抽蓄 (儲能)
    if "抽蓄" in ft or "明潭" in name or "大觀" in name:
        return "#9932CC", "抽蓄" # Dark Orchid (紫色)
        
    # 2. 核能
    if "核能" in ft: 
        return "yellow", "核能"
        
    # 3. 再生能源 (分家)
    if "風力" in ft: 
        return "#00FF00", "風力" # Lime Green (綠)
    if "太陽" in ft or "光電" in ft: 
        return "#FFA500", "太陽能" # Orange (橙)
        
    # 4. 水力
    if "水力" in ft: 
        return "#00BFFF", "水力"  # Deep Sky Blue (藍)
        
    # 5. 火力系
    if "燃煤" in ft or "煤" in ft: 
        return "#AAAAAA", "燃煤" # Light Gray (灰)
    if "燃氣" in ft or "氣" in ft or "LNG" in ft: 
        return "#FF4500", "燃氣" # Orange Red (紅)
    if "燃油" in ft or "輕油" in ft or "柴油" in ft:
        return "#A0522D", "燃油" # Sienna (棕)
        
    return "#8B0000", "其他"

# ---------------------------------------------------------
# 3. 主程式
# ---------------------------------------------------------
url = "https://service.taipower.com.tw/data/opendata/apply/file/d006001/001.json"
print(f"正在下載: {url} ...")

try:
    response = requests.get(url, verify=False) 
    response.encoding = 'utf-8'
    data = response.json()
    
    if isinstance(data, dict) and 'aaData' in data: raw_list = data['aaData']
    else: raw_list = data

    df = pd.DataFrame(raw_list)

    # 欄位對應
    target_cols = {'機組名稱': 'name', '機組類型': 'type', '淨發電量(MW)': 'gen'}
    rename_dict = {}
    for col in df.columns:
        if col in target_cols: rename_dict[col] = target_cols[col]
        elif "名稱" in col: rename_dict[col] = 'name'
        elif "類型" in col: rename_dict[col] = 'type'
        elif "淨發電量" in col and "比" not in col: rename_dict[col] = 'gen'
    df.rename(columns=rename_dict, inplace=True)
    df['gen'] = pd.to_numeric(df['gen'], errors='coerce').fillna(0)

    # 統計容器 (細分風/光/抽蓄)
    stats = {"核能":0, "燃氣":0, "燃煤":0, "燃油":0, "抽蓄":0, "水力":0, "風力":0, "太陽能":0}
    plant_groups = {}
    total_gen = 0

    for index, row in df.iterrows():
        gen = max(0, row['gen'])
        
        # 修正：抽蓄在發電時算正值，抽水時是負值
        # 統計圓餅圖時，我們通常看「貢獻度」(正值)，或者看「淨值」
        # 這裡為了戰情圖顯示比例，我們先只加總「正向發電量」到圓餅圖，避免負數吃掉比例
        # 但地圖上的 popup 仍會顯示負數
        if gen > 0:
            total_gen += gen
        
        color, category = get_style(row)
        
        # 統計 (若出現未定義類別，歸類為其他)
        if category in stats: 
            if gen > 0: stats[category] += gen
        else: 
            if "其他" not in stats: stats["其他"] = 0
            if gen > 0: stats["其他"] += gen
        
        coords, plant_key = get_location_and_fix(str(row['name']), row['type'])
        
        if coords:
            if plant_key not in plant_groups:
                plant_groups[plant_key] = {
                    'coords': coords, 'type': category, 'color': color, 
                    'total_gen': 0, 'details': []
                }
            plant_groups[plant_key]['total_gen'] += row['gen']
            plant_groups[plant_key]['details'].append(f"{row['name']}: {row['gen']} MW")

    print(f"資料處理完成。正向總發電量: {total_gen:,.0f} MW")
    
    # ---------------------------------------------------------
    # 4. 繪圖
    # ---------------------------------------------------------
    m = folium.Map(location=[23.6, 121.0], zoom_start=8, tiles='CartoDB dark_matter')

    for name, data in plant_groups.items():
        gen_mw = data['total_gen']
        # 繪圖大小邏輯：負數(抽水)也給它大小，顯示為紫色圈圈
        safe_gen = abs(gen_mw)
        
        radius = (safe_gen ** 0.5) * 0.8
        if radius < 3: radius = 3
        
        mw_text = f"{gen_mw:.1f} MW"
        status_text = ""
        if gen_mw < 0: 
            mw_text = f"<span style='color:red'>{gen_mw:.1f} (抽水/充電中)</span>"
            status_text = " (負載)"
        
        popup_html = f"""
        <div style="font-family: Arial; min-width: 150px;">
            <b style="font-size:14px">{name}</b><br>
            <span style="color:{data['color']}; font-weight:bold;">● {data['type']}</span><br>
            <b>{mw_text}</b>
            <hr style="margin:5px 0">
            <div style="font-size:11px; color:#555">{"<br>".join(data['details'][:8])}</div>
        </div>
        """
        
        folium.CircleMarker(
            location=data['coords'],
            radius=radius,
            popup=folium.Popup(popup_html, max_width=250),
            color=data['color'],
            fill=True, fill_opacity=0.8, weight=1
        ).add_to(m)

    # ---------------------------------------------------------
    # 5. 圓餅圖與圖例 (Legend) - 全面細分版
    # ---------------------------------------------------------
    tw_time = datetime.now(pytz.timezone('Asia/Taipei')).strftime("%Y-%m-%d %H:%M")
    
    pcts = {}
    if total_gen > 0:
        for k, v in stats.items(): pcts[k] = (v / total_gen) * 100
    else:
        for k in stats.keys(): pcts[k] = 0
        
    # 顏色映射
    color_map = {
        "核能": "yellow",
        "燃氣": "#FF4500",
        "燃煤": "#AAAAAA", 
        "燃油": "#A0522D", 
        "抽蓄": "#9932CC", # 紫色
        "水力": "#00BFFF",
        "風力": "#00FF00",
        "太陽能": "#FFA500", # 橙色
        "其他": "#333333"
    }
    
    # 顯示順序 (基載 -> 中載 -> 尖載/再生)
    order_keys = ["核能", "燃煤", "燃氣", "燃油", "抽蓄", "水力", "風力", "太陽能"]
    
    acc = 0
    stops = []
    
    for key in order_keys:
        if key in pcts:
            val = pcts[key]
            c = color_map[key]
            stops.append(f"{c} {acc:.1f}% {acc + val:.1f}%")
            acc += val
        
    gradient_str = ", ".join(stops)
    
    # 圖例 HTML 生成 (動態生成 row)
    legend_rows = ""
    for key in order_keys:
        if key in pcts:
            legend_rows += f'''
             <div style="display:flex; justify-content:space-between; color:{color_map[key]};">
                <span>■ {key}</span> <span>{pcts.get(key,0):.1f}%</span>
             </div>
            '''

    legend_html = f'''
     <div style="position: fixed; bottom: 30px; left: 30px; width: 260px; 
     background-color: rgba(30, 30, 30, 0.9); color: white; z-index:9999; 
     padding: 15px; border-radius: 12px; border: 1px solid #555; font-family: 'Microsoft JhengHei', Arial;
     box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
     
     <div style="font-size:16px; font-weight:bold; margin-bottom:5px; border-bottom:1px solid #555; padding-bottom:5px;">
        ⚡ 台灣電力戰情
        <span style="font-size:11px; float:right; margin-top:4px; color:#aaa;">{tw_time}</span>
     </div>
     
     <div style="display: flex; align-items: flex-start; margin-top:10px;">
         <div style="width: 80px; height: 80px; border-radius: 50%; margin-right: 15px; flex-shrink: 0;
             background: conic-gradient({gradient_str}); border: 2px solid #fff;">
         </div>
         
         <div style="font-size:12px; line-height: 1.5; width: 100%;">
             {legend_rows}
         </div>
     </div>
     
     <div style="margin-top:8px; font-size:11px; color:#ddd; text-align:center; background:#444; border-radius:4px;">
         總發電量: {total_gen:,.0f} MW
     </div>
     </div>
     '''
    m.get_root().html.add_child(folium.Element(legend_html))

    output_file = "taiwan_power_map_v9.html"
    m.save(output_file)
    print(f"✅ V9 最終版地圖生成完畢: {output_file}")

except Exception as e:
    print(f"❌ 錯誤: {e}")