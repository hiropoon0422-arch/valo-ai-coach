import streamlit as st
import json
import re
import requests
import time
from PIL import Image
from google import genai
import plotly.graph_objects as go

# ==========================================
# 1. 初期設定 & サイバー・ネオンCSS
# ==========================================
st.set_page_config(page_title="VALO AI Coach Pro", layout="wide", initial_sidebar_state="expanded")

# カスタムCSSでサイバー・ネオン感を演出
st.markdown("""
    <style>
    /* 全体の背景をより暗く */
    .stApp {
        background-color: #0d1117;
    }
    /* 見出しにシアン色のネオングロウ */
    h1, h2, h3 {
        color: #0ff !important;
        text-shadow: 0 0 5px #0ff, 0 0 10px #0ff;
        font-family: 'Arial Black', sans-serif;
    }
    /* ボタンをサイバー風に */
    .stButton>button {
        background-color: transparent !important;
        color: #0f0 !important;
        border: 2px solid #0f0 !important;
        box-shadow: 0 0 8px #0f0, inset 0 0 8px #0f0 !important;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #0f0 !important;
        color: #000 !important;
        box-shadow: 0 0 15px #0f0, inset 0 0 15px #0f0 !important;
    }
    /* ステータスメッセージの発光 */
    .stAlert {
        background-color: rgba(0, 255, 255, 0.1) !important;
        border-left: 5px solid #0ff !important;
        color: #e6edf3 !important;
    }
    </style>
""", unsafe_allow_html=True)

# APIキーを安全に取得
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
HDEV_API_KEY = st.secrets["HDEV_API_KEY"]
MODEL_ID = "gemini-2.5-pro" 

client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. ユーティリティ関数
# ==========================================

def fetch_last_match_data(name, tag):
    """APIから最新の試合データを取得"""
    url = f"https://api.henrikdev.xyz/valorant/v3/matches/ap/{name}/{tag}?size=1"
    headers = {"Authorization": HDEV_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data["data"][0] if data.get("data") else None
    except Exception as e:
        st.sidebar.error(f"API通信エラー: {e}")
        return None
    return None

def extract_json_from_text(text):
    """AIの回答からJSONを抽出"""
    if not text:
        return None
    try:
        match_block = re.search(r'```json\s*([\[\{].*?[\]\}])\s*```', text, re.DOTALL)
        if match_block:
            return json.loads(match_block.group(1))
        match_raw = re.search(r'[\[\{].*[\]\}]', text, re.DOTALL)
        if match_raw:
            return json.loads(match_raw.group(0))
    except (json.JSONDecodeError, TypeError):
        return None
    return None

def safe_generate_content(contents_list):
    """混雑時に自動で5分待機してリトライする"""
    wait_time = 300 
    placeholder = st.empty() 
    
    while True:
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=contents_list
            )
            placeholder.empty() 
            return response.text
        except Exception as e:
            err_msg = str(e)
            if any(x in err_msg for x in ["429", "quota", "ResourceExhausted"]):
                placeholder.empty() 
                with placeholder.container():
                    st.warning(f"現在AIモデルが混雑しています。リフレッシュするまで5分待機します... ({time.strftime('%H:%M:%S')})")
                    progress_bar = st.progress(0)
                    for i in range(wait_time):
                        time.sleep(1)
                        progress_bar.progress((i + 1) / wait_time)
                    st.info("再試行を開始します...")
                continue
            else:
                st.error(f"致命的なエラーが発生しました: {e}")
                return None

# ==========================================
# 3. グラフ描画関数
# ==========================================

def draw_radar_chart(radar_data):
    """レーダーチャートの描画"""
    categories = ['撃ち合い(ACS)', '精密さ(HS%)', '起点作成(FB)', 'サポート(Assist)', '生存力(Death)']
    values = [
        radar_data.get("combat", 5),
        radar_data.get("precision", 5),
        radar_data.get("entry", 5),
        radar_data.get("support", 5),
        radar_data.get("survival", 5)
    ]
    # 円を閉じるために最初の値を追加
    values.append(values[0])
    categories.append(categories[0])

    fig = go.Figure(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        fillcolor='rgba(0, 255, 255, 0.2)',
        line=dict(color='#0ff', width=2),
        marker=dict(color='#0ff', size=6)
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 10], color='rgba(255,255,255,0.5)', gridcolor='rgba(255,255,255,0.2)'),
            angularaxis=dict(color='white', gridcolor='rgba(255,255,255,0.2)')
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=40, t=20, b=20),
        height=300
    )
    return fig

def draw_comparison_bar(comp_data):
    """目標数値との比較棒グラフ描画"""
    metrics = []
    actuals = []
    targets = []
    
    for key, data in comp_data.items():
        metrics.append(key.upper())
        actuals.append(data.get("actual", 0))
        targets.append(data.get("target", 0))

    fig = go.Figure(data=[
        go.Bar(name='あなたの数値', x=metrics, y=actuals, marker_color='#0ff'),
        go.Bar(name='適正ランク目標', x=metrics, y=targets, marker_color='rgba(255, 255, 255, 0.3)')
    ])
    fig.update_layout(
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        margin=dict(l=20, r=20, t=20, b=20),
        height=300,
        yaxis=dict(gridcolor='rgba(255,255,255,0.1)')
    )
    return fig

# ==========================================
# 4. メインUI
# ==========================================

st.title("⚡ VALO AI Coach Pro")

