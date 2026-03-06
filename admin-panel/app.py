import streamlit as st
import os
import pandas as pd
import db_utils
import time
import requests
import json
import datetime
import html as html_lib

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
if 'user_id' not in st.session_state:
    st.session_state.user_id = 0

ROLE_LABELS = {
    'boss': '👑 Boss',
    'operator': '🛠️ 运营',
    'watcher': '👁️ 守望者',
    'enterprise': '🏢 企业',
    'admin': '👑 Boss',
    'user': '👁️ 守望者',
}
LEVEL_LABELS = {
    'initial': '🔵 初始守望者',
    'advanced': '🟡 进阶守望者',
    'mentor': '🔴 导师级守望者',
}

def can_access(module):
    """检查当前登录用户是否可访问某模块"""
    role = st.session_state.user_role
    if role == 'boss':
        return True
    if role == 'operator':
        try:
            perm_json = db_utils.get_system_setting("operator_permissions", "{}")
            perms = json.loads(perm_json) if perm_json else {}
            uid_str = str(st.session_state.user_id)
            allowed = perms.get(uid_str, [])
            return module in allowed
        except Exception:
            return False
    return False

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
                    st.session_state.user_role = "boss"
                    st.session_state.user_id = 0
                    st.session_state.username = "Developer (Boss)"
                    st.success("身份验证成功！正在跳转...")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("密钥无效")

    with tab2:
        with st.form("user_login"):
            phone = st.text_input("手机号")
            submit_user = st.form_submit_button("登录", use_container_width=True)
            if submit_user and phone:
                df = cached_run_query("SELECT * FROM users WHERE phone = ?", params=(phone,))
                if isinstance(df, pd.DataFrame) and not df.empty:
                    user_row = df.iloc[0]
                    role = user_row.get('role', 'watcher')
                    # 只允许 boss 和 operator 登录 admin-panel
                    if role not in ('boss', 'operator'):
                        st.error("⛔ 访问被拒绝：仅 boss 和运营账号可登录管理后台")
                    else:
                        # 尝试获取后端 token（使用管理员专用接口）
                        try:
                            res = requests.post(f"{BACKEND_URL}/api/auth/admin-login", json={"phone": phone}, timeout=5)
                            if res.ok:
                                st.session_state.token = res.json().get("token")
                            else:
                                st.warning(f"⚠️ Token 获取失败（{res.status_code}），部分 AI 功能可能受限")
                                st.session_state.token = None
                        except Exception as e:
                            st.warning(f"⚠️ 无法连接后端服务，部分功能受限: {e}")
                            st.session_state.token = None

                        st.session_state.logged_in = True
                        st.session_state.user_role = role
                        st.session_state.user_id = int(user_row.get('id', 0))
                        st.session_state.username = user_row.get('guardian_name') or user_row.get('username') or phone
                        st.success(f"欢迎，{st.session_state.username}！")
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
    sessions_df = cached_run_query("""
        SELECT s.*,
          COALESCE(s.final_score, (
            SELECT COALESCE(json_extract(e.payload, '$.attributesAfter.安全力'), 0)
                 + COALESCE(json_extract(e.payload, '$.attributesAfter.脑波力'), 0)
                 + COALESCE(json_extract(e.payload, '$.attributesAfter.实感力'), 0)
                 + COALESCE(json_extract(e.payload, '$.attributesAfter.创心力'), 0)
                 + COALESCE(json_extract(e.payload, '$.attributesAfter.沟通力'), 0)
            FROM game_events e
            WHERE e.session_id = s.id AND e.type = 'card_choice'
            ORDER BY e.ts DESC LIMIT 1
          )) AS effective_score,
          COALESCE(s.ended_at, (
            SELECT MAX(e.ts) FROM game_events e
            WHERE e.session_id = s.id AND e.type = 'card_choice'
          )) AS effective_ended_at
        FROM game_sessions s
    """)
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
        scores = sessions_df['effective_score'].dropna()
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
        last_30 = today - datetime.timedelta(days=29) # Include today
        daily_counts = sessions_df[sessions_df['date'] >= last_30].groupby('date').size()
        
        # Create a date range for the last 30 days
        date_range = pd.date_range(start=last_30, end=today)
        
        # Prepare data for heatmap
        heatmap_data = []
        for d in date_range:
            d_date = d.date()
            count = daily_counts.get(d_date, 0)
            level = 0
            if count > 0: level = 1
            if count > 2: level = 2
            if count > 5: level = 3
            if count > 8: level = 4
            
            heatmap_data.append({
                "date": d_date.strftime("%Y-%m-%d"),
                "count": count,
                "level": level,
                "weekday": d.weekday() # 0=Mon, 6=Sun
            })
            
        # Simplified Grid Layout (7 cols)
        # We can just dump 30 divs in a container with grid-template-columns: repeat(7, ...);
        # To align properly (e.g. if today is Wed, the last item is Wed), we might want to shift?
        # But "Last 30 Days" usually implies just a sequence. 
        # If we want a calendar view, we should align strictly.
        # Let's align strictly: pad start with empty boxes until the correct weekday of `last_30`.
        
        first_day_weekday = date_range[0].weekday() # 0=Mon
        # Pad empty slots
        padded_data = [{"level": -1, "date": "", "count": 0}] * first_day_weekday + heatmap_data
        
        # CSS for Grid
        st.markdown("""
        <style>
            .heatmap-calendar {
                display: grid;
                grid-template-columns: repeat(7, 1fr);
                gap: 4px;
                max-width: 300px; /* Limit width to force rows */
                padding: 10px 0;
            }
            .day-box {
                aspect-ratio: 1;
                border-radius: 3px;
                background-color: #ebedf0;
                cursor: pointer;
                position: relative;
                font-size: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: transparent; /* Hide text unless debug */
            }
            .day-box:hover::after {
                content: attr(data-tooltip);
                position: absolute;
                bottom: 100%;
                left: 50%;
                transform: translateX(-50%);
                background-color: #333;
                color: #fff;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
                white-space: nowrap;
                z-index: 10;
                pointer-events: none;
                margin-bottom: 5px;
            }
            .level-0 { background-color: #ebedf0; }
            .level-1 { background-color: #9be9a8; }
            .level-2 { background-color: #40c463; }
            .level-3 { background-color: #30a14e; }
            .level-4 { background-color: #216e39; }
            .level--1 { background-color: transparent; cursor: default; }
            
            .weekday-header {
                display: grid;
                grid-template-columns: repeat(7, 1fr);
                gap: 4px;
                max-width: 300px;
                margin-bottom: 5px;
                font-size: 10px;
                color: #666;
                text-align: center;
            }
        </style>
        """, unsafe_allow_html=True)
        
        # Header
        headers = ["一", "二", "三", "四", "五", "六", "日"]
        header_html = "".join([f"<div>{h}</div>" for h in headers])
        st.markdown(f'<div class="weekday-header">{header_html}</div>', unsafe_allow_html=True)
        
        # Grid
        html_boxes = ""
        for item in padded_data:
            if item['level'] == -1:
                html_boxes += '<div class="day-box level--1"></div>'
            else:
                tooltip = f"{item['date']}: {item['count']} 场"
                html_boxes += f'<div class="day-box level-{item["level"]}" data-tooltip="{tooltip}"></div>'
            
        st.markdown(f'<div class="heatmap-calendar">{html_boxes}</div>', unsafe_allow_html=True)
        st.caption("最近30天 (深色表示高频)")

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
        scores = sessions_df['effective_score'].dropna()
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
        recent = sessions_df.sort_values('started_at', ascending=False).head(5).copy()
        
        # Calc duration in minutes（优先 ended_at，否则用最后一张卡牌时间戳）
        if 'effective_ended_at' in recent.columns and 'started_at' in recent.columns:
            recent['duration_mins'] = (recent['effective_ended_at'] - recent['started_at']) / 1000 / 60
            recent['duration_mins'] = recent['duration_mins'].apply(lambda x: f"{x:.1f} min" if pd.notnull(x) and x > 0 else "N/A")
        else:
             recent['duration_mins'] = "N/A"

        # Rename columns for better display
        display_map = {
            'id': 'ID',
            'user_id': 'User',
            'username': 'Name', # Try checking username too
            'effective_score': 'Score',
            'location': 'Location',
            'duration_mins': 'Duration',
            'start_dt': 'Time'
        }
        
        # Filter existing columns
        cols_to_show = [c for c in display_map.keys() if c in recent.columns]
        recent_display = recent[cols_to_show].rename(columns=display_map)
        
        # Format Time
        if 'Time' in recent_display.columns:
             recent_display['Time'] = recent_display['Time'].dt.strftime('%m-%d %H:%M')
        
        st.dataframe(recent_display, hide_index=True, use_container_width=True)

