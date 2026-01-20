import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import pandas as pd
import urllib3
import json
from datetime import datetime
import pytz

# --- 網頁設定 ---
st.set_page_config(page_title="台灣電力即時戰情室", layout="wide", page_icon="⚡")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 1. 核心數據與設定 (維持原本 V9.1 邏輯) ---
location_dict = {
    "核一": [25.289, 121.589], "核二": [25.201, 121.666], "核三": [21.958, 120.752],
    "台中": [24.213, 120.483], "麥寮": [23.793, 120.199], "和平": [24.307, 121.760],
    "林口": [25.122, 121.298], "大林": [22.535, 120.336], "興達": [22.856, 120.198],
    "大潭": [25.027, 121.047], "通霄": [24.491, 120.675], "協和": [25.155, 121.745],
    "南部": [22.607, 120.294], "國光": [25.042, 121.341], "新桃": [24.814, 121.197],
    "海湖": [25.116, 121.278], "長生": [25.116, 121.278], "星元": [24.079, 120.412], 
    "嘉惠": [23.533, 120.475], "森霸": [23.083, 120.366], "豐德": [23.083, 120.366], 
    "明潭": [23.839, 120.890], "大觀": [23.837, 120.898],
    "德基": [24.256, 121.161], "青山": [24.223, 121.139], "谷關": [24.204, 121.082], 
    "天輪": [24.185, 121.026], "馬鞍": [24.175, 120.941], "萬大": [23.977, 121.127], 
    "卓蘭": [24.318, 120.835], "碧海": [24.293, 121.613], "立霧": [24.166, 121.637], 
    "翡翠": [24.903, 121.564], "石門": [24.813, 121.246], "曾文": [23.250, 120.528], 
    "烏山頭": [23.193, 120.460], "粗坑": [24.845, 121.189], "桂山": [24.916, 121.558],
    "觀園": [25.039, 121.060], "觀園風力": [25.039, 121.060],
    "大鵬": [24.606, 120.735], "大鵬風力": [24.606, 120.735],
    "石門風力": [25.295, 121.565], "大潭風力": [25.030, 121.045], "蘆竹風力": [25.107, 121.272],
    "大園風力": [25.077, 121.202], "香山風力": [24.757, 120.909],
    "台中風力": [24.256, 120.505], "台中港": [24.256, 120.505], "彰工風力": [24.128, 120.422],
    "王功風力": [23.971, 120.334], "彰濱風力": [24.062, 120.395], "永安風力": [22.822, 120.218],
    "恆春風力": [21.954, 120.743], "中屯": [23.613, 119.605], "湖西": [23.582, 119.671],
    "四湖風力": [23.635, 120.225], "雲麥風力": [23.766, 120.231],
    "GENERIC_WIND": [24.05, 120.30],
    "彰濱光": [24.062, 120.395], "彰濱太陽": [24.062, 120.395], "南鹽光": [23.189, 120.119], 
    "台南鹽田": [23.189, 120.119], "七美": [23.208, 119.428], "望安": [23.369, 119.502],
    "高訓光": [22.605, 120.310], "豐德光": [23.083, 120.366], "大潭光": [25.027, 121.047], 
    "台中光": [24.213, 120.483], "興達光": [22.856, 120.198], "林口光": [25.122, 121.298],
    "GENERIC_SOLAR": [23.15, 120.10],
    "金門": [24.426, 118.396], "塔山": [24.426, 118.396], "珠山": [26.155, 119.927], 
    "馬祖": [26.155, 119.927], "蘭嶼": [22.036, 121.556], "綠島": [22.663, 121.493]
}

def get_location_and_fix(name, p_type):
    name_clean = name.replace("(", "").replace(")", "").replace(" ", "")
    for key, coords in location_dict.items():
        if key in name_clean: return coords, key
    if "風" in str(p_type) or "Wind" in str(p_type): return location_dict["GENERIC_WIND"], "其他風力(彰化外海示意)"
    if "光" in str(p_type) or "太陽" in str(p_type) or "Solar" in str(p_type): return location_dict["GENERIC_SOLAR"], "其他光電(南部示意)"
    return None, name

def get_style(row):
    ft = str(row['type']); name = str(row['name'])
    if "抽蓄" in ft or "明潭" in name or "大觀" in name: return "#9932CC", "抽蓄"
    if "核能" in ft: return "yellow", "核能"
    if "風力" in ft: return "#00FF00", "風力"
    if "太陽" in ft or "光電" in ft: return "#FFA500", "太陽能"
    if "水力" in ft: return "#00BFFF", "水力"
    if "燃煤" in ft or "煤" in ft: return "#AAAAAA", "燃煤"
    if "燃氣" in ft or "氣" in ft: return "#FF4500", "燃氣"
    if "燃油" in ft or "柴油" in ft: return "#A0522D", "燃油"
    return "#8B0000", "其他"