with st.sidebar:
    st.header("👤 ID SYSTEM")
    p_name = st.text_input("Name", placeholder="Sova")
    p_tag = st.text_input("Tag", placeholder="JPN")
    st.markdown("---")
    st.write("/// SECURE CONNECTION ESTABLISHED")

col1, col2 = st.columns(2)
with col1:
    st.subheader("1. DETAIL DATA")
    file_detail = st.file_uploader("Upload Detail [IMAGE]", type=['png', 'jpg', 'jpeg'], key="det")
with col2:
    st.subheader("2. SCORE DATA")
    file_score = st.file_uploader("Upload Score [IMAGE]", type=['png', 'jpg', 'jpeg'], key="sco")

if st.button("🚀 INITIATE ANALYSIS", type="primary"):
    if not (p_name and p_tag and file_detail and file_score):
        st.error("SYSTEM ERROR: 名前、タグ、および2枚の画像データが必要です。")
    else:
        with st.status("🔗 サーバーと同期中...", expanded=True) as status:
            # 1. APIロード
            st.write("📡 公式APIからメタデータを取得中...")
            match_json = fetch_last_match_data(p_name, p_tag)
            
            has_api_data = False
            has_timeline = False
            
            if match_json:
                has_api_data = True
                metadata = match_json.get('metadata') or {}
                game_mode = metadata.get('mode', '不明')
                map_name = metadata.get('map', '不明')
                st.info(f"✅ マッチ確認: {game_mode} / Map: {map_name}")
                
                rounds_data = match_json.get('rounds') or []
                kills_data = match_json.get('kills') or []
                has_timeline = bool(rounds_data and kills_data)
            else:
                st.warning("⚠️ APIデータ未検出。画像によるビジュアル解析モードへ移行します。")

            # 2. 統合画像解析（1回の通信で2枚を同時処理）
            st.write("👁️ マルチモーダル画像解析を実行中...")
            img_det_pil = Image.open(file_detail)
            img_sco_pil = Image.open(file_score)
            
            # AIにグラフ描画用のJSON構造を強制するプロンプト
            extraction_prompt = """
            あなたは世界最高峰のVALORANTデータアナリストです。
            提供された2枚の画像（1枚目: 詳細画面、2枚目: スコアボード）を同時に確認し、以下の構造を持つ1つのJSONを出力してください。
            Markdownの ```json ... ``` で囲み、それ以外のテキストは一切出力しないでください。

            {
              "radar_10pt": {
                "combat": 1から10の数値 (ACSに基づく撃ち合いの強さ),
                "precision": 1から10の数値 (HS%に基づく精密さ),
                "entry": 1から10の数値 (ファーストブラッドに基づく起点作成力),
                "support": 1から10の数値 (アシスト数に基づくサポート力),
                "survival": 1から10の数値 (デス数の少なさに基づく生存力)
              },
              "comparison": {
                "ACS": {"actual": 実際のACS数値, "target": このエージェント/ロールの目標ACS},
                "HS%": {"actual": 実際のHSパーセンテージ, "target": 25などの目標値}
              },
              "raw_stats_summary": "画像から読み取れた特筆すべきスタッツの特徴を簡潔なテキストで"
            }
            """
            
            res_vision = safe_generate_content([extraction_prompt, img_det_pil, img_sco_pil])
            extracted_data = extract_json_from_text(res_vision)

            if not extracted_data:
                status.update(label="解析エラー", state="error", expanded=True)
                st.error("❌ 画像からのデータ抽出構造が破損しています。再試行してください。")
            else:
                st.write("🧠 最終戦略レポートを構築中...")
                
                # 3. 最終コーチングプロンプト
                final_prompt = f"""
                あなたは冷徹かつ的確なプロのVALORANTコーチです。
                以下のデータを元に、次の試合に活きる具体的なアドバイスを作成してください。
                ※プレイヤーの名前は出さず「あなた」と呼ぶこと。
                
                【データ】
                API取得タイムライン有無: {has_timeline}
                画像解析データ: {json.dumps(extracted_data, ensure_ascii=False)}
                
                【出力要件】
                1. 抽出データに基づき、プレイスタイルの「明確な強み」を1つ称賛する。
                2. 数値が目標（target）に届いていない、またはレーダーチャートで低かった部分を「致命的な弱点」として指摘し、その理由を推測する。
                3. 明日の試合から1秒で意識できる具体的な改善アクションを提示する。
                """
                
                advice = safe_generate_content([final_prompt])
                
                if advice:
                    status.update(label="解析完了", state="complete", expanded=False)
                    st.divider()
                    
                    # グラフの描画（2カラムでサイバーなUI）
                    st.markdown("### 📊 STATS VISUALIZATION")
                    g_col1, g_col2 = st.columns(2)
                    
                    with g_col1:
                        st.markdown("<div style='text-align: center; color: #0ff;'>PLAYSTYLE RADAR</div>", unsafe_allow_html=True)
                        radar_data = extracted_data.get("radar_10pt", {})
                        if radar_data:
                            st.plotly_chart(draw_radar_chart(radar_data), use_container_width=True)
                            
                    with g_col2:
                        st.markdown("<div style='text-align: center; color: #0ff;'>TARGET COMPARISON</div>", unsafe_allow_html=True)
                        comp_data = extracted_data.get("comparison", {})
                        if comp_data:
                            st.plotly_chart(draw_comparison_bar(comp_data), use_container_width=True)
                    
                    st.divider()
                    st.markdown("### 📋 TACTICAL ADVICE")
                    st.markdown(advice)
                else:
                    status.update(label="生成失敗", state="error", expanded=True)
                    st.error("AIからのアドバイス生成に失敗しました。")