def user_management_page():
    st.header("👤 用户管理")

    tab_list, tab_level_apps, tab_feedback = st.tabs(["📋 用户列表", "📩 等级申请审核", "💬 感想与反馈"])

    # ── Tab 1: 用户列表 ──
    with tab_list:
        search_term = st.text_input("🔍 搜索用户 (手机号/ID/昵称)", "")
        query = """
            SELECT u.id, u.username, u.phone, u.guardian_name, u.role,
                   u.watcher_level, u.enterprise_id, u.created_at,
                   COUNT(g.id) as total_games,
                   COALESCE(AVG(CASE WHEN g.final_score IS NOT NULL AND g.final_score > 0 THEN g.final_score END), 0) as avg_score,
                   MAX(g.started_at) as last_played,
                   GROUP_CONCAT(DISTINCT g.game_mode) as modes_played
            FROM users u
            LEFT JOIN game_sessions g ON u.id = g.user_id
        """
        params = ()
        if search_term:
            query += " WHERE u.phone LIKE ? OR u.username LIKE ? OR u.guardian_name LIKE ? OR CAST(u.id AS TEXT) = ?"
            wildcard = f"%{search_term}%"
            params = (wildcard, wildcard, wildcard, search_term)
        query += " GROUP BY u.id ORDER BY total_games DESC"

        df = cached_run_query(query, params=params)
        if not isinstance(df, pd.DataFrame) or df.empty:
            st.info("暂无用户数据")
        else:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("总用户数", len(df))
            k2.metric("活跃用户 (≥1场)", len(df[df['total_games'] > 0]))
            k3.metric("总游戏场次", int(df['total_games'].sum()))
            k4.metric("守望者总数", len(df[df['role'].isin(['watcher', 'user'])]))

            st.divider()

            def get_display(row):
                guard = str(row.get('guardian_name') or '').strip()
                nick = str(row.get('username') or '').strip()
                return guard or nick or "未知"

            display_df = df.copy()
            display_df['身份'] = display_df.apply(get_display, axis=1)
            display_df['角色'] = display_df['role'].apply(lambda r: ROLE_LABELS.get(r, r))
            display_df['等级'] = display_df['watcher_level'].apply(lambda l: LEVEL_LABELS.get(l, l) if l else '-')
            display_df['平均分'] = display_df['avg_score'].apply(lambda x: f"{x:.1f}" if x else "0.0")
            cols = ['id', '身份', 'phone', '角色', '等级', 'total_games', '平均分']
            final = display_df[cols].copy()
            final.columns = ['ID', '守望师', '手机号', '角色', '等级', '场次', '平均分']
            st.dataframe(final, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("🔎 用户详情")
            user_ids = df['id'].tolist()
            selected_uid = st.selectbox(
                "选择用户",
                user_ids,
                format_func=lambda x: f"#{x} {df[df['id']==x].iloc[0].get('guardian_name') or df[df['id']==x].iloc[0].get('phone') or '未知'}"
            )
            if selected_uid:
                user_row = df[df['id'] == selected_uid].iloc[0]
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(f"**📱 手机号**: {user_row.get('phone') or '未绑定'}")
                    st.markdown(f"**🛡️ 守望师名**: {user_row.get('guardian_name') or '未设置'}")
                    st.markdown(f"**🎮 总场次**: {int(user_row['total_games'])}   |   **📊 平均分**: {user_row['avg_score']:.0f}")
                    st.markdown(f"**🎯 模式记录**: {user_row.get('modes_played') or '无'}")
                with c2:
                    st.markdown(f"**角色**: {ROLE_LABELS.get(user_row.get('role'), user_row.get('role') or '-')}")
                    st.markdown(f"**等级**: {LEVEL_LABELS.get(user_row.get('watcher_level'), '-')}")
                    if user_row.get('last_played'):
                        st.markdown(f"**最后游戏**: {format_ts(user_row['last_played'])}")

                # 游戏记录
                if int(user_row['total_games']) > 0:
                    with st.expander("🎮 游戏记录"):
                        sessions = cached_run_query(
                            "SELECT id, started_at, ended_at, final_score, game_mode, status FROM game_sessions WHERE user_id = ? ORDER BY started_at DESC",
                            params=(selected_uid,)
                        )
                        if isinstance(sessions, pd.DataFrame) and not sessions.empty:
                            sessions['时间'] = sessions['started_at'].apply(lambda x: format_ts(x) if x else '--')
                            sessions['得分'] = sessions['final_score'].apply(lambda x: str(int(x)) if pd.notna(x) else '--')
                            sessions['时长'] = sessions.apply(
                                lambda r: format_duration(r['ended_at'] - r['started_at'])
                                if r.get('ended_at') and r.get('started_at') and r['ended_at'] > r['started_at'] else '--', axis=1
                            )
                            st.dataframe(
                                sessions[['id', '时间', 'game_mode', '得分', '时长', 'status']].rename(
                                    columns={'id': 'Session', 'game_mode': '模式', 'status': '状态'}
                                ), use_container_width=True, hide_index=True
                            )

                # OSS 关联文件
                if st.session_state.get('token'):
                    with st.expander("📂 关联 OSS 文件"):
                        headers = {"Authorization": f"Bearer {st.session_state.token}"}
                        tab_a, tab_r = st.tabs(["🎤 录音", "📝 复盘报告"])
                        with tab_a:
                            try:
                                res = requests.get(f"{BACKEND_URL}/api/admin/oss/files",
                                    params={"prefix": f"game-audio/user_{selected_uid}_", "maxKeys": 50, "delimiter": ""},
                                    headers=headers, timeout=5)
                                if res.ok:
                                    for f in res.json().get('files', []):
                                        st.markdown(f"🎵 [{f['name'].split('/')[-1]}]({f['url']})  ({f['size']/1024:.1f} KB)")
                                else:
                                    st.info("暂无录音文件")
                            except Exception as e:
                                st.warning(str(e))
                        with tab_r:
                            try:
                                res = requests.get(f"{BACKEND_URL}/api/admin/oss/files",
                                    params={"prefix": f"game-review/report_{selected_uid}_", "maxKeys": 50, "delimiter": ""},
                                    headers=headers, timeout=5)
                                if res.ok:
                                    for f in res.json().get('files', []):
                                        icon = "📄" if f['name'].endswith('.html') else "📋"
                                        st.markdown(f"{icon} [{f['name'].split('/')[-1]}]({f['url']})  ({f['size']/1024:.1f} KB)")
                                else:
                                    st.info("暂无复盘报告")
                            except Exception as e:
                                st.warning(str(e))

                # Boss 操作区
                if st.session_state.user_role == 'boss':
                    st.divider()
                    st.markdown("**⚡ Boss 操作**")
                    bc1, bc2, bc3 = st.columns(3)
                    with bc1:
                        new_role = st.selectbox("设置角色", ['watcher', 'operator', 'boss', 'enterprise'], key=f"role_{selected_uid}")
                        if st.button("更新角色", key=f"updrole_{selected_uid}"):
                            _, err = db_utils.execute_update("UPDATE users SET role = ? WHERE id = ?", (new_role, selected_uid))
                            if err:
                                st.error(err)
                            else:
                                st.success(f"角色已更新为 {new_role}")
                                clear_cache(); st.rerun()
                    with bc2:
                        new_level = st.selectbox("设置等级", ['initial', 'advanced', 'mentor'], key=f"lv_{selected_uid}")
                        level_note = st.text_input("备注原因", key=f"lvnote_{selected_uid}")
                        if st.button("更新等级", key=f"updlv_{selected_uid}"):
                            if st.session_state.get('token'):
                                try:
                                    res = requests.put(
                                        f"{BACKEND_URL}/api/admin/users/{selected_uid}/level",
                                        json={"level": new_level, "note": level_note},
                                        headers={"Authorization": f"Bearer {st.session_state.token}"}
                                    )
                                    if res.ok:
                                        st.success(f"等级已更新为 {LEVEL_LABELS.get(new_level, new_level)}")
                                        clear_cache(); st.rerun()
                                    else:
                                        st.error(res.text)
                                except Exception as e:
                                    st.error(str(e))
                            else:
                                _, err = db_utils.execute_update("UPDATE users SET watcher_level = ? WHERE id = ?", (new_level, selected_uid))
                                if not err:
                                    st.success("等级已更新"); clear_cache(); st.rerun()
                    with bc3:
                        ent_id = st.text_input("设置企业ID（子账号归属）", key=f"ent_{selected_uid}")
                        if st.button("绑定企业", key=f"bindent_{selected_uid}") and ent_id:
                            _, err = db_utils.execute_update("UPDATE users SET enterprise_id = ? WHERE id = ?", (ent_id, selected_uid))
                            if not err:
                                st.success("企业账号已绑定"); clear_cache(); st.rerun()

    # ── Tab 2: 等级申请审核 ──
    with tab_level_apps:
        if not can_access('user_management') and st.session_state.user_role != 'boss':
            st.warning("⛔ 无权访问")
        else:
            st.subheader("📩 守望者升级申请队列")
            status_filter = st.radio("筛选", ['pending', 'approved', 'rejected'], horizontal=True)
            apps_df = cached_run_query("""
                SELECT la.id, la.user_id, u.guardian_name, u.phone,
                       la.from_level, la.to_level, la.reason, la.status, la.created_at, la.note
                FROM watcher_level_applications la
                JOIN users u ON u.id = la.user_id
                WHERE la.status = ?
                ORDER BY la.created_at DESC
            """, params=(status_filter,))

            if not isinstance(apps_df, pd.DataFrame) or apps_df.empty:
                st.info("暂无申请记录")
            else:
                for _, row in apps_df.iterrows():
                    with st.expander(f"#{row['id']} {row['guardian_name'] or row['phone']} | {LEVEL_LABELS.get(row['from_level'],row['from_level'])} → {LEVEL_LABELS.get(row['to_level'],row['to_level'])}"):
                        st.markdown(f"**申请时间**: {format_ts(row['created_at'])}")
                        st.markdown(f"**申请理由**: {row['reason'] or '（未填写）'}")
                        if status_filter == 'pending' and st.session_state.get('token'):
                            headers = {"Authorization": f"Bearer {st.session_state.token}"}
                            note = st.text_input("审核备注", key=f"anote_{row['id']}")
                            ac1, ac2 = st.columns(2)
                            with ac1:
                                if st.button("✅ 通过", key=f"app_{row['id']}"):
                                    res = requests.put(f"{BACKEND_URL}/api/admin/level-applications/{row['id']}",
                                        json={"action": "approve", "note": note}, headers=headers)
                                    if res.ok:
                                        st.success("已通过，等级已更新"); clear_cache(); st.rerun()
                                    else:
                                        st.error(res.text)
                            with ac2:
                                if st.button("❌ 驳回", key=f"rej_{row['id']}"):
                                    res = requests.put(f"{BACKEND_URL}/api/admin/level-applications/{row['id']}",
                                        json={"action": "reject", "note": note}, headers=headers)
                                    if res.ok:
                                        st.success("已驳回"); clear_cache(); st.rerun()
                                    else:
                                        st.error(res.text)
                        elif status_filter != 'pending':
                            st.markdown(f"**审核备注**: {row.get('note') or '无'}")

    # ── Tab 3: 感想与反馈 ──
    with tab_feedback:
        st.subheader("💬 用户感想与系统反馈")
        fb_filter = st.radio("类型", ['all', 'reflection', 'bug'], format_func=lambda x: {'all':'全部','reflection':'感想','bug':'问题反馈'}[x], horizontal=True)
        reviewed_filter = st.checkbox("只看未读", value=True)

        q = """
            SELECT f.id, f.type, f.content, f.created_at, f.reviewed,
                   u.guardian_name, u.phone, f.activity_id
            FROM user_feedback f
            JOIN users u ON u.id = f.user_id
        """
        conds, p = [], []
        if fb_filter != 'all':
            conds.append("f.type = ?"); p.append(fb_filter)
        if reviewed_filter:
            conds.append("f.reviewed = 0")
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY f.created_at DESC"

        fb_df = cached_run_query(q, params=tuple(p) if p else None)
        if not isinstance(fb_df, pd.DataFrame) or fb_df.empty:
            st.info("暂无反馈记录")
        else:
            st.caption(f"共 {len(fb_df)} 条")
            for _, row in fb_df.iterrows():
                type_icon = "💭" if row['type'] == 'reflection' else "🐛"
                label = f"{type_icon} {row['guardian_name'] or row['phone']} — {format_ts(row['created_at'])}"
                if not row['reviewed']:
                    label = "🔴 " + label
                with st.expander(label):
                    st.write(row['content'])
                    if st.session_state.get('token') and not row['reviewed']:
                        if st.button("标记已读", key=f"fbread_{row['id']}"):
                            headers = {"Authorization": f"Bearer {st.session_state.token}"}
                            requests.put(f"{BACKEND_URL}/api/admin/feedback/{row['id']}/read", headers=headers)
                            clear_cache(); st.rerun()

# --- Analysis Helpers ---

def get_analysis_data():
    """Fetch all necessary data for analysis"""
    # 1. Sessions
    sessions_df = cached_run_query("""
        SELECT s.*,
          COALESCE(s.final_score, (
            SELECT COALESCE(json_extract(e.payload, '$.attributesAfter.安全力'), 0)
                 + COALESCE(json_extract(e.payload, '$.attributesAfter.脑波力'), 0)
                 + COALESCE(json_extract(e.payload, '$.attributesAfter.实感力'), 0)
                 + COALESCE(json_extract(e.payload, '$.attributesAfter.创心力'), 0)
                 + COALESCE(json_extract(e.payload, '$.attributesAfter.沟通力'), 0)
            FROM game_events e
            WHERE e.session_id = s.id AND e.type = 'card_choice'
            ORDER BY e.ts DESC LIMIT 1
          )) AS effective_score,
          COALESCE(s.ended_at, (
            SELECT MAX(e.ts) FROM game_events e
            WHERE e.session_id = s.id AND e.type = 'card_choice'
          )) AS effective_ended_at
        FROM game_sessions s
    """)
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
        avg_score = sessions_df['effective_score'].mean()
        
        # Avg Duration（优先 ended_at，否则用最后一张卡牌时间戳）
        valid_durations = []
        for _, row in sessions_df.iterrows():
            s = row.get('started_at')
            e = row.get('effective_ended_at')
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
            st.bar_chart(sessions_df['effective_score'].value_counts())

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
        display_cols = ['id', 'user_id', 'date_obj', 'game_mode', 'effective_score']
        st.dataframe(
            filtered_df[display_cols].sort_values('id', ascending=False),
            use_container_width=True,
            column_config={
                "date_obj": "Date",
                "effective_score": st.column_config.ProgressColumn("Score", format="%d", min_value=0, max_value=120) # Approx max
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

def _render_card_attr_effects(options):
    """将 attributeEffects 渲染为彩色标签（网格缩略）"""
    html_parts = []
    for opt_key in ['A', 'B', 'C']:
        opt = options.get(opt_key, {})
        effects = opt.get('attributeEffects', {})
        tags = []
        for attr, val in effects.items():
            if val and val != 0:
                color = '#4CAF50' if val > 0 else '#f44336'
                sign = '+' if val > 0 else ''
                tags.append(f'<span style="background:{color};color:white;border-radius:4px;padding:1px 6px;font-size:11px;margin:1px">{attr}{sign}{val}</span>')
        no_change = '<span style="color:#999;font-size:11px">无变化</span>'
        html_parts.append(f"<div style='margin-bottom:4px'><b>{opt_key}</b>: {''.join(tags) if tags else no_change}</div>")
    return ''.join(html_parts)

def _render_card_visual(card, selected=False):
    """渲染一张卡牌的 HTML 卡片"""
    branch = card.get('branch', 'release')
    status = card.get('status', 'pending')
    branch_badge = '🟢 发布版' if branch == 'release' else '🔵 测试版'
    status_colors = {'active': '#4CAF50', 'pending': '#FF9800', 'approved': '#2196F3', 'deleted': '#9E9E9E'}
    status_color = status_colors.get(status, '#9E9E9E')
    safety = card.get('safetyType', '')
    phase = card.get('phase', '')
    event_text = (card.get('event') or '')[:60] + ('...' if len(card.get('event','')) > 60 else '')
    version_label = card.get('versionLabel') or card.get('version_label') or f"v{card.get('version', 1)}"
    border = '3px solid #1976D2' if selected else '1px solid #ddd'

    return f"""
    <div style="border:{border};border-radius:10px;padding:12px;margin:6px 0;
         background:linear-gradient(135deg,#1565C0 0%,#B8860B 100%);
         color:white;position:relative;min-height:140px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:8px">
        <span style="background:rgba(255,255,255,0.25);border-radius:4px;padding:2px 8px;font-size:12px;font-weight:bold">{safety}</span>
        <span style="background:rgba(255,255,255,0.25);border-radius:4px;padding:2px 8px;font-size:12px">{phase}</span>
      </div>
      <div style="font-size:13px;line-height:1.5;margin-bottom:10px;min-height:50px">{event_text}</div>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:11px;opacity:0.85;color:white;">{branch_badge} · {version_label}</span>
        <span style="background:{status_color};border-radius:4px;padding:1px 6px;font-size:11px;color:white;">{status}</span>
      </div>
    </div>"""

def _build_card_view_html(card, annotations, token='', backend_url='http://127.0.0.1:8080'):
    """自包含卡牌详情 HTML：Word 风格批注（选中→高亮→悬浮编辑弹窗）"""
    def _esc(t): return html_lib.escape(str(t or ''))

    def _highlight(text, anns):
        if not text: return ''
        result = _esc(text)
        import re
        for ann in anns:
            raw_sel = str(ann.get('selected_text', '')).strip()
            if not raw_sel: continue
            nid = str(ann.get('id', ''))
            content = ann.get('content', '')
            completed = ann.get('completed', False)
            
            # 基于“单词/汉字组”的模糊分割，忽略中间的任意空白和换行
            words = [re.escape(_esc(w)) for w in re.split(r'\s+', raw_sel) if w]
            if not words:
                continue
            
            pattern_str = r'\s+'.join(words)
            cls = 'ann-done' if completed else 'ann-hl'
            data = (f'data-nid="{nid}" data-content="{_esc(content)}" '
                    f'data-sel="{_esc(raw_sel)}" data-completed="{str(completed).lower()}"')
                    
            def replacer(match):
                m = match.group(0)
                if 'data-nid' in m: return m
                return f'<mark class="{cls}" {data}>{m}</mark>'
            
            try:
                result = re.sub(pattern_str, replacer, result, count=1)
            except Exception:
                pass
        return result.replace('\r\n', '<br>').replace('\n', '<br>')

    card_id = card.get('id', 0)
    safety = _esc(card.get('safetyType', ''))
    phase = _esc(card.get('phase', ''))
    audio_url = f"http://oss.ai5000days.com/cards_audio/{card_id}.mp3"
    event_html = _highlight(card.get('event', ''), annotations)
    opt_colors = {'A': '#1565C0', 'B': '#6A1B9A', 'C': '#E65100'}
    opts_html = ''
    options = card.get('options', {})
    for opt_key in ['A', 'B', 'C']:
        opt = options.get(opt_key, {})
        if not opt:
            continue
        t_html = _highlight(opt.get('text', ''), annotations)
        c_html = _highlight(opt.get('consequence', ''), annotations)
        col = opt_colors.get(opt_key, '#333')
        cons_sec = f'<div class="cons">后果：{c_html}</div>' if c_html else ''
        effects = opt.get('attributeEffects', {})
        eff_tags = ''.join(
            f'<span class="eff {"pos" if v > 0 else "neg"}">{a}{"+" if v > 0 else ""}{v}</span>'
            for a, v in effects.items() if v and v != 0
        )
        opts_html += (
            f'<div class="opt-block">'
            f'<div class="opt-header"><span class="opt-badge" style="background:{col}">{opt_key}</span>'
            f'<span class="opt-text">{t_html}</span></div>'
            f'{cons_sec}'
            f'<div class="eff-row">{eff_tags if eff_tags else "<span class=no-eff>无属性变化</span>"}</div>'
            f'</div>'
        )

    if audio_url:
        audio_html = (f'<div class="meta-row">🔊 <a href="{_esc(audio_url)}" target="_blank" '
                      f'class="audio-link">播放 / 下载音频</a></div>')
    else:
        audio_html = '<div class="meta-row" style="color:rgba(255,255,255,.55);font-size:12px">🔇 暂无音频</div>'

    css = """*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px;color:#222;background:#f8f9fa;padding:14px;line-height:1.7}
.card-meta{background:linear-gradient(135deg,#1565C0,#B8860B);color:white;border-radius:10px;padding:10px 14px;margin-bottom:12px}
.meta-row{margin:3px 0;font-size:12px}
.badge{background:rgba(255,255,255,0.25);border-radius:4px;padding:2px 10px;font-size:12px;font-weight:600;margin-right:6px}
.audio-link{color:#FFD54F;text-decoration:none;font-size:12px}.audio-link:hover{text-decoration:underline}
.section-label{font-weight:600;color:#555;font-size:11px;text-transform:uppercase;letter-spacing:.8px;margin:14px 0 6px}
.event-text{background:white;border:1px solid #e8e8e8;border-radius:8px;padding:12px 14px;line-height:1.8;color:#333;user-select:text;-webkit-user-select:text;}
.opt-block{background:white;border:1px solid #e8e8e8;border-radius:8px;padding:12px;margin:8px 0;user-select:text;-webkit-user-select:text;}
.opt-header{display:flex;align-items:flex-start;gap:10px;margin-bottom:6px}
.opt-badge{color:white;font-weight:700;border-radius:50%;width:22px;height:22px;display:inline-flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;margin-top:2px}
.opt-text{flex:1;line-height:1.7;user-select:text;-webkit-user-select:text;}
.cons{background:#F8F9FA;border-left:3px solid #90CAF9;border-radius:0 6px 6px 0;padding:8px 10px;margin:6px 0;font-size:13px;color:#444;user-select:text;-webkit-user-select:text;}
.eff-row{margin-top:8px;display:flex;flex-wrap:wrap;gap:4px}
.eff{border-radius:12px;padding:2px 10px;font-size:12px;display:inline-block}
.eff.pos{background:rgba(76,175,80,0.12);border:1px solid #4CAF50;color:#388E3C}
.eff.neg{background:rgba(244,67,54,0.10);border:1px solid #f44336;color:#D32F2F}
.no-eff{color:#999;font-size:12px}
mark.ann-hl{background:#FFF176;border-bottom:2px solid #F9A825;border-radius:2px;padding:0 1px;cursor:pointer}
mark.ann-done{background:#E8F5E9;border-bottom:2px solid #66BB6A;border-radius:2px;padding:0 1px;cursor:pointer;text-decoration:line-through;opacity:.7}
#hl-popup{position:fixed;display:none;background:white;border:1px solid #e0e0e0;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,.18);padding:12px 14px;z-index:2000;min-width:220px;max-width:320px}
#hl-popup-body{font-size:13px;color:#333;margin-bottom:10px;line-height:1.6;border-left:3px solid #F9A825;padding-left:8px}
.hl-btns{display:flex;gap:6px;flex-wrap:wrap}
.hl-btn{border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:12px;font-weight:500}
.hl-btn-edit{background:#E3F2FD;color:#1565C0}.hl-btn-done{background:#E8F5E9;color:#2E7D32}.hl-btn-del{background:#FFEBEE;color:#C62828}
.hl-btn:hover{filter:brightness(.93)}
#hl-edit-row{display:none;margin-top:8px}
#hl-edit-input{width:100%;border:1px solid #e0e0e0;border-radius:6px;padding:6px 8px;font-size:13px;font-family:inherit}
#hl-edit-save{margin-top:6px;background:#1a237e;color:white;border:none;border-radius:6px;padding:6px 14px;cursor:pointer;font-size:12px;font-weight:500}"""

    js = f"""var CARD_ID={{card_id}},TOKEN='{{token}}',BACKEND='{{backend_url}}',_curNid=null,_popTimer=null;
var popup=document.getElementById('hl-popup');
function _showPopup(el,e){{_curNid=el.getAttribute('data-nid');var content=el.getAttribute('data-content')||'';var completed=el.getAttribute('data-completed')==='true';document.getElementById('hl-popup-body').textContent=content;document.getElementById('hl-edit-row').style.display='none';document.getElementById('hl-edit-input').value=content;var db=document.getElementById('hl-btn-done');db.textContent=completed?'✓ 已完成':'✅ 标记完成';db.style.display=completed?'none':'inline-block';popup.style.display='block';var px=Math.min(e.clientX+10,window.innerWidth-340);var py=e.clientY-popup.offsetHeight-10;if(py<10)py=e.clientY+20;popup.style.left=px+'px';popup.style.top=py+'px';}}
function _hidePopup(){{popup.style.display='none';_curNid=null;}}
document.querySelectorAll('mark.ann-hl,mark.ann-done').forEach(function(m){{m.addEventListener('mouseenter',function(e){{clearTimeout(_popTimer);_showPopup(this,e);}});m.addEventListener('mouseleave',function(){{_popTimer=setTimeout(function(){{_hidePopup();}},300);}});}});
popup.addEventListener('mouseenter',function(){{clearTimeout(_popTimer);}});popup.addEventListener('mouseleave',function(){{_popTimer=setTimeout(_hidePopup,300);}});
document.getElementById('hl-btn-edit').addEventListener('click',function(){{document.getElementById('hl-edit-row').style.display='block';document.getElementById('hl-edit-input').focus();}});
document.getElementById('hl-edit-save').addEventListener('click',function(){{var nc=document.getElementById('hl-edit-input').value.trim();if(!nc||!_curNid)return;this.disabled=true;fetch(BACKEND+'/api/admin/cards/'+CARD_ID+'/notes/'+_curNid,{{method:'PUT',headers:{{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN}},body:JSON.stringify({{content:nc}})}}).then(function(r){{return r.json();}}).then(function(d){{if(d.ok){{var btns=window.parent.document.querySelectorAll('button');for(var i=0;i<btns.length;i++){{if(btns[i].innerText.includes('刷新批注数据')){{btns[i].click();return;}}}}}}else alert('保存失败: '+(d.error||''));}});}});
document.getElementById('hl-btn-done').addEventListener('click',function(){{if(!_curNid)return;this.disabled=true;fetch(BACKEND+'/api/admin/cards/'+CARD_ID+'/notes/'+_curNid,{{method:'PUT',headers:{{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN}},body:JSON.stringify({{completed:true}})}}).then(function(r){{return r.json();}}).then(function(d){{if(d.ok){{var btns=window.parent.document.querySelectorAll('button');for(var i=0;i<btns.length;i++){{if(btns[i].innerText.includes('刷新批注数据')){{btns[i].click();return;}}}}}}else alert('操作失败: '+(d.error||''));}});}});
document.getElementById('hl-btn-del').addEventListener('click',function(){{if(!_curNid)return;if(!confirm('确认删除该批注？'))return;this.disabled=true;fetch(BACKEND+'/api/admin/cards/'+CARD_ID+'/notes/'+_curNid,{{method:'DELETE',headers:{{'Authorization':'Bearer '+TOKEN}}}}).then(function(r){{return r.json();}}).then(function(d){{if(d.ok){{var btns=window.parent.document.querySelectorAll('button');for(var i=0;i<btns.length;i++){{if(btns[i].innerText.includes('刷新批注数据')){{btns[i].click();return;}}}}}}else alert('删除失败: '+(d.error||''));}});}});"""

    return (
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head><body>'
        f'<div class="card-meta">'
        f'<div><span class="badge">{safety}</span><span class="badge">{phase}</span>'
        f'<span style="font-size:12px;opacity:.85">ID #{card_id}</span></div>'
        f'{audio_html}'
        f'</div>'
        f'<div class="section-label">📖 事件描述</div>'
        f'<div class="event-text">{event_html}</div>'
        f'<div class="section-label">🎯 选项与后果</div>'
        f'{opts_html}'
        f'<div id="hl-popup">'
        f'<div id="hl-popup-body"></div>'
        f'<div class="hl-btns">'
        f'<button class="hl-btn hl-btn-edit" id="hl-btn-edit">✏️ 编辑</button>'
        f'<button class="hl-btn hl-btn-done" id="hl-btn-done">✅ 标记完成</button>'
        f'<button class="hl-btn hl-btn-del" id="hl-btn-del">🗑️ 删除</button>'
        f'</div>'
        f'<div id="hl-edit-row">'
        f'<input id="hl-edit-input" type="text">'
        f'<button id="hl-edit-save">保存</button>'
        f'</div>'
        f'</div>'
        f'<script>{js}</script></body></html>'
    )


@st.dialog("🎴 卡牌详情", width="large")
def _card_full_dialog(card_id, headers):
    """4-Tab: 卡牌详情 / 卡牌编辑 / 批注历史 / 版本历史"""
    try:
        res = requests.get(f"{BACKEND_URL}/api/admin/cards", params={}, headers=headers)
        card_list = res.json().get('cards', []) if res.ok else []
        card = next((c for c in card_list if c['id'] == card_id), None)
    except Exception as e:
        st.error(str(e)); return
    if not card:
        st.error(f"未找到卡牌 #{card_id}"); return

    try:
        nr = requests.get(f"{BACKEND_URL}/api/admin/cards/{card_id}/notes", headers=headers)
        notes = nr.json().get('notes', []) if nr.ok else []
    except Exception:
        notes = []

    branch = card.get('branch', 'release')
    _ver_label = card.get('versionLabel') or card.get('version_label') or f"v{card.get('version', 1)}"
    st.markdown(
        f"**ID #{card_id}** · {'🟢 发布版' if branch == 'release' else '🔵 测试版'} "
        f"`{_ver_label}` · `{card.get('status')}`"
    )

    # ── 草稿检测（在渲染 tabs 前，以便动态修改标签名）──
    _edit_safety_opts = ['身体安全', '心理安全', '社交安全', '经济安全', '数字权益']
    _edit_attrs = ['安全力', '脑波力', '实感力', '创心力', '沟通力']
    _edit_opts_orig = card.get('options', {})
    _all_edit_keys = (
        [f"e_event_{card_id}", f"e_safety_{card_id}", f"e_phase_{card_id}"]
        + [f"e2_{ok}_{sfx}_{card_id}" for ok in ['A','B','C'] for sfx in ['t','c']]
        + [f"e2_{ok}_{a}_{card_id}" for ok in ['A','B','C'] for a in _edit_attrs]
    )
    _has_draft = (
        st.session_state.get(f"e_event_{card_id}") not in (None, card.get('event', ''))
        or any(
            st.session_state.get(f"e2_{ok}_t_{card_id}") not in (None, _edit_opts_orig.get(ok, {}).get('text', ''))
            for ok in ['A', 'B', 'C']
        )
    )
    _edit_tab_label = "✏️ 卡牌编辑 🔴" if _has_draft else "✏️ 卡牌编辑"
    tab1, tab2, tab3, tab4 = st.tabs(["📄 卡牌详情", _edit_tab_label, "📝 备注", "📜 版本历史"])

    # ── Tab 1: 详情 ──
    with tab1:
        import streamlit.components.v1 as stc
        stc.html(
            _build_card_view_html(
                card, notes,
                token=st.session_state.get('token', ''),
                backend_url=BACKEND_URL
            ),
            height=500, scrolling=True
        )
        st.divider()
        st.markdown("##### 📝 添加备注")
        with st.form(key=f"add_note_form_{card_id}", clear_on_submit=True):
            note_text = st.text_area("备注内容", height=80, placeholder="写下您对这张卡牌的备注...")
            submit_note = st.form_submit_button("✅ 提交备注", use_container_width=True)
            if submit_note:
                if not note_text.strip():
                    st.error("备注内容不能为空！")
                else:
                    res = requests.post(
                        f"{BACKEND_URL}/api/admin/cards/{card_id}/notes",
                        json={"content": note_text.strip()},
                        headers=headers
                    )
                    if res.ok:
                        st.success("备注添加成功！"); time.sleep(0.5); st.rerun()
                    else:
                        st.error(f"提交失败：{res.json().get('error', '未知错误')}")
        st.divider()
        a1, a2, a3, a4 = st.columns(4)
        status = card.get('status')
        branch = card.get('branch', 'release')

        # 增加测试卡牌单发上线选项
        if branch == 'draft' and a3.button("🚀 测试版单发部署", use_container_width=True, type="primary", key=f"dlg_deploy_{card_id}"):
            try:
                # 给单卡专门部署，也就是传给自己后端的 bulk-publish 接口使用通用秘钥发布
                from db_utils import get_system_setting
                pw = get_system_setting("DEV_KEY", "sj0127wqt")
                res = requests.post(f"{BACKEND_URL}/api/admin/cards/bulk-publish", json={"cardIds": [card_id], "secretKey": pw}, headers=headers)
                if res.ok:
                    st.success("已成功从测试版部署为正式版上线"); time.sleep(0.5); st.rerun()
                else:
                    st.error(res.text)
            except Exception as e:
                st.error(f"部署失败: {e}")

        if status == 'pending' and a4.button("✅ 审核上线", use_container_width=True, key=f"dlg_approve_{card_id}"):
            res = requests.put(f"{BACKEND_URL}/api/cards/{card_id}", json={"status": "active"}, headers=headers)
            if res.ok:
                st.success("已上线"); time.sleep(0.3); st.rerun()
        if status == 'active' and a4.button("🔴 下架", use_container_width=True, key=f"dlg_delist_{card_id}"):
            res = requests.delete(f"{BACKEND_URL}/api/cards/{card_id}", headers=headers)
            if res.ok:
                st.success("已下架"); time.sleep(0.3); st.rerun()

    # ── Tab 2: 编辑 ──
    with tab2:
        safety_opts = _edit_safety_opts
        phase_opts = ['启蒙期', '成长期', '青春期']
        attrs = _edit_attrs
        options = card.get('options', {})

        # 草稿状态提示
        if _has_draft:
            _bc1, _bc2 = st.columns([5, 1])
            _bc1.info("📝 有未提交草稿，意外关闭后自动保留，重新打开可继续编辑。")
            if _bc2.button("🗑️ 清除草稿", key=f"clr_draft_{card_id}", help="丢弃草稿，恢复为上次保存的内容"):
                for _k in _all_edit_keys:
                    st.session_state.pop(_k, None)
                st.rerun()
        else:
            st.caption("💡 草稿自动保留：意外点出对话框后，重新打开仍可继续编辑。")
        e_safety = st.selectbox("安全类型", safety_opts,
            index=safety_opts.index(card['safetyType']) if card.get('safetyType') in safety_opts else 0,
            key=f"e_safety_{card_id}")
        e_phase = st.selectbox("年龄阶段", phase_opts,
            index=phase_opts.index(card['phase']) if card.get('phase') in phase_opts else 0,
            key=f"e_phase_{card_id}")
        e_event = st.text_area("📖 事件描述", value=card.get('event', ''), height=130, key=f"e_event_{card_id}")
        st.markdown("---")
        new_options = {}
        opt_icons = {'A': '🔵', 'B': '🟣', 'C': '🟠'}
        for opt_key in ['A', 'B', 'C']:
            opt = options.get(opt_key, {})
            with st.expander(f"{opt_icons[opt_key]} 选项 {opt_key}", expanded=True):
                text_val = st.text_area("选项文字", value=opt.get('text', ''), height=80,
                                        key=f"e2_{opt_key}_t_{card_id}")
                cons_val = st.text_area("选项后果", value=opt.get('consequence', ''), height=80,
                                        key=f"e2_{opt_key}_c_{card_id}")
                st.markdown("**属性效果**（正数加分，负数减分）")
                effects = opt.get('attributeEffects', {a: 0 for a in attrs})
                eff_cols = st.columns(5)
                new_effects = {}
                for i, attr in enumerate(attrs):
                    new_effects[attr] = eff_cols[i].number_input(
                        attr, value=int(effects.get(attr, 0)),
                        min_value=-5, max_value=5, step=1,
                        key=f"e2_{opt_key}_{attr}_{card_id}")
                new_options[opt_key] = {'text': text_val, 'consequence': cons_val, 'attributeEffects': new_effects}
        st.divider()
        e_version_desc = st.text_input(
            "📌 版本说明（可选）",
            placeholder="例：修改了A选项表述，调整B选项属性效果",
            key=f"e_ver_desc_{card_id}",
            help="提交后将显示在版本历史中，便于追溯"
        )
        _submitter = st.session_state.get('username') or '未知'
        st.caption(f"提交人：**{_submitter}**（将自动记录到版本历史）")
        if st.button("💾 保存草稿版本", use_container_width=True, type="primary", key=f"e_save_{card_id}"):
            if not e_event.strip():
                st.error("事件描述不能为空")
            else:
                try:
                    if card.get('branch') == 'release':
                        requests.post(f"{BACKEND_URL}/api/admin/cards/{card_id}/branch", headers=headers)
                    updated = {
                        "safetyType": e_safety, "phase": e_phase, "event": e_event,
                        "options": new_options,
                        "versionDesc": e_version_desc.strip() or None,
                    }
                    res = requests.put(f"{BACKEND_URL}/api/cards/{card_id}", json=updated, headers=headers)
                    if res.ok:
                        for _k in _all_edit_keys + [f"e_ver_desc_{card_id}"]:
                            st.session_state.pop(_k, None)
                        st.success("✅ 保存成功！已更新至测试版")
                        time.sleep(0.5); st.rerun()
                    else:
                        st.error(f"保存失败: {res.text}")
                except Exception as e:
                    st.error(str(e))

    # ── Tab 3: 备注 ──
    with tab3:
        if not notes:
            st.info("暂无备注")
        else:
            for n in reversed(notes):
                ts = format_ts(n.get('created_at'))
                content = html_lib.escape(n.get('content', ''))
                author_display = n.get('author_name') or f"uid:{n.get('author', '?')}"
                st.markdown(f"**{ts}** · 👤 {author_display} — {content}")
                st.divider()

    # ── Tab 4: 版本历史 ──
    with tab4:
        try:
            res = requests.get(f"{BACKEND_URL}/api/admin/cards/{card_id}/versions", headers=headers)
            versions = res.json().get('versions', []) if res.ok else []
            if versions:
                for v in versions:
                    icon = '🟢' if v.get('branch') == 'release' else '🔵'
                    label = v.get('version_label') or f"v{v.get('version', '?')}"
                    update_time = format_ts(v.get('updated_at')) if v.get('updated_at') else "未知时间"
                    with st.expander(f"{icon} {label}  [{v.get('status', '未知')}]  {update_time}"):
                        st.caption(str(v.get('event', ''))[:300])
                        if str(v.get('id')) != str(card_id):
                            st.markdown("---")
                            c1, c2 = st.columns([1, 4])
                            if c1.button("🚀 设为当前显示版本", key=f"rec_v_{v['id']}_{card_id}"):
                                try:
                                    # 后端已经在 /versions 接口返回了包含了完整 options 的数据对象
                                    target_draft = v
                                    
                                    # 构建要覆盖的数据结构，提取所需字段
                                    updated = {
                                        "safetyType": target_draft.get('safetyType') or target_draft.get('safety_type'),
                                        "phase": target_draft.get('phase'),
                                        "event": target_draft.get('event'),
                                        "options": target_draft.get('options')
                                    }
                                    
                                    # 发送 PUT 请求强制覆盖当前显示的活动卡片
                                    put_res = requests.put(f"{BACKEND_URL}/api/cards/{card_id}", json=updated, headers=headers)
                                    if put_res.ok:
                                        st.success(f"✅ 已成功将当前版本内容重置为历史版本: {label}")
                                        # 使用 query param 重载详情框
                                        st.query_params['card_dialog'] = str(card_id)
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.error(f"覆盖失败: {put_res.text}")
                                except Exception as e:
                                    st.error(f"操作异常: {str(e)}")
            else:
                st.info("暂无版本历史")
        except Exception as e:
            st.error(str(e))


def card_management_page():
    st.header("🎴 卡牌管理")
    if not st.session_state.get('token'):
        st.error("⚠️ 未检测到后端 API 令牌，请尝试重新登录。")
        return

    headers = {"Authorization": f"Bearer {st.session_state.token}"}

    # 处理批注后重定向回弹窗
    if hasattr(st, "query_params") and 'card_dialog' in st.query_params:
        cid = st.query_params['card_dialog']
        if cid and cid.isdigit():
            st.session_state._open_card_dialog = int(cid)
        # 清除查询参数，以免刷新时重新触发
        st.query_params.clear()

    # ── 顶部筛选栏 ──
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 2, 1, 1])
    with fc1:
        online_filter = st.selectbox("是否上线", ['全部', '已上线', '未上线'], key="card_online_f")
    with fc2:
        phase_filter = st.selectbox("阶段", ['全部', '启蒙期', '成长期', '青春期'], key="card_phase_f")
    with fc3:
        safety_opts = ['全部', '身体安全', '心理安全', '社交安全', '经济安全', '数字权益']
        safety_filter = st.selectbox("安全类型", safety_opts, key="card_safety_f")
    with fc4:
        sort_order = st.selectbox("ID 排序", ['↓ 最新', '↑ 最旧'], key="card_sort_f")
    with fc5:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("➕ 新建", use_container_width=True, key="btn_new_card"):
            st.session_state.card_edit_mode = 'new'
            st.session_state.selected_card_id = None

    # ── 获取卡牌 ──
    try:
        res = requests.get(f"{BACKEND_URL}/api/admin/cards", params={}, headers=headers)
        all_cards = res.json().get('cards', []) if res.ok else []
    except Exception as e:
        st.error(f"获取卡牌失败: {e}"); return

    if online_filter == '已上线':
        all_cards = [c for c in all_cards if c.get('status') == 'active']
    elif online_filter == '未上线':
        all_cards = [c for c in all_cards if c.get('status') != 'active']
    if phase_filter != '全部':
        all_cards = [c for c in all_cards if c.get('phase') == phase_filter]
    if safety_filter != '全部':
        all_cards = [c for c in all_cards if c.get('safetyType') == safety_filter]
    all_cards.sort(key=lambda c: c.get('id', 0), reverse=(sort_order == '↓ 最新'))

    st.caption(f"共找到 {len(all_cards)} 张卡牌")
    st.divider()

    # ── 触发 Dialog ──
    if st.session_state.get('_open_card_dialog'):
        cid = st.session_state.pop('_open_card_dialog')
        _card_full_dialog(cid, headers)

    # ── 新建表单 ──
    if st.session_state.get('card_edit_mode') == 'new':
        with st.expander("➕ 新建卡牌", expanded=True):
            attrs = ['安全力', '脑波力', '实感力', '创心力', '沟通力']
            with st.form("new_card_form"):
                n_safety = st.selectbox("安全类型", ['身体安全', '心理安全', '社交安全', '经济安全', '数字权益'])
                n_phase = st.selectbox("阶段", ['启蒙期', '成长期', '青春期'])
                n_event = st.text_area("📖 事件描述", height=120)
                new_opts = {}
                opt_icons = {'A': '🔵', 'B': '🟣', 'C': '🟠'}
                for opt_key in ['A', 'B', 'C']:
                    st.markdown(f"**{opt_icons[opt_key]} 选项 {opt_key}**")
                    t = st.text_area("选项文字", height=70, key=f"n_{opt_key}_t")
                    c = st.text_area("选项后果", height=70, key=f"n_{opt_key}_c")
                    eff_cols = st.columns(5)
                    effs = {}
                    for j, attr in enumerate(attrs):
                        effs[attr] = eff_cols[j].number_input(
                            attr, value=0, min_value=-5, max_value=5, step=1,
                            key=f"n_{opt_key}_{attr}")
                    new_opts[opt_key] = {'text': t, 'consequence': c, 'attributeEffects': effs}
                submitted = st.form_submit_button("💾 提交审核", use_container_width=True)
                if submitted and n_event:
                    try:
                        resp = requests.post(f"{BACKEND_URL}/api/cards",
                            json={"safetyType": n_safety, "phase": n_phase,
                                  "event": n_event, "options": new_opts},
                            headers=headers)
                        if resp.ok:
                            st.success(f"✅ 卡牌已创建！ID: {resp.json().get('id')}")
                            st.session_state.card_edit_mode = 'view'
                            time.sleep(0.5); st.rerun()
                        else:
                            st.error(resp.text)
                    except Exception as e:
                        st.error(str(e))

                    except Exception as e:
                        st.error(str(e))

    # ── 批量上线操作面板 ──
    if all_cards:
        with st.expander("🚀 批量发布卡牌预发布", expanded=False):
            st.info("💡 选中下方列表中的卡牌，在此处输入管理员密钥后统一发布。发布后，卡牌版本会自动更新为正式版（如 v2版）。")
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                secret_key = st.text_input("管理员密钥", type="password", key="bulk_secret")
            with c2:
                # 统计已勾选的卡牌数量
                selected_ids = [c['id'] for c in all_cards if st.session_state.get(f"chk_{c['id']}")]
                st.write(f"当前已勾选 **{len(selected_ids)}** 张卡牌待发布")
            with c3:
                st.markdown("&nbsp;", unsafe_allow_html=True)
                if st.button("🌟 确认批量上线", use_container_width=True, type="primary"):
                    if not secret_key:
                        st.error("请输入管理员密钥！")
                    elif not selected_ids:
                        st.warning("请至少在下方勾选一张卡牌！")
                    else:
                        try:
                            payload = {"cardIds": selected_ids, "secretKey": secret_key}
                            resp = requests.post(f"{BACKEND_URL}/api/admin/cards/bulk-publish", json=payload, headers=headers)
                            if resp.ok:
                                res_data = resp.json().get('results', [])
                                st.success(f"✅ 成功发布 {len(res_data)} 张卡牌！")
                                # 重置勾选状态
                                for cid in selected_ids:
                                    st.session_state[f"chk_{cid}"] = False
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"发布失败: {resp.json().get('error', resp.text)}")
                        except Exception as e:
                            st.error(str(e))

    # ── 全宽卡牌网格 ──
    if not all_cards:
        st.info("没有符合条件的卡牌")
    else:
        for row_start in range(0, len(all_cards), 3):
            row_cards = all_cards[row_start:row_start + 3]
            cols = st.columns(3)
            for i, card in enumerate(row_cards):
                with cols[i]:
                    cid = card['id']
                    
                    st.markdown(_render_card_visual(card, False), unsafe_allow_html=True)
                    
                    # 增加一行横向布局，放 [批量选择框] 和 [查看按钮]
                    bc1, bc2 = st.columns([1, 4])
                    with bc1:
                        # 用 key 绑定 session_state 进行多选管理
                        st.checkbox("选", key=f"chk_{cid}")
                    with bc2:
                        if st.button(f"🔍 查看预修改", key=f"view_{cid}_{row_start}", use_container_width=True):
                            st.session_state._open_card_dialog = cid
                            st.rerun()

    # ── AI 生成器 ──
    st.divider()
    with st.expander("✨ AI 卡牌生成器"):
        with st.form("generate_card_form"):
            topic = st.text_input("主题", placeholder="例如：校园霸凌，高年级抢低年级零花钱")
            content = st.text_area("详细描述（可选）", placeholder="补充更多细节...", height=80)
            submitted = st.form_submit_button("开始生成", use_container_width=True)
        if submitted:
            if not topic and not content:
                st.warning("请输入主题或内容")
            else:
                with st.spinner("AI 正在创作中... (10-20 秒)"):
                    try:
                        resp = requests.post(f"{BACKEND_URL}/api/admin/generate-card",
                            json={"topic": topic, "content": content}, headers=headers)
                        if resp.ok:
                            st.session_state.generated_card = resp.json().get("card")
                            st.success("生成成功！请在下方预览并提交。")
                        else:
                            st.error(f"生成失败: {resp.status_code} - {resp.text}")
                    except Exception as e:
                        st.error(str(e))
        if st.session_state.get("generated_card"):
            card_json = st.text_area("JSON Editor",
                value=json.dumps(st.session_state.generated_card, indent=2, ensure_ascii=False), height=300)
            if st.button("💾 提交审核"):
                try:
                    card_data = json.loads(card_json)
                    resp = requests.post(f"{BACKEND_URL}/api/cards", json=card_data, headers=headers)
                    if resp.ok:
                        st.success(f"✅ 卡牌 #{resp.json().get('id')} 已提交审核")
                        del st.session_state.generated_card
                        time.sleep(0.5); st.rerun()
                    else:
                        st.error(f"保存失败: {resp.text}")
                except json.JSONDecodeError:
                    st.error("JSON 格式错误")