# --- 2. 抓取資料 (UTF-8-SIG 修正版) ---
@st.cache_data(ttl=60)
def fetch_data():
    try:
        url = "https://service.taipower.com.tw/data/opendata/apply/file/d006001/001.json"
        response = requests.get(url, verify=False)
        try:
            data = json.loads(response.content.decode('utf-8-sig'))
        except:
            data = json.loads(response.content.decode('utf-8'))
            
        raw_list = data['aaData'] if isinstance(data, dict) and 'aaData' in data else data
        df = pd.DataFrame(raw_list)
        target_cols = {'機組名稱': 'name', '機組類型': 'type', '淨發電量(MW)': 'gen'}
        rename_dict = {}
        for col in df.columns:
            if col in target_cols: rename_dict[col] = target_cols[col]
            elif "名稱" in col: rename_dict[col] = 'name'
            elif "類型" in col: rename_dict[col] = 'type'
            elif "淨發電量" in col and "比" not in col: rename_dict[col] = 'gen'
        df.rename(columns=rename_dict, inplace=True)
        df['gen'] = pd.to_numeric(df['gen'], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"資料讀取錯誤: {e}")
        return pd.DataFrame()

# --- 3. 主程式介面 ---
st.title("⚡ 台灣電力即時戰情室 (HUD版)")
tw_time = datetime.now(pytz.timezone('Asia/Taipei')).strftime("%Y-%m-%d %H:%M:%S")

col1, col2 = st.columns([3, 1])
with col1:
    st.caption(f"最後更新時間: {tw_time} (數據每60秒自動更新)")
with col2:
    if st.button('🔄 手動更新'):
        st.rerun()

df = fetch_data()

