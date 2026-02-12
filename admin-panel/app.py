import streamlit as st
import os
import pandas as pd
import db_utils
import time
import requests
import json
import datetime

# 北京时区 (UTC+8)，全局统一使用
BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8080")

# --- Config & Session State ---
st.set_page_config(page_title="WQT 中台管理系统", layout="wide", page_icon="🏢")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'username' not in st.session_state:
    st.session_state.username = None

# Try fallback to DB for DEV_KEY
DEV_KEY = db_utils.get_system_setting("DEV_KEY", "sj0127wqt")

# --- Caching & Helpers ---

@st.cache_data(ttl=60)
def cached_run_query(query, params=None):
    """Cached wrapper for db_utils.run_query"""
    # Simply call the original function
    return db_utils.run_query(query, params)

def clear_cache():
    st.cache_data.clear()

# --- Authentication Views ---
def login_page():
    st.markdown("<h1 style='text-align: center;'>WQT 统一身份认证</h1>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔑 开发者模式 (Developer)", "👤 用户登录 (User)"])
    
    with tab1:
        with st.form("dev_login"):
            key = st.text_input("开发者密钥", type="password")
            submit = st.form_submit_button("进入上帝模式", use_container_width=True)
            if submit:
                if key == DEV_KEY:
                    # Authenticate with backend as dev user to get token
                    try:
                        # Assuming dev user exists or we use a hardcoded dev token strategy.
                        # For now, let's try to login as a specific dev account if it exists, 
                        # or just fallback to basic auth if backend supports it (it doesn't, needs JWT).
                        # Let's auto-register/login a dev admin account.
                        payload = {"username": "admin_panel", "password": "dev_password_secure"}
                        
                        # Try login
                        res = requests.post(f"{BACKEND_URL}/api/auth/login", json=payload)
                        if res.status_code == 401:
                             # Try register if not exists
                             res = requests.post(f"{BACKEND_URL}/api/auth/register", json=payload)
                        
                        if res.ok:
                            token = res.json().get("token")
                            st.session_state.token = token
                        else:
                            st.warning("后端连接失败或认证失败，部分功能可能受限")
                            st.session_state.token = None

                    except Exception as e:
                        st.error(f"Backend Connection Error: {e}")
                        st.session_state.token = None

                    st.session_state.logged_in = True
                    st.session_state.user_role = "admin"
                    st.session_state.username = "Developer"
                    st.success("身份验证成功！正在跳转...")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("密钥无效")

    with tab2:
        with st.form("user_login"):
            phone = st.text_input("手机号")
            # In a real app, verify password hash. For demo/boss, simple check or mock.
            # Assuming Boss uses a specific account or just checking existence for now as per "login with existing phone".
            # For strictness, we should check password. But user request implies "log in with phone".
            # Let's check if user exists.
            submit_user = st.form_submit_button("登录", use_container_width=True)
            if submit_user and phone:
                df = cached_run_query("SELECT * FROM users WHERE phone = ?", params=(phone,))
                if isinstance(df, pd.DataFrame) and not df.empty:
                    user_row = df.iloc[0]
                    # Check role
                    role = user_row.get('role', 'user')
                    st.session_state.logged_in = True
                    st.session_state.user_role = role
                    st.session_state.username = user_row.get('username') or phone
                    st.success(f"欢迎回归, {st.session_state.username}!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("用户不存在")

# --- Review Logic (Ported from game-review.js) ---
def format_duration(ms):
    if not isinstance(ms, (int, float)) or ms <= 0:
        return ""
    total_sec = round(ms / 1000)
    m = total_sec // 60
    s = total_sec % 60
    return f"{m}分{s}秒"

def format_ts(ts):
    if not ts: return ""
    try:
        dt = datetime.datetime.fromtimestamp(int(ts) / 1000, tz=BEIJING_TZ)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ""

def sum_attributes(attrs):
    if not attrs or not isinstance(attrs, dict):
        return 0
    return sum(float(v or 0) for v in attrs.values())

def parse_payload(payload):
    if not payload:
        return {}
    if isinstance(payload, dict):
        return payload
    try:
        return json.loads(payload)
    except:
        return {}

def build_review_data(session, events):
    # session: dict or row
    # events: list of dicts
    
    parsed_events = []
    for ev in events:
        ev_copy = ev.copy()
        ev_copy['payload'] = parse_payload(ev.get('payload'))
        parsed_events.append(ev_copy)
    
    card_events = [e for e in parsed_events if e.get('type') == 'card_choice']
    skill_events = [e for e in parsed_events if e.get('type') == 'skill_use']
    start_event = next((e for e in parsed_events if e.get('type') == 'game_start'), None)
    finish_event = next((e for e in parsed_events if e.get('type') == 'game_finish'), None)
    
    processed_cards = []
    for idx, ev in enumerate(card_events):
        payload = ev.get('payload', {})
        processed_cards.append({
            "index": idx + 1,
            "cardId": payload.get('cardId'),
            "phase": payload.get('phase', ""),
            "eventText": payload.get('eventText', ""),
            "choice": payload.get('choice', ""),
            "optionText": payload.get('optionText', ""),
            "consequence": payload.get('consequence', ""),
            "timeSpentSec": payload.get('timeSpentSec'),
            "attributeDelta": payload.get('attributeDelta') or payload.get('attributeEffects') or {},
            "attributesBefore": payload.get('attributesBefore', {}),
            "attributesAfter": payload.get('attributesAfter', {}),
            "wasFailure": bool(payload.get('wasFailure')),
            "isCreativeOption": bool(payload.get('isCreativeOption')),
            "ts": ev.get('ts')
        })
        
    processed_skills = []
    for ev in skill_events:
        payload = ev.get('payload', {})
        processed_skills.append({
            "ts": ev.get('ts'),
            "skill": payload.get('skill', ""),
            "cardId": payload.get('cardId'),
            "optionD": payload.get('optionD', ""),
            "rescued": payload.get('rescued', []),
            "attributeChange": payload.get('attributeChange', {}),
            "attributesBefore": payload.get('attributesBefore', {}),
            "attributesAfter": payload.get('attributesAfter', {})
        })
        
    final_score = session.get('final_score')
    if final_score is None:
        if processed_cards:
            final_score = sum_attributes(processed_cards[-1]['attributesAfter'])
        else:
            final_score = 0
            
    # Safe conversion helper
    def to_int_safe(val):
        try:
            if pd.isna(val) or val is None or val == "":
                return None
            return int(float(val))
        except:
            return None

    s_ts = to_int_safe(session.get('started_at') or (start_event['ts'] if start_event else None))
    e_ts = to_int_safe(session.get('ended_at') or (finish_event['ts'] if finish_event else None))
    
    started_at = s_ts
    ended_at = e_ts
    duration_ms = (e_ts - s_ts) if (s_ts is not None and e_ts is not None) else None
    
    players = parse_payload(session.get('players_json'))
    settings = parse_payload(session.get('game_settings_json'))
    
    return {
        "session": {
            "id": session.get('id'),
            "startedAt": started_at,
            "endedAt": ended_at,
            "finalScore": final_score,
            "location": session.get('location'),
            "players": players,
            "mode": session.get('game_mode'),
            "settings": settings
        },
        "cards": processed_cards,
        "skills": processed_skills,
        "durationMs": duration_ms
    }

def build_extract_prompt(data):
    session = data['session']
    cards = data['cards']
    skills = data['skills']
    
    payload = {
        "sessionId": session['id'],
        "location": session['location'],
        "players": session['players'],
        "mode": session['mode'],
        "startedAt": session['startedAt'],
        "endedAt": session['endedAt'],
        "duration": format_duration(data['durationMs']),
        "finalScore": session['finalScore'],
        "cards": [{
            "cardId": c['cardId'],
            "phase": c['phase'],
            "event": c['eventText'],
            "choice": c['choice'],
            "optionText": c['optionText'],
            "consequence": c['consequence'],
            "delta": c['attributeDelta'],
            "timeSpentSec": c['timeSpentSec'],
            "wasFailure": c['wasFailure'],
            "isCreativeOption": c['isCreativeOption']
        } for c in cards],
        "skills": [{
            "skill": s['skill'],
            "cardId": s['cardId'],
            "optionD": s['optionD'],
            "rescued": s['rescued'],
            "attributeChange": s['attributeChange'],
            "scoreChange": sum(s['attributeChange'].values()) if s['attributeChange'] else 0
        } for s in skills]
    }
    
    return "\n".join([
        "你是游戏复盘分析师。分析以下游戏数据，提取有意思的关键点。",
        "请严格按照JSON格式输出，不要包含任何其他文字或解释。",
        "",
        "输出格式：",
        "```json",
        "{",
        '  "keyMoments": [',
        '    {"type": "breakthrough|setback|turning_point|skill_use", "cardId": 数字, "impact": 数字, "description": "描述"}',
        "  ],",
        '  "decisionPatterns": [',
        '    {"pattern": "模式名称", "frequency": 数字, "description": "描述"}',
        "  ],",
        '  "growthHighlights": [',
        '    {"moment": "时刻描述", "description": "详细描述"}',
        "  ],",
        '  "reflectionPoints": [',
        '    {"moment": "反思点", "description": "启示内容"}',
        "  ]",
        "}",
        "```",
        "",
        "分析要点：",
        "- keyMoments: 关键转折点（得分大幅变化、失败、突破、技能使用等）",
        "- decisionPatterns: 决策模式（选择倾向、反应时间、技能使用策略等）",
        "- growthHighlights: 成长亮点（技能使用、创新选择、属性提升等）",
        "- reflectionPoints: 值得反思的点（可改进之处、学习机会等）",
        "- 结合玩家信息（地点、人数等）进行情境化分析。",
        "",
        "游戏数据：",
        "```json",
        json.dumps(payload, ensure_ascii=False, indent=2),
        "```"
    ])

def format_players(p):
    if not p: return "未知"
    s = []
    if p.get('enlightenment'): s.append(f"启蒙期{p['enlightenment']}人")
    if p.get('growth'): s.append(f"成长期{p['growth']}人")
    if p.get('adolescence'): s.append(f"青春期{p['adolescence']}人")
    if p.get('adults'): s.append(f"成年人{p['adults']}人")
    return ", ".join(s) if s else "无详细数据"

def build_story_prompt_part1(data, extract_md):
    session = data['session']
    mode_str = '标准版' if session['mode'] == 'standard' else ('精华版' if session['mode'] == 'essence' else (session['mode'] or '未知'))
    
    meta = " | ".join([
        f"地点: {session['location'] or '未知'}",
        f"玩家: {format_players(session['players'])}",
        f"模式: {mode_str}",
        f"游戏开始: {format_ts(session['startedAt']) or '未知'}",
        f"游戏结束: {format_ts(session['endedAt']) or '未知'}",
        f"总时长: {format_duration(data['durationMs']) or '未知'}",
        f"最终得分: {session['finalScore']}"
    ])
    
    return "\n".join([
        "你是叙事写手。请基于“精炼数据”写这场游戏的复盘故事第一部分。",
        "要求：",
        "- 输出标准 Markdown。",
        "- 标题必须是：# 游戏复盘：回顾",
        "- 篇幅在 600-900 字之间（数据不足可略短，但不要少于 400 字）。",
        "- 叙述顺序尽量按卡牌顺序，穿插关键分数变化与决策原因。",
        "- 开头请简要提及本次游戏的背景信息（地点、玩家构成等）。",
        "- 不要写成纯清单。",
        "",
        f"基础信息：{meta}",
        "",
        "精炼数据：",
        extract_md
    ])

def build_story_prompt_part2(extract_md):
    return "\n".join([
        "你是叙事写手。请基于“精炼数据”输出第二部分：有意思的点与整体启示。",
        "要求：",
        "- 输出标准 Markdown。",
        "- 标题必须是：# 游戏复盘：有意思的点与启示",
        "- 篇幅在 400-700 字之间（数据不足可略短，但不要少于 300 字）。",
        "- 至少包含 3-6 个“有意思的点”、1-2 个整体趋势、1 条可行动的启示。",
        "- 可使用列表，但不要只堆叠要点。",
        "",
        "精炼数据：",
        extract_md
    ])

def build_report_html(markdown, data):
    # Simplified HTML template logic
    title = "小伍的AI成长日记"
    session = data['session']
    meta = " | ".join([
        f"复盘生成时间: {datetime.datetime.now(tz=BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')}",
        f"游戏开始: {format_ts(session['startedAt']) or '未知'}",
        f"游戏结束: {format_ts(session['endedAt']) or '未知'}",
        f"总时长: {format_duration(data['durationMs']) or '未知'}",
        f"最终得分: {session['finalScore']}"
    ])
    
    # Just minimal structure to wrap markdown
    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>{title}</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    body {{ font-family: sans-serif; max-width: 800px; margin: 40px auto; line-height: 1.6; color: #333; }}
    .meta {{ background: #f4f4f4; padding: 10px; margin-bottom: 20px; font-size: 0.9em; color: #666; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="meta">{meta}</div>
  <div id="content"></div>
  <script>
    document.getElementById('content').innerHTML = marked.parse({json.dumps(markdown)});
  </script>
</body>
</html>
"""


# --- Prompt Engineering Workbench ---

def render_node_header(title, status="pending", icon="⚪"):
    colors = {
        "pending": "#e0e0e0",
        "running": "#ffe066",
        "done": "#b7eb8f", 
        "error": "#ffccc7"
    }
    color = colors.get(status, "#e0e0e0")
    st.markdown(f"""
    <div style="
        padding: 10px 15px; 
        background-color: white; 
        border-left: 5px solid {color}; 
        border-radius: 4px; 
        box-shadow: 0 1px 2px rgba(0,0,0,0.05); 
        margin-bottom: 10px; 
        display: flex; 
        align-items: center; 
        justify-content: space-between;">
        <span style="font-weight: 600; font-size: 1.1em; color: #333;">{icon} {title}</span>
        <span style="font-size: 0.8em; color: #888; text-transform: uppercase; letter-spacing: 0.5px;">{status}</span>
    </div>
    """, unsafe_allow_html=True)

def review_testing_page():
    st.markdown("## 🛠️ 提示词工程台 (Prompt Workbench)")
    st.caption("可视化调试复盘报告生成工作流。每个节点独立可控，支持实时修改 Prompt 并观察结果。")

    # 1. Session Selector
    with st.container():
        # Fetch last 20 sessions (with at least 7 card choices)
        query = """
            SELECT s.id, s.user_id, s.started_at, s.final_score, COUNT(e.id) as card_count 
            FROM game_sessions s 
            LEFT JOIN game_events e ON s.id = e.session_id AND e.type = 'card_choice'
            GROUP BY s.id 
            HAVING card_count >= 7 
            ORDER BY s.id DESC 
            LIMIT 20
        """
        sessions_df = cached_run_query(query)
        
        selected_session_id = None
        if isinstance(sessions_df, pd.DataFrame) and not sessions_df.empty:
            options = {f"Session {r['id']} | User {r['user_id']} | {format_ts(r['started_at'])} | {r['card_count']} Cards": r['id'] for _, r in sessions_df.iterrows()}
            selected_label = st.selectbox("选择调试场次 (Target Session)", list(options.keys()))
            selected_session_id = options[selected_label]
        else:
            st.warning("暂无满足条件的游戏记录 (需至少7次卡牌选择)")
            return

    if not selected_session_id:
        return

    # --- State Management ---
    # Data
    if 'wb_session_id' not in st.session_state or st.session_state.wb_session_id != selected_session_id:
        # Reset if session changed
        st.session_state.wb_session_id = selected_session_id
        st.session_state.wb_data = None
        st.session_state.wb_extract = None
        st.session_state.wb_story1 = None
        st.session_state.wb_story2 = None
    
    # Prompts (Initialize with defaults if empty)
    if 'prompt_extract' not in st.session_state: st.session_state.prompt_extract = ""
    if 'prompt_story1' not in st.session_state: st.session_state.prompt_story1 = ""
    if 'prompt_story2' not in st.session_state: st.session_state.prompt_story2 = ""

    # Helper: Call LLM
    def call_llm_direct(prompt, max_tokens=1000, temp=0.7):
        if not st.session_state.token:
            st.error("请先登录")
            return None
        try:
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            res = requests.post(f"{BACKEND_URL}/api/llm/story", 
                                json={"prompt": prompt, "max_tokens": max_tokens, "temperature": temp},
                                headers=headers)
            if res.ok:
                return res.json().get('story', "")
            else:
                st.error(f"LLM Error: {res.text}")
                return None
        except Exception as e:
            st.error(f"Req Error: {e}")
            return None

    # Layout
    c_node0, c_node1, c_node2, c_node3, c_node4 = st.tabs(["0. 数据锚点", "1. 关键点分析", "2. 故事构建(上)", "3. 故事构建(下)", "4. 最终报告"])

    # --- Node 0: Data Anchor ---
    with c_node0:
        render_node_header("Data Anchor", "done" if st.session_state.wb_data else "pending", "💾")
        
        if st.button("🔄 加载/重置数据 (Load Data)", type="primary"):
            with st.spinner("Loading..."):
                full_session = cached_run_query(f"SELECT * FROM game_sessions WHERE id = {selected_session_id}").iloc[0].to_dict()
                game_events = cached_run_query(f"SELECT * FROM game_events WHERE session_id = {selected_session_id} ORDER BY ts ASC")
                events_list = game_events.to_dict('records')
                st.session_state.wb_data = build_review_data(full_session, events_list)
                st.success("数据已加载")
                time.sleep(0.5)
                st.rerun()

        if st.session_state.wb_data:
            st.json(st.session_state.wb_data, expanded=False)
        else:
            st.info("请先点击加载数据")

    # --- Node 1: Extract ---
    with c_node1:
        status = "done" if st.session_state.wb_extract else ("pending" if st.session_state.wb_data else "waiting_prev")
        render_node_header("Analysis Agent", status, "🧠")

        if not st.session_state.wb_data:
            st.warning("请先在 Node 0 加载数据")
        else:
            # Prepare Prompt Template
            default_prompt = build_extract_prompt(st.session_state.wb_data)
            # If state prompt is empty or just initialized, maybe sync? 
            # Strategy: We want users to edit. If they edit, we keep it. 
            # If data changes, the DATA part of prompt changes. 
            # So we separate Logic Template vs Data Injection? 
            # For simplicity in this workbench, we just show the FULL prompt. 
            # If user wants to reset, they can clear it.
            
            val = st.session_state.prompt_extract if st.session_state.prompt_extract else default_prompt
            
            col_l, col_r = st.columns([1, 1])
            with col_l:
                st.markdown("**输入 (Prompt)**")
                new_prompt = st.text_area("Prompt Editor", value=val, height=400, key="editor_extract")
                
                btn_row = st.columns([1, 3])
                if btn_row[0].button("▶ 运行", key="run_node1", type="primary"):
                    st.session_state.prompt_extract = new_prompt # Save
                    with st.spinner("AI正在思考..."):
                        res = call_llm_direct(new_prompt, max_tokens=900, temp=0.2)
                        if res:
                            st.session_state.wb_extract = res
                            st.rerun()
                            
                if btn_row[1].button("↺ 重置 Prompt", key="reset_node1"):
                     st.session_state.prompt_extract = ""
                     st.rerun()

            with col_r:
                st.markdown("**输出 (Output)**")
                if st.session_state.wb_extract:
                    st.code(st.session_state.wb_extract, language="json")
                else:
                    st.info("等待运行...")

    # --- Node 2: Story Part 1 ---
    with c_node2:
        status = "done" if st.session_state.wb_story1 else ("pending" if st.session_state.wb_extract else "waiting_prev")
        render_node_header("Story Teller (Part 1)", status, "📖")

        if not st.session_state.wb_extract:
             st.warning("请先完成 Node 1 分析")
        else:
            default_prompt = build_story_prompt_part1(st.session_state.wb_data, st.session_state.wb_extract)
            val = st.session_state.prompt_story1 if st.session_state.prompt_story1 else default_prompt

            col_l, col_r = st.columns([1, 1])
            with col_l:
                st.markdown("**输入 (Prompt)**")
                new_prompt = st.text_area("Prompt Editor", value=val, height=400, key="editor_story1")
                
                btn_row = st.columns([1, 3])
                if btn_row[0].button("▶ 运行", key="run_node2", type="primary"):
                    st.session_state.prompt_story1 = new_prompt
                    with st.spinner("正在撰写故事..."):
                        res = call_llm_direct(new_prompt, max_tokens=1400, temp=0.7)
                        if res:
                            st.session_state.wb_story1 = res
                            st.rerun()

                if btn_row[1].button("↺ 重置 Prompt", key="reset_node2"):
                     st.session_state.prompt_story1 = ""
                     st.rerun()

            with col_r:
                st.markdown("**输出 (Output)**")
                if st.session_state.wb_story1:
                    st.markdown(st.session_state.wb_story1)
                else:
                    st.info("等待运行...")

    # --- Node 3: Story Part 2 ---
    with c_node3:
        status = "done" if st.session_state.wb_story2 else ("pending" if st.session_state.wb_extract else "waiting_prev")
        render_node_header("Story Teller (Part 2)", status, "💡")

        if not st.session_state.wb_extract:
             st.warning("请先完成 Node 1 分析 (本节点依赖 Extract 数据)")
        else:
            default_prompt = build_story_prompt_part2(st.session_state.wb_extract)
            val = st.session_state.prompt_story2 if st.session_state.prompt_story2 else default_prompt

            col_l, col_r = st.columns([1, 1])
            with col_l:
                st.markdown("**输入 (Prompt)**")
                new_prompt = st.text_area("Prompt Editor", value=val, height=400, key="editor_story2")
                
                btn_row = st.columns([1, 3])
                if btn_row[0].button("▶ 运行", key="run_node3", type="primary"):
                    st.session_state.prompt_story2 = new_prompt
                    with st.spinner("正在撰写启示..."):
                        res = call_llm_direct(new_prompt, max_tokens=1200, temp=0.7)
                        if res:
                            st.session_state.wb_story2 = res
                            st.rerun()
                
                if btn_row[1].button("↺ 重置 Prompt", key="reset_node3"):
                     st.session_state.prompt_story2 = ""
                     st.rerun()

            with col_r:
                st.markdown("**输出 (Output)**")
                if st.session_state.wb_story2:
                    st.markdown(st.session_state.wb_story2)
                else:
                    st.info("等待运行...")


    # --- Node 4: Final Report ---
    with c_node4:
        render_node_header("Final Report", "done" if (st.session_state.wb_story1 and st.session_state.wb_story2) else "waiting", "📑")
        
        if st.session_state.wb_story1 and st.session_state.wb_story2:
            full_md = st.session_state.wb_story1 + "\n\n" + st.session_state.wb_story2
            html = build_report_html(full_md, st.session_state.wb_data)
            st.components.v1.html(html, height=800, scrolling=True)
            
            st.markdown("---")
            st.download_button("📥 下载 HTML 报告", data=html, file_name="report.html", mime="text/html")
        else:
            st.info("请先完成 Node 2 和 Node 3 的故事生成。")

# --- Application Modules ---
def overview_page():
    st.header("🎛️ 驾驶舱 (Cockpit)")
    
    # --- Data Fetching ---
    # Fetch all sessions for client-side processing (efficient enough for <10k rows)
    # in production, do aggregation in SQL.
    sessions_df = cached_run_query("SELECT * FROM game_sessions")
    users_df = cached_run_query("SELECT id, created_at FROM users")
    
    if not isinstance(sessions_df, pd.DataFrame): sessions_df = pd.DataFrame()
    if not isinstance(users_df, pd.DataFrame): users_df = pd.DataFrame()
    
    # Pre-process
    if not sessions_df.empty:
        # timestamp is usually ms in this system based on format_ts
        sessions_df['start_dt'] = pd.to_datetime(sessions_df['started_at'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai')
        sessions_df['date'] = sessions_df['start_dt'].dt.date
    
    # --- Metrics ---
    total_users = len(users_df)
    total_games = len(sessions_df)
    
    # Active Today
    today = datetime.datetime.now(tz=BEIJING_TZ).date()
    if not sessions_df.empty:
        active_today = len(sessions_df[sessions_df['date'] == today])
        scores = sessions_df['final_score'].dropna()
        avg_score = scores.mean() if not scores.empty else 0
    else:
        active_today = 0
        avg_score = 0
        
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("👥 总用户数", f"{total_users:,}")
    with col2:
        st.metric("🎮 总游戏场次", f"{total_games:,}")
    with col3:
        st.metric("🚀 今日活跃场次", f"{active_today:,}")
    with col4:
        st.metric("📊 平均得分", f"{avg_score:.1f}")

    st.markdown("---")

    # --- Charts ---
    if sessions_df.empty:
        st.info("暂无足够数据展示图表")
        return

    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("📈 近30天活跃趋势")
        # Filter last 30 days
        last_30 = today - datetime.timedelta(days=30)
        daily_trend = sessions_df[sessions_df['date'] >= last_30].groupby('date').size().reset_index(name='count')
        # Fill missing days? For simplicity, line chart usually connects dots.
        # Let's ensure date format is string for Altair/Streamlit
        if not daily_trend.empty:
            daily_trend['date'] = daily_trend['date'].astype(str)
            st.line_chart(daily_trend, x='date', y='count', height=300)
        else:
            st.caption("近30天无数据")

    with c2:
        st.subheader("🎯 游戏模式分布")
        if 'game_mode' in sessions_df.columns:
            mode_dist = sessions_df['game_mode'].fillna('unknown').value_counts()
            st.bar_chart(mode_dist, height=300)
        else:
            st.caption("无模式数据")

    c3, c4 = st.columns([1, 1])
    
    with c3:
        st.subheader("🏆 得分分布")
        # Binning scores
        scores = sessions_df['final_score'].dropna()
        if not scores.empty:
            # Create interactive histogram via altair or simple bar chart of bins
            # Simple manual binning for st.bar_chart
            bins = [0, 60, 80, 100, 9999]
            labels = ['<60', '60-80', '80-100', '>100']
            score_cats = pd.cut(scores, bins=bins, labels=labels, right=False)
            st.bar_chart(score_cats.value_counts().sort_index())
        else:
            st.caption("无得分数据")

    with c4:
        st.subheader("⏱️ 最近5场游戏")
        recent = sessions_df.sort_values('started_at', ascending=False).head(5)
        # Simplify display
        display_cols = []
        if 'id' in recent.columns: display_cols.append('id')
        if 'user_id' in recent.columns: display_cols.append('user_id')
        if 'final_score' in recent.columns: display_cols.append('final_score')
        if 'game_mode' in recent.columns: display_cols.append('game_mode')
        if 'start_dt' in recent.columns: display_cols.append('start_dt')
        
        st.dataframe(recent[display_cols], hide_index=True, use_container_width=True)

def user_management_page():
    st.header("👤 用户全景视图 (User 360)")
    
    search_term = st.text_input("🔍 搜索用户 (手机号/ID/昵称)", "")
    
    # 获取用户 + 场次统计的聚合数据
    query = """
        SELECT u.id, u.username, u.phone, u.guardian_name, u.role, u.created_at,
               COUNT(g.id) as total_games,
               COALESCE(AVG(CASE WHEN g.final_score IS NOT NULL AND g.final_score > 0 THEN g.final_score END), 0) as avg_score,
               MAX(g.started_at) as last_played,
               GROUP_CONCAT(DISTINCT g.game_mode) as modes_played
        FROM users u
        LEFT JOIN game_sessions g ON u.id = g.user_id
    """
    params = ()
    if search_term:
        query += " WHERE u.phone LIKE ? OR u.username LIKE ? OR u.id = ?"
        wildcard = f"%{search_term}%"
        params = (wildcard, wildcard, search_term)
    query += " GROUP BY u.id ORDER BY total_games DESC"
    
    df = cached_run_query(query, params=params)
    
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("暂无用户数据")
        return
    
    # --- KPI ---
    k1, k2, k3 = st.columns(3)
    k1.metric("总用户数", len(df))
    active_users = len(df[df['total_games'] > 0])
    k2.metric("活跃用户 (≥1场)", active_users)
    k3.metric("总游戏场次", int(df['total_games'].sum()))
    
    st.markdown("---")
    
    # --- 用户列表 ---
    st.subheader("📋 用户列表")
    def get_user_display(row):
        nick = str(row.get('username') or '').strip()
        guard = str(row.get('guardian_name') or '').strip()
        if nick and guard: return f"{nick} ({guard})"
        return nick or guard or "未知"

    display_df = df.copy()
    display_df['显示身份'] = display_df.apply(get_user_display, axis=1)
    
    # 挑选并重命名列
    cols_to_show = ['id', '显示身份', 'phone', 'role', 'total_games', 'avg_score', 'modes_played']
    final_display = display_df[cols_to_show].copy()
    final_display['avg_score'] = final_display['avg_score'].apply(lambda x: f"{x:.1f}" if x else "0.0")
    final_display.columns = ['ID', '用户/守望者', '手机号', '角色', '场次数', '平均分', '游戏模式']
    
    st.dataframe(final_display, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # --- 用户详情 ---
    st.subheader("🔎 用户详情")
    user_ids = df['id'].tolist()
    selected_uid = st.selectbox("选择用户", user_ids, format_func=lambda x: f"User {x} — {df[df['id']==x].iloc[0].get('phone') or df[df['id']==x].iloc[0].get('username') or '未知'}")
    
    if selected_uid:
        user_row = df[df['id'] == selected_uid].iloc[0]
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**📱 手机号**: {user_row.get('phone') or '未绑定'}")
            st.markdown(f"**👤 昵称**: {user_row.get('username') or '未设置'}")
            st.markdown(f"**🛡️ 守望师**: {user_row.get('guardian_name') or '未设置'}")
            st.markdown(f"**🎮 总场次**: {int(user_row['total_games'])}   |   **📊 平均分**: {user_row['avg_score']:.0f}")
            st.markdown(f"**🎯 游戏模式**: {user_row.get('modes_played') or '无记录'}")
        
        with c2:
            st.markdown(f"**🔑 角色**: `{user_row.get('role') or 'user'}`")
            if user_row.get('last_played'):
                st.markdown(f"**🕐 最后游戏**: {format_ts(user_row['last_played'])}")
        
        # --- 该用户的游戏记录 ---
        if int(user_row['total_games']) > 0:
            st.markdown("##### 🎮 游戏记录")
            sessions = cached_run_query(
                "SELECT id, started_at, ended_at, final_score, game_mode, status FROM game_sessions WHERE user_id = ? ORDER BY started_at DESC",
                params=(selected_uid,)
            )
            if isinstance(sessions, pd.DataFrame) and not sessions.empty:
                sessions['时间'] = sessions['started_at'].apply(lambda x: format_ts(x) if x else '--')
                sessions['得分'] = sessions['final_score'].apply(lambda x: str(int(x)) if pd.notna(x) and x > 0 else '--')
                sessions['时长'] = sessions.apply(
                    lambda r: format_duration(r['ended_at'] - r['started_at']) if r.get('ended_at') and r.get('started_at') and r['ended_at'] > r['started_at'] else '--', axis=1
                )
                st.dataframe(
                    sessions[['id', '时间', 'game_mode', '得分', '时长', 'status']].rename(columns={'id':'Session ID', 'game_mode':'模式', 'status':'状态'}),
                    use_container_width=True, hide_index=True
                )
        
        # --- OSS 关联文件 ---
        st.markdown("##### 📂 关联 OSS 文件")
        st.caption(f"自动查找该用户上传的音频和复盘报告 (按 user_{selected_uid} 前缀匹配)")
        
        if st.session_state.get('token'):
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            
            tab_audio, tab_report = st.tabs(["🎤 录音文件", "📝 复盘报告"])
            
            with tab_audio:
                try:
                    res = requests.get(f"{BACKEND_URL}/api/admin/oss/files", 
                        params={"prefix": f"game-audio/user_{selected_uid}_", "maxKeys": 50, "delimiter": ""}, 
                        headers=headers, timeout=5)
                    if res.ok:
                        files = res.json().get('files', [])
                        if files:
                            for f in files:
                                name = f['name'].split('/')[-1]
                                st.markdown(f"🎵 [{name}]({f['url']})  ({f['size']/1024:.1f} KB)")
                        else:
                            st.info("该用户暂无录音文件")
                    else:
                        st.warning(f"获取失败: {res.status_code}")
                except Exception as e:
                    st.warning(f"无法连接后端 API: {e}")
            
            with tab_report:
                try:
                    res = requests.get(f"{BACKEND_URL}/api/admin/oss/files", 
                        params={"prefix": f"game-review/report_{selected_uid}_", "maxKeys": 50, "delimiter": ""}, 
                        headers=headers, timeout=5)
                    if res.ok:
                        files = res.json().get('files', [])
                        if files:
                            for f in files:
                                name = f['name'].split('/')[-1]
                                icon = "📄" if name.endswith('.html') else "📋"
                                st.markdown(f"{icon} [{name}]({f['url']})  ({f['size']/1024:.1f} KB)")
                        else:
                            st.info("该用户暂无复盘报告")
                    else:
                        st.warning(f"获取失败: {res.status_code}")
                except Exception as e:
                    st.warning(f"无法连接后端 API: {e}")
        else:
            st.warning("未登录后端 API，无法查询 OSS 文件")
    
    # --- Admin Actions ---
    if st.session_state.user_role == 'admin':
        st.divider()
        st.subheader("⚡ 管理员操作")
        c1, c2 = st.columns([1, 2])
        with c1:
            target_id = st.text_input("目标用户 ID")
        with c2:
            new_role = st.selectbox("设置权限等级", ["admin", "user", "guest"])
        if st.button("更新权限"):
            if target_id:
                rows, err = db_utils.execute_update("UPDATE users SET role = ? WHERE id = ?", (new_role, target_id))
                if err:
                    st.error(f"失败: {err}")
                elif rows > 0:
                    st.success(f"用户 {target_id} 权限已更新为 {new_role}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("未找到匹配的用户ID")

# --- Analysis Helpers ---

def get_analysis_data():
    """Fetch all necessary data for analysis"""
    # 1. Sessions
    sessions_df = cached_run_query("SELECT * FROM game_sessions")
    if not isinstance(sessions_df, pd.DataFrame):
        sessions_df = pd.DataFrame()
    
    # 2. Card Events (optimization: only fetch card_choice events)
    events_df = cached_run_query("SELECT * FROM game_events WHERE type = 'card_choice'")
    if not isinstance(events_df, pd.DataFrame):
        events_df = pd.DataFrame()
    
    return sessions_df, events_df

def process_daily_stats(sessions_df):
    if sessions_df.empty:
        return pd.DataFrame()
    
    # Ensure started_at is datetime
    # Timestamp is likely in milliseconds based on previous code (format_ts divides by 1000)
    sessions_df['date'] = pd.to_datetime(sessions_df['started_at'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.date
    
    daily_counts = sessions_df.groupby('date').size().reset_index(name='count')
    daily_counts = daily_counts.sort_values('date')
    return daily_counts

def process_card_stats(events_df):
    if events_df.empty:
        return pd.DataFrame()
        
    card_usage = []
    
    for _, row in events_df.iterrows():
        try:
            payload = parse_payload(row['payload'])
            card_id = payload.get('cardId')
            if card_id:
                card_usage.append({
                    'card_id': card_id,
                    'choice': payload.get('choice'),
                    'is_creative': payload.get('isCreativeOption', False),
                    'was_failure': payload.get('wasFailure', False)
                })
        except:
            continue
            
    if not card_usage:
        return pd.DataFrame()
        
    df = pd.DataFrame(card_usage)
    
    # Aggregation
    stats = df.groupby('card_id').agg(
        choices=('choice', 'count'),
        creative_uses=('is_creative', 'sum'),
        failures=('was_failure', 'sum')
    ).reset_index()
    
    stats.columns = ['Card ID', 'Total Choices', 'Creative Uses', 'Failures']
    stats = stats.sort_values('Total Choices', ascending=False)
    return stats


def game_analysis_page():
    st.header("🎮 业务数据分析 (Game Analytics)")
    
    # Load Data
    with st.spinner("正在加载分析数据..."):
        sessions_df, events_df = get_analysis_data()
        
    if sessions_df.empty:
        st.warning("暂无游戏数据")
        return

    # Tabs
    tab_overview, tab_sessions, tab_cards = st.tabs(["📊 核心指标 (Overview)", "🔎 场次明细 (Explorer)", "🎴 卡牌分析 (Cards)"])
    
    # --- Tab 1: Overview ---
    with tab_overview:
        # KPI Row
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        total_games = len(sessions_df)
        
        # Today's games
        today = datetime.datetime.now(tz=BEIJING_TZ).date()
        # Ensure date column exists for filtering
        sessions_df['date_obj'] = pd.to_datetime(sessions_df['started_at'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai').dt.date
        today_games = sessions_df[sessions_df['date_obj'] == today]
        today_count = len(today_games)
        
        # Average Score
        avg_score = sessions_df['final_score'].mean()
        
        # Avg Duration
        # Calculate duration for each session
        valid_durations = []
        for _, row in sessions_df.iterrows():
            s = row.get('started_at')
            e = row.get('ended_at')
            if s and e and e > s:
                valid_durations.append(e - s)
        
        avg_duration_ms = sum(valid_durations) / len(valid_durations) if valid_durations else 0
        avg_duration_str = format_duration(avg_duration_ms)

        kpi1.metric("总游戏场次", total_games)
        kpi2.metric("今日新增", today_count)
        kpi3.metric("平均得分", f"{avg_score:.1f}")
        kpi4.metric("平均游戏时长", avg_duration_str)
        
        st.markdown("---")
        
        # Charts
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("每日游戏场次趋势")
            daily_df = process_daily_stats(sessions_df)
            if not daily_df.empty:
                # Streamlit line chart expects date as index or x-axis
                st.line_chart(daily_df.set_index('date'))
            else:
                st.write("数据不足")
                
        with c2:
            st.subheader("得分分布")
            st.bar_chart(sessions_df['final_score'].value_counts())

    # --- Tab 2: Session Explorer ---
    with tab_sessions:
        st.caption("查询和复盘具体游戏场次")
        
        # Filters
        c_filter1, c_filter2 = st.columns([1, 2])
        with c_filter1:
            s_mode = st.selectbox("游戏模式", ["All"] + list(sessions_df['game_mode'].unique()))
            
        filtered_df = sessions_df.copy()
        if s_mode != "All":
            filtered_df = filtered_df[filtered_df['game_mode'] == s_mode]
            
        # Display Table
        display_cols = ['id', 'user_id', 'date_obj', 'game_mode', 'final_score']
        st.dataframe(
            filtered_df[display_cols].sort_values('id', ascending=False), 
            use_container_width=True,
            column_config={
                "date_obj": "Date",
                "final_score": st.column_config.ProgressColumn("Score", format="%d", min_value=0, max_value=120) # Approx max
            }
        )
        
        st.divider()
        st.subheader("🔬 单局详情复盘")
        target_sid = st.number_input("输入 Session ID 查看详情", min_value=1, step=1)
        
        if st.button("查看详情"):
             # Reuse build_review_data logic
             sess_row = sessions_df[sessions_df['id'] == target_sid]
             if not sess_row.empty:
                 row_dict = sess_row.iloc[0].to_dict()
                 # Fetch events for this session
                 sess_events = cached_run_query(f"SELECT * FROM game_events WHERE session_id = {target_sid} ORDER BY ts ASC")
                 if not sess_events.empty:
                     data = build_review_data(row_dict, sess_events.to_dict('records'))
                     
                     st.json(data['session'], expanded=False)
                     st.write(f"**总耗时:** {format_duration(data['durationMs'])}")
                     
                     st.write("##### 卡牌选择流")
                     for c in data['cards']:
                         with st.expander(f"Step {c['index']}: {c['cardId']} ({c['phase']})"):
                             st.write(f"**事件:** {c['eventText']}")
                             st.write(f"**选择:** {c['choice']}")
                             st.write(f"**结果:** {c['consequence']}")
                             st.write(f"**属性变化:** {c['attributeDelta']}")
                 else:
                     st.warning("未找到该场次的事件日志")
             else:
                 st.error("未找到该 Session ID")

    # --- Tab 3: Card Analytics ---
    with tab_cards:
        st.subheader("🎴 卡牌使用热度榜")
        
        card_stats = process_card_stats(events_df)
        
        if not card_stats.empty:
             st.dataframe(card_stats, use_container_width=True)
             
             # Visualize Top 10
             top_10 = card_stats.head(10)
             st.subheader("Top 10 被选卡牌")
             st.bar_chart(top_10.set_index('Card ID')['Total Choices'])
        else:
             st.info("暂无卡牌数据")

def card_management_page():
    st.header("🎴 卡牌全生命周期管理")

    if not st.session_state.get('token'):
        st.error("⚠️ 未检测到后端 API 令牌，请尝试重新登录。")
        return

    # Tabs for Lifecycle
    tab_active, tab_pending, tab_approved, tab_recycle, tab_generate = st.tabs([
        "🟢 使用中 (Active)", 
        "🟠 待审核 (Pending Review)", 
        "🔵 已通过 (Approved/Ready)",
        "🗑️ 回收站 (Recycle Bin)",
        "✨ AI 生成器"
    ])

    headers = {"Authorization": f"Bearer {st.session_state.token}"}

    # Helper: Fetch cards by status
    def get_cards_by_status(status):
        try:
            # Note: We added a new Admin API for this: GET /api/admin/cards?status=...
            # But we can also query DB directly since we are in the same environment (admin panel).
            # FOR CONSISTENCY and to use the same logic, let's query DB directly for display, 
            # effectively same as API but faster.
            # However, using API ensures we see what the backend sees.
            # Let's use requests to fetch from backend to verify backend filtering works too.
            res = requests.get(f"{BACKEND_URL}/api/admin/cards", params={"status": status}, headers=headers)
            if res.ok:
                return res.json().get('cards', [])
            return []
        except Exception as e:
            st.error(f"Error fetching {status} cards: {e}")
            return []

    # Helper: Action Button
    def action_button(card_id, action_name, new_status, key_suffix, confirm=False):
        if st.button(action_name, key=f"{action_name}_{card_id}_{key_suffix}"):
            try:
                payload = {"status": new_status}
                res = requests.put(f"{BACKEND_URL}/api/cards/{card_id}", json=payload, headers=headers)
                if res.ok:
                    st.success(f"操作成功: {action_name}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(f"操作失败: {res.text}")
            except Exception as e:
                st.error(f"Req Error: {e}")

    # --- 1. Active Cards (In Game) ---
    with tab_active:
        cards = get_cards_by_status("active")
        st.caption(f"当前线上版本使用的卡牌 (共 {len(cards)} 张)")
        if cards:
            df = pd.DataFrame(cards)
            # Simplified columns
            display_df = df[['id', 'key', 'safetyType', 'event', 'version', 'updatedAt']]
            st.dataframe(display_df, use_container_width=True)
            
            with st.expander("🛠️ 管理选中卡牌 (下架)"):
                card_id = st.number_input("输入 ID 下架到回收站", min_value=1, step=1, key="deactive_id")
                if st.button("🔴 下架 (Soft Delete)"):
                    try:
                        res = requests.delete(f"{BACKEND_URL}/api/cards/{card_id}", headers=headers)
                        if res.ok:
                            st.success(f"卡牌 {card_id} 已下架")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"失败: {res.text}")
                    except Exception as e:
                        st.error(f"Error: {e}")

    # --- 2. Pending Review ---
    with tab_pending:
        cards = get_cards_by_status("pending")
        st.caption(f"待审核卡牌 (共 {len(cards)} 张)")
        
        for card in cards:
            with st.expander(f"🆔 {card['id']} | {card['safetyType']} - {card['event'][:30]}..."):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.json(card)
                with c2:
                    st.write("#### 审核操作")
                    action_button(card['id'], "✅ 通过 (Approve)", "approved", "pending_app")
                    action_button(card['id'], "🚀 直接上线 (Active)", "active", "pending_act")
                    if st.button("📝 修改 (Edit)", key=f"edit_{card['id']}"):
                        st.session_state.editing_card = card
                    action_button(card['id'], "❌ 驳回 (Reject)", "deleted", "pending_del")

        # Edit Area
        if "editing_card" in st.session_state:
            st.divider()
            st.subheader(f"正在编辑卡牌: {st.session_state.editing_card['id']}")
            card = st.session_state.editing_card
            
            new_json = st.text_area("JSON Content", value=json.dumps(card, indent=2, ensure_ascii=False), height=300)
            if st.button("💾 保存修改"):
                try:
                    updated_data = json.loads(new_json)
                    # Filter out metadata that shouldn't be overridden raw if API handles it, 
                    # but endpoint expects body updates.
                    # PUT endpoint logic: merges body fields.
                    # We can pass the whole object.
                    res = requests.put(f"{BACKEND_URL}/api/cards/{card['id']}", json=updated_data, headers=headers)
                    if res.ok:
                        st.success("修改已保存")
                        del st.session_state.editing_card
                        st.rerun()
                    else:
                        st.error(f"保存失败: {res.text}")
                except Exception as e:
                    st.error(f"Error: {e}")


    # --- 3. Approved (Ready to Deploy) ---
    with tab_approved:
        cards = get_cards_by_status("approved")
        st.caption(f"审核通过，等待上线 (共 {len(cards)} 张)")
        for card in cards:
             with st.expander(f"🆔 {card['id']} | {card['safetyType']}"):
                st.write(card['event'])
                action_button(card['id'], "🚀 上线 (Publish)", "active", "appr_pub")

    # --- 4. Recycle Bin ---
    with tab_recycle:
        cards = get_cards_by_status("deleted")
        st.caption(f"回收站 (保留15天) (共 {len(cards)} 张)")
        st.dataframe(pd.DataFrame(cards), use_container_width=True)
        
        card_id = st.number_input("输入 ID 恢复", min_value=1, step=1, key="restore_id")
        action_button(card_id, "♻️ 恢复 (Restore Pending)", "pending", "recycle_res")

    # --- 5. Generate ---
    with tab_generate:
        st.subheader("🤖 AI 卡牌生成器")
        
        with st.form("generate_card_form"):
            topic = st.text_input("主题/新闻原型 (Topic)", placeholder="例如：校园霸凌，高年级抢低年级零花钱")
            content = st.text_area("详细描述 (Optional)", placeholder="补充更多细节...")
            submitted = st.form_submit_button("开始生成 (Generate)", use_container_width=True)
        
        if submitted:
            if not topic and not content:
                st.warning("请输入主题或内容")
            else:
                with st.spinner("AI 正在思考和创作中... (可能需要 10-20 秒)"):
                    try:
                        payload = {"topic": topic, "content": content}
                        resp = requests.post(f"{BACKEND_URL}/api/admin/generate-card", json=payload, headers=headers)
                        
                        if resp.ok:
                            data = resp.json()
                            st.session_state.generated_card = data.get("card")
                            st.success("生成成功！请在下方预览并保存。")
                        else:
                            st.error(f"生成失败: {resp.status_code} - {resp.text}")
                    except Exception as e:
                        st.error(f"请求错误: {e}")

        # Preview and Save
        if "generated_card" in st.session_state and st.session_state.generated_card:
            st.divider()
            st.subheader("📝 预览与保存")
            
            # Allow editing before save
            card_json = st.text_area("JSON Editor", value=json.dumps(st.session_state.generated_card, indent=2, ensure_ascii=False), height=400)
            
            if st.button("💾 确认并提交审核 (Pending)"):
                try:
                    card_data = json.loads(card_json)
                    # Status will be 'pending' by default from backend
                    resp = requests.post(f"{BACKEND_URL}/api/cards", json=card_data, headers=headers)
                    
                    if resp.ok:
                        saved_data = resp.json()
                        st.success(f"✅ 卡牌已提交至【待审核】! ID: {saved_data.get('id')}")
                        # Clear state
                        del st.session_state.generated_card
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"保存失败: {resp.status_code} - {resp.text}")
                except json.JSONDecodeError:
                    st.error("JSON 格式错误，请检查编辑器内容")
                except Exception as e:
                    st.error(f"保存请求错误: {e}")

def oss_management_page():
    st.header("📂 OSS 文件管理 (目录视图)")

    if not st.session_state.get('token'):
        st.error("⚠️ 未检测到后端 API 令牌，请尝试重新登录。")
        return

    headers = {"Authorization": f"Bearer {st.session_state.token}"}

    # State for current directory (prefix)
    if 'oss_current_path' not in st.session_state:
        st.session_state.oss_current_path = "" # Root

    # State for deletion confirmation
    if 'oss_delete_target' not in st.session_state:
        st.session_state.oss_delete_target = None

    # Breadcrumbs / Navigation
    current_path = st.session_state.oss_current_path
    
    col_nav1, col_nav2 = st.columns([4, 1])
    with col_nav1:
        if not current_path:
            st.markdown("### 🏠 根目录 (Root)")
        else:
            st.markdown(f"### 📂 /{current_path}")
            if st.button("⬅️ 返回上一级 (Back)", key="btn_back"):
                # "game-audio/user_123/" -> "game-audio/" -> ""
                parts = current_path.strip("/").split("/")
                if len(parts) > 1:
                    st.session_state.oss_current_path = "/".join(parts[:-1]) + "/"
                else:
                    st.session_state.oss_current_path = ""
                st.rerun()

    with col_nav2:
        if st.button("🔄 刷新", use_container_width=True):
            st.rerun()

    # --- Deletion Confirmation Dialog ---
    if st.session_state.oss_delete_target:
        target = st.session_state.oss_delete_target
        st.warning(f"⚠️ 正在请求删除文件：{target}", icon="⚠️")
        st.markdown("**请确认是否执行删除操作？此操作不可恢复！**")
        
        d_col1, d_col2 = st.columns([1, 1])
        with d_col1:
            if st.button("✅ 确认删除 (Yes, I'm sure)", type="primary", use_container_width=True):
                try:
                    del_res = requests.delete(
                        f"{BACKEND_URL}/api/admin/oss/files", 
                        json={"filename": target}, 
                        headers=headers
                    )
                    if del_res.ok:
                        st.success(f"已删除: {target}")
                        st.session_state.oss_delete_target = None
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"删除失败: {del_res.text}")
                except Exception as e:
                    st.error(f"请求错误: {e}")
        
        with d_col2:
            if st.button("❌ 取消 (Cancel)", use_container_width=True):
                st.session_state.oss_delete_target = None
                st.rerun()
        
        st.divider()

    # Fetch Data
    try:
        # Use delimiter to emulate directory structure
        params = {
            "maxKeys": 100, # Increased for browser view
            "delimiter": "/",
            "prefix": current_path
        }
            
        res = requests.get(f"{BACKEND_URL}/api/admin/oss/files", params=params, headers=headers)
        
        if res.ok:
            data = res.json()
            files = data.get('files', [])
            folders = data.get('folders', []) # These are prefixes like "game-audio/"
            
            if not files and not folders:
                st.info("此文件夹为空 (Empty)")
            
            # 1. Render Folders
            if folders:
                st.subheader("📁 文件夹")
                for folder_prefix in folders:
                    # Folder prefix usually implies full path from root, e.g. "game-audio/"
                    folder_name = folder_prefix
                    # If deeper, show relative name? 
                    # OSS prefixes are full paths.
                    # e.g. root -> "game-audio/"
                    # inside "game-audio/" -> "game-audio/sub/"
                    # Display logic:
                    display_name = folder_prefix
                    if current_path and folder_prefix.startswith(current_path):
                        display_name = folder_prefix[len(current_path):]
                    
                    c1, c2 = st.columns([4, 1])
                    c1.markdown(f"**📂 {display_name}**")
                    if c2.button("进入", key=f"enter_{folder_prefix}"):
                        st.session_state.oss_current_path = folder_prefix
                        st.rerun()
                st.divider()

            # 2. Render Files
            if files:
                st.subheader("📄 文件")
                # Table Header
                h1, h2, h3, h4 = st.columns([3, 1, 2, 1])
                h1.markdown("**Filename**")
                h2.markdown("**Size**")
                h3.markdown("**Time**")
                h4.markdown("**Action**")
                
                for f in files:
                    # Skip the folder placeholder itself (sometimes OSS returns folder key as object)
                    if f['name'] == current_path:
                        continue
                        
                    c1, c2, c3, c4 = st.columns([3, 1, 2, 1])
                    
                    # Display Name relative to current path
                    display_name = f['name']
                    if current_path and f['name'].startswith(current_path):
                        display_name = f['name'][len(current_path):]
                        
                    c1.markdown(f"[{display_name}]({f['url']})")
                    c2.write(f"{f['size']/1024:.1f} KB")
                    # Format time a bit if possible, or raw
                    try:
                        # OSS 返回的是 ISO 格式的 UTC 时间 (如 2023-01-01T12:00:00.000Z)
                        dt_utc = datetime.datetime.fromisoformat(f['lastModified'].replace('Z', '+00:00'))
                        dt_beijing = dt_utc.astimezone(BEIJING_TZ)
                        c3.write(dt_beijing.strftime("%Y-%m-%d %H:%M:%S"))
                    except:
                        c3.write(f['lastModified'].replace('T', ' ')[:19])
                    
                    if c4.button("🗑️", key=f"pre_del_{f['name']}", help="申请删除"):
                        st.session_state.oss_delete_target = f['name']
                        st.rerun()

        else:
            st.error(f"无法获取文件列表: {res.status_code} - {res.text}")

    except Exception as e:
        st.error(f"App Error: {e}")



def system_settings_page():
    st.header("⚙️ 系统设置")
    st.markdown("""
    欢迎来到系统管理中心。在这里你可以管理全局配置参数、监控数据库状态并下载数据备份。
    """)
    
    # 初始化常用参数（如果不存在）
    from db_utils import get_system_setting, set_system_setting
    defaults = [
        ("DEV_KEY", "sj0127wqt", "开发者登录密钥，用于本地测试绕过验证"),
        ("DEFAULT_GAME_TIME", "5000", "游戏默认倒计时时长（秒）"),
        ("GAME_MODES", """[
  {"id": "standard", "name": "标准版", "desc": "体验 15 张卡牌", "time": 5000, "detail": "启蒙5 / 成长5 / 青春5", "targetCards": 15, "distribution": {"启蒙期": 5, "成长期": 5, "青春期": 5}},
  {"id": "essence", "name": "精华版", "desc": "体验 9 张卡牌", "time": 3600, "detail": "启蒙3 / 成长3 / 青春3", "targetCards": 9, "distribution": {"启蒙期": 3, "成长期": 3, "青春期": 3}}
]""", "游戏模式逻辑定义（JSON数组格式）"),
        ("ATTRIBUTES_CONFIG", """{
  "initial": 3,
  "min": 0,
  "max": 10,
  "failureThreshold": 0
}""", "伍力值平衡参数（JSON对象格式）"),
        ("BRANDING_INFO", """{
  "title": "《AI在5000天·伍力全开》伍力值计分系统",
  "copyright": "© 2026 上海伍仟天数字科技有限公司 | 保留所有权利",
  "welcome_title": "欢迎来到AI 5000天<br>伍力全开的世界！"
}""", "全站品牌信息与欢迎语（JSON对象格式）")
    ]
    for key, val, desc in defaults:
        if get_system_setting(key) is None:
            set_system_setting(key, val, desc)

    tab_params, tab_db, tab_about = st.tabs(["🔧 业务参数配置", "💾 数据库体检与备份", "ℹ️ 关于系统"])
    
    with tab_params:
        st.subheader("全局业务参数")
        st.info("💡 **说明**：此处的参数直接影响系统的运行行为。例如修改 `DEV_KEY` 后，管理员登录时需使用新密钥。")
        
        # List all
        df = db_utils.run_query("SELECT key, value, description, updated_at FROM system_settings")
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.write("当前暂无自定义参数。")
        
        st.divider()
        st.markdown("#### 📝 新增或修改参数")
        with st.expander("点击展开编辑表单"):
            with st.form("upsert_setting"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    k = st.text_input("参数名 (Key)", placeholder="例如: DEV_KEY")
                with c2:
                    d = st.text_input("功能描述 (Description)", placeholder="简述该参数的作用")
                
                v = st.text_area("参数值 (Value)", placeholder="输入具体的值...")
                
                if st.form_submit_button("💾 保存配置并即时生效", use_container_width=True):
                    if k:
                        ok, err = db_utils.set_system_setting(k, v, d)
                        if ok:
                            st.success(f"✅ 配置 `{k}` 已成功保存并应用！")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ 保存失败: {err}")
                    else:
                        st.warning("⚠️ 参数名不能为空")
                        
    with tab_db:
        st.subheader("数据库运维健康站")
        if os.path.exists(db_utils.DB_PATH):
            size_mb = os.path.getsize(db_utils.DB_PATH) / (1024 * 1024)
            
            # Use columns for a card-like feel
            m1, m2 = st.columns(2)
            with m1:
                st.metric("数据库占用空间", f"{size_mb:.2f} MB")
            with m2:
                # Get table counts roughly
                tables = db_utils.get_all_tables()
                table_count = len(tables) if isinstance(tables, pd.DataFrame) else 0
                st.metric("总数据表数量", f"{table_count} 个")

            st.divider()
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("##### 🧹 性能优化")
                st.caption("重建索引并释放空闲空间。当感到数据库查询变慢时建议执行。")
                if st.button("立即执行数据库瘦身 (VACUUM)", use_container_width=True):
                    with st.spinner("正在优化中..."):
                        try:
                            # Use connection directly to run VACUUM
                            conn = db_utils.get_connection(read_only=False)
                            conn.execute("VACUUM")
                            conn.close()
                            st.success("✨ 数据库瘦身成功！")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 优化失败: {e}")
            
            with c2:
                st.markdown("##### 📥 数据安全备份")
                st.caption("下载当前的原始数据库文件。建议在进行大规模数据清理前备份。")
                try:
                    with open(db_utils.DB_PATH, "rb") as f:
                        st.download_button(
                            label="生成并下载数据库快照 (.db)",
                            data=f,
                            file_name=f"wqt_backup_{datetime.datetime.now(tz=BEIJING_TZ).strftime('%Y%m%d_%H%M%S')}.db",
                            mime="application/x-sqlite3",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"备份准备失败: {e}")
        else:
            st.error("🚨 警告：未检测到数据库文件路径，请检查代码配置。")

    with tab_about:
        st.markdown("### 🏢 WQT 中台管理系统")
        st.write("---")
        st.markdown(f"""
        - **当前版本**: `v1.1.0`
        - **构建环境**: `Agentic Automation`
        - **服务器时区**: `Asia/Shanghai (UTC+8)`
        - **系统运行状态**: 🟢 正常 (Healthy)
        """)
        st.write("---")
        st.caption("© 2026 WQT Project - 为 AI 赋能成长。")


# --- Data Audit System ---

def run_auto_audit():
    """Run automated rules to flag or trash sessions"""
    # 1. Fetch active sessions (or null status)
    df = db_utils.run_query("SELECT * FROM game_sessions WHERE status IS NULL OR status = 'active'")
    if df.empty:
        return 0, 0
        
    flagged_count = 0
    trashed_count = 0
    
    updates = [] # List of (new_status, id)
    
    for _, row in df.iterrows():
        sid = row['id']
        
        # Rule 1: Short Duration (< 60s)
        s_ts = row.get('started_at')
        e_ts = row.get('ended_at')
        duration = 0
        if s_ts and e_ts:
            try:
                duration = (int(e_ts) - int(s_ts)) / 1000
            except:
                duration = 0
        
        # Rule 2: Few Interactions (Check events or just trust duration/score)
        # For efficiency, let's just use duration & completion check today. 
        # Deep event check is slow for list.
        # We can also check if final_score is 0 or None for "abandoned" games
        
        new_status = None
        
        # Trash: < 10s or No Score (Aborted immediately)
        if duration < 10 and (row.get('final_score') is None or row.get('final_score') == 0):
            new_status = 'trash'
            trashed_count += 1
        
        # Flag: < 60s but maybe valid? 
        elif duration < 60:
            new_status = 'flagged'
            flagged_count += 1
            
        # Flag: Test users
        players_json = str(row.get('players_json', '')).lower()
        if 'test' in players_json or 'admin' in players_json:
            new_status = 'flagged'
            flagged_count += 1

        if new_status:
            updates.append((new_status, sid))
            
    # Batch update (Simulation loop)
    # Ideally use executemany, but db_utils wrapper might not support it directly easily.
    # Let's simple loop for now (Data volume low).
    for status, sid in updates:
        db_utils.execute_update("UPDATE game_sessions SET status = ? WHERE id = ?", (status, sid))
        
    return flagged_count, trashed_count

def data_audit_page():
    st.header("🧹 数据审计 (Data Audit)")
    
    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    
    # Get counts
    res = cached_run_query("SELECT status, COUNT(*) as c FROM game_sessions GROUP BY status")
    stats = {}
    if not res.empty:
        for _, r in res.iterrows():
            k = r['status'] if r['status'] else 'active' # Treat null as active
            stats[k] = r['c']
            
    active_c = stats.get('active', 0)
    flagged_c = stats.get('flagged', 0)
    trash_c = stats.get('trash', 0)
    
    with col1:
        st.metric("🟢 有效 (Active)", active_c)
    with col2:
        st.metric("🟠 待审核 (Flagged)", flagged_c)
    with col3:
        st.metric("🗑️ 回收站 (Trash)", trash_c)
    with col4:
        if st.button("⚡ 运行自动审计"):
            with st.spinner("正在分析数据..."):
                f, t = run_auto_audit()
            st.success(f"已处理: 标记 {f} 条, 移入回收站 {t} 条")
            time.sleep(1)
            st.rerun()

    st.markdown("---")
    
    tab_review, tab_trash, tab_all = st.tabs(["🧐 待审核 (Review)", "♻️ 回收站 (Bin)", "📋 全部列表"])
    
    # Helper: Action Column
    def render_actions(sid, current_status):
        c1, c2 = st.columns(2)
        key_base = f"audit_{sid}"
        
        if current_status == 'flagged':
            if c1.button("✅ 通过", key=f"{key_base}_approve"):
                db_utils.execute_update("UPDATE game_sessions SET status = 'active' WHERE id = ?", (sid,))
                st.rerun()
            if c2.button("🗑️ 丢弃", key=f"{key_base}_trash"):
                db_utils.execute_update("UPDATE game_sessions SET status = 'trash' WHERE id = ?", (sid,))
                st.rerun()
                
        elif current_status == 'trash':
            if c1.button("♻️ 还原", key=f"{key_base}_restore"):
                db_utils.execute_update("UPDATE game_sessions SET status = 'active' WHERE id = ?", (sid,))
                st.rerun()
            if c2.button("❌ 删除", key=f"{key_base}_del", type="primary"):
                # Hard Delete!
                db_utils.execute_update("DELETE FROM game_sessions WHERE id = ?", (sid,))
                st.warning(f"Session {sid} 已永久删除")
                time.sleep(0.5)
                st.rerun()

    # Helper: Format duration from ms
    def _fmt_duration(started_at, ended_at):
        if started_at and ended_at:
            try:
                dur_ms = int(ended_at) - int(started_at)
                if dur_ms <= 0:
                    return "-"
                return format_duration(dur_ms)
            except:
                pass
        return "-"
                
    # --- Tab 1: Review (待审核) ---
    with tab_review:
        # Enhanced query: join users, count cards
        review_query = """
            SELECT 
                gs.*,
                COALESCE(u.guardian_name, u.username, u.phone, 'Unknown') as user_display,
                (SELECT COUNT(*) FROM game_events ge WHERE ge.session_id = gs.id AND ge.type = 'card_selected') as card_count
            FROM game_sessions gs
            LEFT JOIN users u ON gs.user_id = u.id
            WHERE gs.status = 'flagged'
            ORDER BY gs.id DESC
        """
        to_review = cached_run_query(review_query)
        if to_review.empty:
            st.info("🎉 没有待审核的记录")
        else:
            for _, row in to_review.iterrows():
                user_name = row.get('user_display', 'Unknown')
                location = row.get('location', '-') or '-'
                card_count = row.get('card_count', 0)
                duration_str = _fmt_duration(row.get('started_at'), row.get('ended_at'))
                
                # 安全处理 final_score
                score_val = row.get('final_score')
                score_display = str(int(score_val)) if pd.notna(score_val) else '-'
                
                with st.expander(f"🆔 {row['id']} | 👤 {user_name} | 📍 {location} | 🎴 {card_count}张 | ⏱ {duration_str} | 得分: {score_display}"):
                    cols = st.columns([3, 1])
                    with cols[0]:
                        # Show key fields in a structured way
                        info_c1, info_c2 = st.columns(2)
                        with info_c1:
                            st.markdown(f"**用户:** {user_name}")
                            st.markdown(f"**地点:** {location}")
                            st.markdown(f"**游戏模式:** {row.get('game_mode') or '-'}")
                        with info_c2:
                            st.markdown(f"**卡牌数量:** {card_count} 张")
                            st.markdown(f"**游玩时长:** {duration_str}")
                            st.markdown(f"**得分:** {score_display}")
                        
                        st.markdown(f"**开始时间:** {format_ts(row.get('started_at'))}")
                        
                        with st.expander("📋 原始数据", expanded=False):
                            st.json({k:v for k,v in row.to_dict().items() if k not in ['payload_json', 'players_json', 'game_settings_json', 'status', 'user_display', 'card_count']})
                    with cols[1]:
                        st.markdown("**操作**")
                        render_actions(row['id'], 'flagged')

    # --- Tab 2: Trash ---
    with tab_trash:
        trash_items = cached_run_query("SELECT * FROM game_sessions WHERE status = 'trash'")
        if trash_items.empty:
            st.info("🗑️ 回收站也是空的")
        else:
            if st.button("🔥 清空回收站 (Delete All Trash)", type="primary"):
                db_utils.execute_update("DELETE FROM game_sessions WHERE status = 'trash'")
                st.success("回收站已清空")
                st.rerun()
            
            st.dataframe(trash_items[['id', 'started_at', 'final_score', 'game_mode']])
            
            sid_to_manage = st.number_input("管理 ID (从上方列表选择)", min_value=1, step=1, key="trash_mgr_id")
            if sid_to_manage:
                st.markdown(f"**管理 Session {sid_to_manage}:**")
                render_actions(sid_to_manage, 'trash')

    # --- Tab 3: All (全部列表 - 增强版) ---
    with tab_all:
        st.caption("展示所有游戏场次，可手动标记待审核")
        
        # Enhanced query: join users, count cards, compute duration
        all_query = """
            SELECT 
                gs.id,
                gs.user_id,
                COALESCE(u.guardian_name, u.username, u.phone, 'Unknown') as user_display,
                gs.location,
                gs.game_mode,
                gs.started_at,
                gs.ended_at,
                gs.final_score,
                gs.status,
                (SELECT COUNT(*) FROM game_events ge WHERE ge.session_id = gs.id AND ge.type = 'card_selected') as card_count
            FROM game_sessions gs
            LEFT JOIN users u ON gs.user_id = u.id
            ORDER BY gs.id DESC 
            LIMIT 200
        """
        all_data = cached_run_query(all_query)
        
        if all_data.empty:
            st.info("暂无数据")
        else:
            # Build display dataframe
            display_rows = []
            for _, row in all_data.iterrows():
                duration_str = _fmt_duration(row.get('started_at'), row.get('ended_at'))
                status_label = {
                    'active': '🟢 有效', 
                    'flagged': '🟠 待审核', 
                    'trash': '🗑️ 回收站'
                }.get(row.get('status') or 'active', row.get('status') or '🟢 有效')
                
                # 安全处理各字段
                score_val = row.get('final_score')
                score_display = int(score_val) if pd.notna(score_val) else '-'
                
                card_count_val = row.get('card_count')
                card_display = int(card_count_val) if pd.notna(card_count_val) else 0
                
                display_rows.append({
                    'ID': row['id'],
                    '用户': row.get('user_display') or 'Unknown',
                    '地点': row.get('location') or '-',
                    '卡牌数': card_display,
                    '游玩时长': duration_str,
                    '得分': score_display,
                    '模式': row.get('game_mode') or '-',
                    '状态': status_label,
                })
            
            display_df = pd.DataFrame(display_rows)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Manual flag section
            st.divider()
            st.subheader("🔶 手动标记待审核")
            
            flag_col1, flag_col2 = st.columns([2, 1])
            with flag_col1:
                flag_sid = st.number_input(
                    "输入 Session ID 标记为待审核", 
                    min_value=1, step=1, key="manual_flag_sid"
                )
            with flag_col2:
                st.write("") # Spacing
                st.write("") # Align with input
                if st.button("🔶 标记待审核", key="manual_flag_btn", use_container_width=True):
                    # Check current status
                    check = db_utils.run_query(
                        "SELECT id, status FROM game_sessions WHERE id = ?", (flag_sid,)
                    )
                    if isinstance(check, pd.DataFrame) and not check.empty:
                        current = check.iloc[0].get('status') or 'active'
                        if current == 'flagged':
                            st.warning(f"Session {flag_sid} 已经是待审核状态")
                        else:
                            db_utils.execute_update(
                                "UPDATE game_sessions SET status = 'flagged' WHERE id = ?", 
                                (flag_sid,)
                            )
                            st.success(f"✅ Session {flag_sid} 已标记为待审核")
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        st.error(f"未找到 Session ID: {flag_sid}")


# --- Main Layout ---
if not st.session_state.logged_in:
    login_page()
else:
    # Sidebar
    with st.sidebar:
        st.title(f"WQT 中台")
        st.write(f"当前用户: **{st.session_state.username}**")
        st.write(f"权限: `{st.session_state.user_role}`")
        
        if st.button("🔄 刷新数据 (Refresh)", use_container_width=True):
            clear_cache()
            st.toast("数据缓存已清除", icon="🔄")
            time.sleep(0.5)
            st.rerun()
            
        st.divider()
        if st.button("退出登录"):
            st.session_state.logged_in = False
            st.session_state.user_role = None
            st.rerun()
            
        st.divider()
        nav = st.radio("导航", ["🎛️ 驾驶舱", "👤 用户管理", "🎴 卡牌管理", "📂 OSS 文件管理", "🎮 游戏分析", "🧹 数据审计", "🔬 复盘测试", "⚙️ 系统设置"])
        st.divider()
        st.caption("🚀 系统版本: v1.1.3")
        st.caption("📅 更新时间: 2026-02-13 04:20")

    # Router
    if "驾驶舱" in nav:
        overview_page()
    elif "用户管理" in nav:
        user_management_page()
    elif "卡牌管理" in nav:
        card_management_page()
    elif "OSS 文件管理" in nav:
        oss_management_page()
    elif "游戏分析" in nav:
        game_analysis_page()
    elif "复盘测试" in nav:
        review_testing_page()
    elif "数据审计" in nav:
        data_audit_page()
    elif "系统设置" in nav:
        system_settings_page()