def activity_management_page():
    st.header("📅 活动管理")
    if not st.session_state.get('token'):
        st.error("⚠️ 未检测到后端 API 令牌"); return
    headers = {"Authorization": f"Bearer {st.session_state.token}"}

    tab_list, tab_create = st.tabs(["📋 活动列表", "➕ 创建活动"])

    with tab_list:
        try:
            res = requests.get(f"{BACKEND_URL}/api/admin/activities", headers=headers)
            activities = res.json().get('activities', []) if res.ok else []
        except Exception as e:
            st.error(str(e)); activities = []

        if not activities:
            st.info("暂无活动，请先创建活动")
        else:
            for act in activities:
                status_icon = '🟢' if act['status'] == 'active' else '🗄️'
                title = f"{status_icon} {act['name']}  [{act.get('activity_code','')}]  桌数:{act.get('table_count',0)}  人数:{act.get('participant_count',0)}  均分:{act.get('avg_score') or '-'}"
                with st.expander(title):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.markdown(f"**主办方**: {act.get('organizer') or '未设置'}")
                        if act.get('started_at'):
                            st.markdown(f"**开始时间**: {format_ts(act['started_at'])}")
                        if act.get('ended_at'):
                            st.markdown(f"**结束时间**: {format_ts(act['ended_at'])}")
                        st.markdown(f"**活动码**: `{act.get('activity_code','')}`  *(玩家凭此加入)*")
                    with c2:
                        if act['status'] == 'active':
                            if st.button("🗄️ 归档", key=f"arch_{act['id']}"):
                                requests.put(f"{BACKEND_URL}/api/admin/activities/{act['id']}",
                                    json={"status": "archived"}, headers=headers)
                                clear_cache(); st.rerun()
                        else:
                            if st.button("🔄 重新激活", key=f"react_{act['id']}"):
                                requests.put(f"{BACKEND_URL}/api/admin/activities/{act['id']}",
                                    json={"status": "active"}, headers=headers)
                                clear_cache(); st.rerun()

                    # ---- 内联编辑表单 ----
                    edit_key = f"edit_act_{act['id']}"
                    if edit_key not in st.session_state:
                        st.session_state[edit_key] = False
                    if st.button("✏️ 编辑活动信息", key=f"edit_btn_{act['id']}"):
                        st.session_state[edit_key] = not st.session_state[edit_key]
                        st.rerun()
                    if st.session_state.get(edit_key):
                        with st.form(key=f"edit_form_{act['id']}"):
                            new_name = st.text_input("活动名称", value=act.get('name') or '', key=f"fn_{act['id']}")
                            new_org = st.text_input("主办方", value=act.get('organizer') or '', key=f"fo_{act['id']}")
                            if st.form_submit_button("💾 保存修改", use_container_width=True):
                                if new_name.strip():
                                    r = requests.put(
                                        f"{BACKEND_URL}/api/admin/activities/{act['id']}",
                                        json={"name": new_name.strip(), "organizer": new_org.strip() or None},
                                        headers=headers
                                    )
                                    if r.ok:
                                        st.success("✅ 已更新")
                                        st.session_state[edit_key] = False
                                        clear_cache(); time.sleep(0.5); st.rerun()
                                    else:
                                        st.error(f"更新失败: {r.text}")
                                else:
                                    st.warning("活动名称不能为空")

                    # 该活动的桌（session）列表
                    st.divider()
                    try:
                        s_res = requests.get(f"{BACKEND_URL}/api/admin/activities/{act['id']}/sessions", headers=headers)
                        sessions = s_res.json().get('sessions', []) if s_res.ok else []
                        if sessions:
                            st.markdown("**游戏桌记录**:")
                            sdf = pd.DataFrame(sessions)
                            sdf['时间'] = sdf['started_at'].apply(lambda x: format_ts(x) if x else '--')
                            # 修复：得分为 0 时也应正常显示 0，而非 '--'
                            sdf['得分'] = sdf['final_score'].apply(lambda x: str(int(x)) if pd.notna(x) and x is not None else '--')
                            st.dataframe(
                                sdf[['table_no', '时间', 'guardian_name', '得分', 'game_mode']].rename(
                                    columns={'table_no':'桌号', 'guardian_name':'守望师', 'game_mode':'模式'}
                                ), use_container_width=True, hide_index=True
                            )
                        else:
                            st.caption("暂无游戏桌记录")
                    except Exception as e:
                        st.warning(str(e))

    with tab_create:
        with st.form("create_activity_form"):
            name = st.text_input("活动名称 *", placeholder="例如：2025年春季安全培训")
            organizer = st.text_input("主办方", placeholder="例如：上海某小学")
            col_s, col_e = st.columns(2)
            with col_s:
                start_date = st.date_input("开始日期（可选）", value=None)
            with col_e:
                end_date = st.date_input("结束日期（可选）", value=None)
            submitted = st.form_submit_button("🎉 创建活动", use_container_width=True)
            if submitted and name:
                import calendar
                payload = {
                    "name": name, "organizer": organizer or None,
                    "started_at": int(datetime.datetime.combine(start_date, datetime.time()).timestamp() * 1000) if start_date else None,
                    "ended_at": int(datetime.datetime.combine(end_date, datetime.time()).timestamp() * 1000) if end_date else None,
                }
                try:
                    res = requests.post(f"{BACKEND_URL}/api/admin/activities", json=payload, headers=headers)
                    if res.ok:
                        data = res.json()
                        st.success(f"✅ 活动已创建！活动码：**{data.get('activity_code')}**")
                        clear_cache(); time.sleep(1); st.rerun()
                    else:
                        st.error(res.text)
                except Exception as e:
                    st.error(str(e))