if not df.empty:
    stats = {"核能":0, "燃氣":0, "燃煤":0, "燃油":0, "抽蓄":0, "水力":0, "風力":0, "太陽能":0}
    plant_groups = {}
    total_gen = 0
    
    for index, row in df.iterrows():
        gen = max(0, row['gen'])
        if gen > 0: total_gen += gen
        
        color, category = get_style(row)
        if category in stats: 
            if gen > 0: stats[category] += gen
        else:
            if "其他" not in stats: stats["其他"] = 0
            if gen > 0: stats["其他"] += gen
            
        coords, plant_key = get_location_and_fix(str(row['name']), row['type'])
        if coords:
            if plant_key not in plant_groups:
                plant_groups[plant_key] = {'coords': coords, 'type': category, 'color': color, 'total_gen': 0, 'details': []}
            plant_groups[plant_key]['total_gen'] += row['gen']
            plant_groups[plant_key]['details'].append(f"{row['name']}: {row['gen']} MW")

    # --- 地圖繪製 ---
    m = folium.Map(location=[23.6, 121.0], zoom_start=8, tiles='CartoDB dark_matter')

    # 繪製圓點
    for name, data in plant_groups.items():
        gen_mw = data['total_gen']
        radius = (abs(gen_mw) ** 0.5) * 0.8
        if radius < 3: radius = 3
        mw_text = f"{gen_mw:.1f} MW"
        if gen_mw < 0: mw_text = f"<span style='color:red'>{gen_mw:.1f} (抽水/負載)</span>"
        
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
            location=data['coords'], radius=radius, popup=folium.Popup(popup_html, max_width=250),
            color=data['color'], fill=True, fill_opacity=0.8, weight=1
        ).add_to(m)

    # ---------------------------------------------------------
    # 🌟 特色1: 懸浮置頂數據列 (HUD Top Bar) - 白色字體
    # ---------------------------------------------------------
    # 準備數據
    fire_mw = stats['燃氣'] + stats['燃煤'] + stats['燃油']
    green_mw = stats['風力'] + stats['太陽能']
    
    metrics_html = f'''
    <div style="
        position: fixed; 
        top: 50px; 
        left: 25%; 
        transform: translateX(-50%);
        z-index: 9999; 
        background-color: rgba(20, 20, 20, 0.7); 
        padding: 10px 20px; 
        border-radius: 50px; 
        border: 1px solid #444;
        display: flex;
        gap: 25px;
        color: white;
        font-family: 'Arial', sans-serif;
        font-size: 14px;
        backdrop-filter: blur(5px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        white-space: nowrap;
    ">
        <div style="display:flex; flex-direction:column; align-items:center;">
            <span style="font-size:10px; color:#aaa;">總發電量</span>
            <span style="font-weight:bold; font-size:16px;">{total_gen:,.0f} <span style="font-size:10px">MW</span></span>
        </div>
        <div style="width:1px; background:#555;"></div>
        <div style="display:flex; flex-direction:column; align-items:center;">
            <span style="font-size:10px; color:#FF4500;">火力合計</span>
            <span style="font-weight:bold;">{fire_mw:,.0f}</span>
        </div>
        <div style="display:flex; flex-direction:column; align-items:center;">
            <span style="font-size:10px; color:yellow;">核能</span>
            <span style="font-weight:bold;">{stats['核能']:,.0f}</span>
        </div>
        <div style="display:flex; flex-direction:column; align-items:center;">
            <span style="font-size:10px; color:#00FF00;">風光綠能</span>
            <span style="font-weight:bold;">{green_mw:,.0f}</span>
        </div>
        <div style="display:flex; flex-direction:column; align-items:center;">
            <span style="font-size:10px; color:#9932CC;">抽蓄儲能</span>
            <span style="font-weight:bold;">{stats['抽蓄']:,.0f}</span>
        </div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(metrics_html))

    # ---------------------------------------------------------
    # 🌟 特色2: 可拖曳圖例 (Draggable Legend)
    # ---------------------------------------------------------
    pcts = {}
    if total_gen > 0:
        for k, v in stats.items(): pcts[k] = (v / total_gen) * 100
    
    color_map = {
        "核能": "yellow", "燃氣": "#FF4500", "燃煤": "#AAAAAA", "燃油": "#A0522D", 
        "抽蓄": "#9932CC", "水力": "#00BFFF", "風力": "#00FF00", "太陽能": "#FFA500", "其他": "#333333"
    }
    order_keys = ["核能", "燃煤", "燃氣", "燃油", "抽蓄", "水力", "風力", "太陽能"]
    
    stops = []; acc = 0; legend_rows = ""
    for key in order_keys:
        if key in pcts:
            val = pcts[key]
            c = color_map[key]
            stops.append(f"{c} {acc:.1f}% {acc + val:.1f}%")
            acc += val
            legend_rows += f'<div style="display:flex; justify-content:space-between; color:{c};"><span>■ {key}</span> <span>{val:.1f}%</span></div>'
            
    gradient_str = ", ".join(stops)
    
    # 注入 Javascript 來實現拖曳
    legend_html = f'''
     <div id="draggable-legend" style="
        position: fixed; 
        bottom: 30px; 
        left: 30px; 
        width: 260px; 
        background-color: rgba(30, 30, 30, 0.9); 
        color: white; 
        z-index: 9999; 
        padding: 15px; 
        border-radius: 12px; 
        border: 1px solid #555; 
        font-family: Arial;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        cursor: move; /* 鼠標變成移動十字 */
        user-select: none; /* 防止拖曳時選取文字 */
     ">
         <div style="font-size:16px; font-weight:bold; margin-bottom:5px; border-bottom:1px solid #555;">
            ⚡ 電力戰情 
            <span style="font-size:10px; font-weight:normal; color:#aaa; float:right;">(可拖曳)</span>
         </div>
         <div style="display: flex; align-items: flex-start; margin-top:10px;">
             <div style="width: 80px; height: 80px; border-radius: 50%; margin-right: 15px; flex-shrink: 0; background: conic-gradient({gradient_str}); border: 2px solid #fff;"></div>
             <div style="font-size:12px; line-height: 1.5; width: 100%;">{legend_rows}</div>
         </div>
     </div>

     <script>
        // 簡單的拖曳腳本
        (function() {{
            var elmnt = document.getElementById("draggable-legend");
            var pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
            
            elmnt.onmousedown = dragMouseDown;

            function dragMouseDown(e) {{
                e = e || window.event;
                e.preventDefault();
                // 取得滑鼠初始位置
                pos3 = e.clientX;
                pos4 = e.clientY;
                document.onmouseup = closeDragElement;
                document.onmousemove = elementDrag;
            }}

            function elementDrag(e) {{
                e = e || window.event;
                e.preventDefault();
                // 計算位移
                pos1 = pos3 - e.clientX;
                pos2 = pos4 - e.clientY;
                pos3 = e.clientX;
                pos4 = e.clientY;
                // 設定新位置
                elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
                elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
                // 清除 bottom 定位以免衝突
                elmnt.style.bottom = "auto";
            }}

            function closeDragElement() {{
                document.onmouseup = null;
                document.onmousemove = null;
            }}
        }})();
     </script>
     '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # 顯示地圖
    st_folium(m, width="100%", height=750) # 高度增加讓地圖更滿版

else:
    st.error("目前無法取得台電資料，請稍後重試。")