def oss_management_page():
    st.header("📂 OSS 文件管理")

    if not st.session_state.get('token'):
        st.error("⚠️ 未检测到后端 API 令牌，请尝试重新登录。")
        return

    headers = {"Authorization": f"Bearer {st.session_state.token}"}

    # 视图切换
    view_mode = st.radio("视图模式", ["📁 目录视图", "📅 活动视图", "👤 角色视图"], horizontal=True)
    st.divider()

    # 删除确认
    if 'oss_delete_target' not in st.session_state:
        st.session_state.oss_delete_target = None
    if st.session_state.oss_delete_target:
        target = st.session_state.oss_delete_target
        st.warning(f"⚠️ 确认删除文件：**{target}**  此操作不可恢复！")
        d1, d2 = st.columns(2)
        if d1.button("✅ 确认删除", type="primary", use_container_width=True):
            try:
                del_res = requests.delete(f"{BACKEND_URL}/api/admin/oss/files", json={"filename": target}, headers=headers)
                if del_res.ok:
                    st.success(f"已删除: {target}")
                    st.session_state.oss_delete_target = None
                    time.sleep(1); st.rerun()
                else:
                    st.error(f"删除失败: {del_res.text}")
            except Exception as e:
                st.error(str(e))
        if d2.button("❌ 取消", use_container_width=True):
            st.session_state.oss_delete_target = None; st.rerun()
        st.divider()

    def fmt_oss_time(t):
        try:
            dt = datetime.datetime.fromisoformat(t.replace('Z', '+00:00')).astimezone(BEIJING_TZ)
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return str(t)[:16]

    def render_file_row(f, prefix=""):
        name = f['name'][len(prefix):] if prefix and f['name'].startswith(prefix) else f['name']
        c1, c2, c3, c4 = st.columns([4, 1, 2, 1])
        c1.markdown(f"[{name or f['name']}]({f['url']})")
        c2.write(f"{f['size']/1024:.1f} KB")
        c3.write(fmt_oss_time(f['lastModified']))
        if c4.button("🗑️", key=f"del_{f['name']}", help="删除"):
            st.session_state.oss_delete_target = f['name']; st.rerun()

    # ── 目录视图 ──
    if "目录" in view_mode:
        if 'oss_current_path' not in st.session_state:
            st.session_state.oss_current_path = ""
        current_path = st.session_state.oss_current_path

        nav1, nav2 = st.columns([4, 1])
        with nav1:
            st.markdown(f"### 🏠 {'根目录' if not current_path else '/' + current_path}")
            if current_path and st.button("⬅️ 返回上级"):
                parts = current_path.strip("/").split("/")
                st.session_state.oss_current_path = "/".join(parts[:-1]) + "/" if len(parts) > 1 else ""
                st.rerun()
        nav2.button("🔄 刷新", on_click=st.rerun)

        try:
            res = requests.get(f"{BACKEND_URL}/api/admin/oss/files",
                params={"maxKeys": 200, "delimiter": "/", "prefix": current_path}, headers=headers)
            if res.ok:
                data = res.json()
                folders = data.get('folders', [])
                files = [f for f in data.get('files', []) if f['name'] != current_path]

                if folders:
                    st.subheader("📁 文件夹")
                    for fp in folders:
                        dname = fp[len(current_path):] if current_path else fp
                        c1, c2 = st.columns([5, 1])
                        c1.markdown(f"**📂 {dname}**")
                        if c2.button("进入", key=f"cd_{fp}"):
                            st.session_state.oss_current_path = fp; st.rerun()
                    st.divider()

                if files:
                    st.subheader("📄 文件")
                    h1, h2, h3, h4 = st.columns([4, 1, 2, 1])
                    h1.markdown("**文件名**"); h2.markdown("**大小**"); h3.markdown("**时间**"); h4.markdown("**操作**")
                    for f in files:
                        render_file_row(f, current_path)
                if not folders and not files:
                    st.info("此目录为空")
            else:
                st.error(f"获取失败: {res.status_code}")
        except Exception as e:
            st.error(str(e))

    # ── 活动视图 ──
    elif "活动" in view_mode:
        st.caption("按活动场次分组，关联 OSS 文件中的 session_id 前缀")
        try:
            act_res = requests.get(f"{BACKEND_URL}/api/admin/activities", headers=headers)
            activities = act_res.json().get('activities', []) if act_res.ok else []

            # 获取所有文件（不分页，尽量多）
            all_res = requests.get(f"{BACKEND_URL}/api/admin/oss/files",
                params={"maxKeys": 500, "delimiter": ""}, headers=headers)
            all_files = all_res.json().get('files', []) if all_res.ok else []

            # 获取所有 sessions 做 id→守望师 映射
            sessions_df = cached_run_query("SELECT id, user_id FROM game_sessions")
            sid_set = set(sessions_df['id'].astype(str).tolist()) if isinstance(sessions_df, pd.DataFrame) and not sessions_df.empty else set()

            for act in activities:
                # 获取该活动的 session id 列表
                s_res = requests.get(f"{BACKEND_URL}/api/admin/activities/{act['id']}/sessions", headers=headers)
                act_sessions = s_res.json().get('sessions', []) if s_res.ok else []
                act_session_ids = {str(s['id']) for s in act_sessions}

                matched = [f for f in all_files if any(f'session_{sid}' in f['name'] or f'/{sid}/' in f['name'] for sid in act_session_ids)]
                count_str = f"{len(matched)} 个文件" if matched else "暂无文件"
                with st.expander(f"📅 {act['name']} [{act.get('activity_code','')}]  ·  {count_str}"):
                    if matched:
                        h1, h2, h3, h4 = st.columns([4, 1, 2, 1])
                        h1.markdown("**文件名**"); h2.markdown("**大小**"); h3.markdown("**时间**"); h4.markdown("**操作**")
                        for f in matched:
                            render_file_row(f)
                    else:
                        st.caption("该活动暂无关联 OSS 文件")

            # 未关联活动的文件
            all_act_sids = set()
            for act in activities:
                s_res = requests.get(f"{BACKEND_URL}/api/admin/activities/{act['id']}/sessions", headers=headers)
                if s_res.ok:
                    for s in s_res.json().get('sessions', []):
                        all_act_sids.add(str(s['id']))
            unmatched = [f for f in all_files if not any(f'session_{sid}' in f['name'] for sid in all_act_sids)]
            if unmatched:
                with st.expander(f"📂 独立游戏（未关联活动）· {len(unmatched)} 个文件"):
                    for f in unmatched:
                        render_file_row(f)
        except Exception as e:
            st.error(str(e))

    # ── 角色视图 ──
    else:
        st.caption("按守望师分组显示文件")
        try:
            all_res = requests.get(f"{BACKEND_URL}/api/admin/oss/files",
                params={"maxKeys": 500, "delimiter": ""}, headers=headers)
            all_files = all_res.json().get('files', []) if all_res.ok else []

            users_df = cached_run_query("SELECT id, guardian_name, phone FROM users WHERE role IN ('watcher','user','enterprise')")
            if not isinstance(users_df, pd.DataFrame) or users_df.empty:
                st.info("暂无用户数据"); return

            for _, u in users_df.iterrows():
                uid = str(u['id'])
                name = u.get('guardian_name') or u.get('phone') or f"用户{uid}"
                matched = [f for f in all_files if f'user_{uid}' in f['name'] or f'/{uid}/' in f['name']]
                if not matched:
                    continue
                with st.expander(f"👤 {name}  ·  {len(matched)} 个文件"):
                    h1, h2, h3, h4 = st.columns([4, 1, 2, 1])
                    h1.markdown("**文件名**"); h2.markdown("**大小**"); h3.markdown("**时间**"); h4.markdown("**操作**")
                    for f in matched:
                        render_file_row(f)
        except Exception as e:
            st.error(str(e))



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
        
        # Custom Display with Grouping
        df = db_utils.run_query("SELECT key, value, description, updated_at FROM system_settings ORDER BY key ASC")
        
        # Show/Hide Secrets Toggle (Admin Only)
        show_secrets = False
        if st.session_state.user_role == 'admin':
            show_secrets = st.toggle("👁️ 显示明文 (Show Secrets)", value=False)
        
        if not df.empty:
            # Categorize
            groups = {
                "☁️ OSS / Storage": [],
                "🤖 AI / LLM": [],
                "📱 Bmob / SMS": [],
                "🛠️ Core / Other": []
            }
            
            for _, row in df.iterrows():
                k = row['key']
                if "OSS" in k or "ALI" in k:
                    groups["☁️ OSS / Storage"].append(row)
                elif "DEEPSEEK" in k or "DASH" in k or "LLM" in k:
                    groups["🤖 AI / LLM"].append(row)
                elif "BMOB" in k or "SMS" in k:
                    groups["📱 Bmob / SMS"].append(row)
                else:
                    groups["🛠️ Core / Other"].append(row)
            
            for group_name, items in groups.items():
                if items:
                    with st.expander(f"{group_name} ({len(items)})", expanded=True):
                        for item in items:
                            k = item['key']
                            v = item['value']
                            d = item['description'] or ""
                            
                            # Mask partial value if sensitive AND not showing secrets
                            display_v = v
                            is_sensitive = any(s in k.upper() for s in ["KEY", "SECRET", "PASSWORD", "TOKEN"])
                            
                            if is_sensitive and not show_secrets:
                                if v and len(v) > 8:
                                    display_v = v[:4] + "****" + v[-4:]
                                elif v:
                                    display_v = "******"

                                
                            c1, c2, c3 = st.columns([2, 3, 3])
                            c1.markdown(f"**{k}**")
                            c2.code(display_v, language="text")
                            c3.caption(d)
                            # Maybe add an inline edit button later
        else:
            st.info("当前暂无自定义参数。请尝试从环境变量导入。")
        
        # --- Import from Env ---
        with st.expander("📥 从当前环境变量导入配置 (Migration Helper)"):
            st.warning("此操作将读取服务器当前运行时的环境变量 (process.env / os.environ)，并将其存入数据库。")
            if st.button("开始扫描并导入 (Scan & Import)"):
                # Define keys we care about
                env_keys = [
                    "JWT_SECRET", "OSS_BUCKET_NAME", "OSS_REGION", "OSS_ENDPOINT",
                    "ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
                    "ALIYUN_OSS_CUSTOM_DOMAIN", "BMOB_APP_ID", "BMOB_REST_KEY",
                    "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DASHSCOPE_API_KEY"
                ]
                count = 0
                for k in env_keys:
                    val = os.getenv(k)
                    if val:
                        # Check if exists
                        if db_utils.get_system_setting(k) is None:
                            db_utils.set_system_setting(k, val, f"Imported from (env) {k}")
                            count += 1
                
                if count > 0:
                    st.success(f"已成功导入 {count} 个配置项！")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.info("未发现新的环境变量需导入，或数据库中已存在。")

        
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
        - **当前版本**: `v1.2.0`
        - **构建环境**: `Agentic Automation`
        - **服务器时区**: `Asia/Shanghai (UTC+8)`
        - **系统运行状态**: 🟢 正常 (Healthy)
        """)

        if st.session_state.user_role == 'boss':
            st.divider()
            st.subheader("🛡️ 运营权限配置")
            st.caption("为运营账号分配可访问的功能模块")

            operators_df = cached_run_query("SELECT id, guardian_name, phone, username FROM users WHERE role = 'operator'")
            if isinstance(operators_df, pd.DataFrame) and not operators_df.empty:
                perm_json_raw = db_utils.get_system_setting("operator_permissions", "{}")
                try:
                    all_perms = json.loads(perm_json_raw) if perm_json_raw else {}
                except Exception:
                    all_perms = {}

                MODULE_OPTIONS = ["user_management", "card_management", "activity_management", "oss_management", "data_audit", "game_analysis", "review_testing"]
                MODULE_LABELS = {
                    "user_management": "👤 用户管理",
                    "card_management": "🎴 卡牌管理",
                    "activity_management": "📅 活动管理",
                    "oss_management": "📂 OSS 管理",
                    "data_audit": "🧹 数据审计",
                    "game_analysis": "🎮 游戏分析",
                    "review_testing": "🔬 复盘测试",
                }

                updated_perms = {}
                for _, op in operators_df.iterrows():
                    uid_str = str(op['id'])
                    name = op.get('guardian_name') or op.get('username') or op.get('phone') or f"#{op['id']}"
                    current = all_perms.get(uid_str, [])
                    st.markdown(f"**{name}** (ID: {op['id']})")
                    selected = st.multiselect(
                        "可访问模块",
                        options=MODULE_OPTIONS,
                        default=[m for m in current if m in MODULE_OPTIONS],
                        format_func=lambda x: MODULE_LABELS.get(x, x),
                        key=f"perm_{uid_str}"
                    )
                    updated_perms[uid_str] = selected
                    st.divider()

                if st.button("💾 保存运营权限配置", type="primary"):
                    ok, err = db_utils.set_system_setting("operator_permissions", json.dumps(updated_perms, ensure_ascii=False), "各运营账号权限配置")
                    if ok:
                        st.success("✅ 权限配置已保存"); clear_cache(); time.sleep(0.5); st.rerun()
                    else:
                        st.error(f"保存失败: {err}")
            else:
                st.info("暂无运营账号。请先在用户管理中将用户角色设置为 operator。")

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
                (SELECT COUNT(*) FROM game_events ge WHERE ge.session_id = gs.id AND ge.type = 'card_choice') as card_count,
                COALESCE(gs.ended_at, (
                    SELECT MAX(e.ts) FROM game_events e
                    WHERE e.session_id = gs.id AND e.type = 'card_choice'
                )) AS effective_ended_at
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
                duration_str = _fmt_duration(row.get('started_at'), row.get('effective_ended_at'))

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
                (SELECT COUNT(*) FROM game_events ge WHERE ge.session_id = gs.id AND ge.type = 'card_choice') as card_count,
                COALESCE(gs.final_score, (
                    SELECT COALESCE(json_extract(e.payload, '$.attributesAfter.安全力'), 0)
                         + COALESCE(json_extract(e.payload, '$.attributesAfter.脑波力'), 0)
                         + COALESCE(json_extract(e.payload, '$.attributesAfter.实感力'), 0)
                         + COALESCE(json_extract(e.payload, '$.attributesAfter.创心力'), 0)
                         + COALESCE(json_extract(e.payload, '$.attributesAfter.沟通力'), 0)
                    FROM game_events e
                    WHERE e.session_id = gs.id AND e.type = 'card_choice'
                    ORDER BY e.ts DESC LIMIT 1
                )) AS effective_score,
                COALESCE(gs.ended_at, (
                    SELECT MAX(e.ts) FROM game_events e
                    WHERE e.session_id = gs.id AND e.type = 'card_choice'
                )) AS effective_ended_at
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
                # 优先用 ended_at，其次用最后一条事件的时间戳
                duration_str = _fmt_duration(row.get('started_at'), row.get('effective_ended_at'))
                status_label = {
                    'active': '🟢 有效',
                    'flagged': '🟠 待审核',
                    'trash': '🗑️ 回收站'
                }.get(row.get('status') or 'active', row.get('status') or '🟢 有效')

                # 优先用 final_score，其次用从最后一张卡牌推算的分数
                score_val = row.get('effective_score')
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
        # 根据权限构建导航项
        all_nav = ["🎛️ 驾驶舱", "👤 用户管理", "🎴 卡牌管理", "📅 活动管理",
                   "📂 OSS 文件管理", "🎮 游戏分析", "🧹 数据审计", "🔬 复盘测试", "⚙️ 系统设置"]
        module_map = {
            "👤 用户管理": "user_management",
            "🎴 卡牌管理": "card_management",
            "📅 活动管理": "activity_management",
            "📂 OSS 文件管理": "oss_management",
            "🎮 游戏分析": "game_analysis",
            "🧹 数据审计": "data_audit",
            "🔬 复盘测试": "review_testing",
            "⚙️ 系统设置": None,  # boss only
        }
        role = st.session_state.user_role
        visible_nav = []
        for item in all_nav:
            if role == 'boss':
                visible_nav.append(item)
            elif role == 'operator':
                mod = module_map.get(item)
                if mod is None:
                    continue  # system settings: boss only
                if item == "🎛️ 驾驶舱" or can_access(mod):
                    visible_nav.append(item)
        nav = st.radio("导航", visible_nav)
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
    elif "活动管理" in nav:
        activity_management_page()
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
