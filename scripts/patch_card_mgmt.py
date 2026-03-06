"""Replace card management section in admin-panel/app.py with new dialog-based implementation."""
import os

APP_PATH = os.path.join(os.path.dirname(__file__), '..', 'admin-panel', 'app.py')

NEW_SECTION = r'''def _build_card_view_html(card, annotations, token='', backend_url='http://127.0.0.1:8080'):
    """自包含卡牌详情 HTML：Word 风格批注（选中→高亮→悬浮编辑弹窗）"""
    def _esc(t): return html_lib.escape(str(t or ''))

    def _highlight(text, anns):
        if not text: return ''
        result = _esc(text)
        for ann in anns:
            sel = ann.get('selected_text', '')
            nid = str(ann.get('id', ''))
            content = ann.get('content', '')
            completed = ann.get('completed', False)
            if sel:
                esc_sel = _esc(sel)
                if esc_sel in result:
                    cls = 'ann-done' if completed else 'ann-hl'
                    data = (f'data-nid="{nid}" data-content="{_esc(content)}" '
                            f'data-sel="{esc_sel}" data-completed="{str(completed).lower()}"')
                    result = result.replace(esc_sel,
                        f'<mark class="{cls}" {data}>{esc_sel}</mark>', 1)
        return result.replace('\n', '<br>')

    card_id = card.get('id', 0)
    safety = _esc(card.get('safetyType', ''))
    phase = _esc(card.get('phase', ''))
    audio_url = card.get('audio_url') or card.get('audioUrl') or ''
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
.event-text{background:white;border:1px solid #e8e8e8;border-radius:8px;padding:12px 14px;line-height:1.8;color:#333;user-select:text}
.opt-block{background:white;border:1px solid #e8e8e8;border-radius:8px;padding:12px;margin:8px 0;user-select:text}
.opt-header{display:flex;align-items:flex-start;gap:10px;margin-bottom:6px}
.opt-badge{color:white;font-weight:700;border-radius:50%;width:22px;height:22px;display:inline-flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;margin-top:2px}
.opt-text{flex:1;line-height:1.7}
.cons{background:#F8F9FA;border-left:3px solid #90CAF9;border-radius:0 6px 6px 0;padding:8px 10px;margin:6px 0;font-size:13px;color:#444}
.eff-row{margin-top:8px;display:flex;flex-wrap:wrap;gap:4px}
.eff{border-radius:12px;padding:2px 10px;font-size:12px;display:inline-block}
.eff.pos{background:rgba(76,175,80,0.12);border:1px solid #4CAF50;color:#388E3C}
.eff.neg{background:rgba(244,67,54,0.10);border:1px solid #f44336;color:#D32F2F}
.no-eff{color:#999;font-size:12px}
mark.ann-hl{background:#FFF176;border-bottom:2px solid #F9A825;border-radius:2px;padding:0 1px;cursor:pointer}
mark.ann-done{background:#E8F5E9;border-bottom:2px solid #66BB6A;border-radius:2px;padding:0 1px;cursor:pointer;text-decoration:line-through;opacity:.7}
#sel-btn{position:fixed;display:none;background:#1a237e;color:white;padding:6px 14px;border-radius:16px;box-shadow:0 3px 12px rgba(0,0,0,.3);cursor:pointer;z-index:1000;font-size:13px;font-weight:500;user-select:none;white-space:nowrap}
#sel-btn:hover{background:#283593}
#ann-panel{display:none;position:fixed;bottom:0;left:0;right:0;background:white;border-top:2px solid #1a237e;padding:14px 16px;z-index:999;box-shadow:0 -4px 18px rgba(0,0,0,.18)}
#ann-quote{background:#FFFDE7;border:1px solid #F9A825;border-radius:6px;padding:6px 10px;font-size:13px;color:#555;margin-bottom:10px;word-break:break-all}
#ann-text{width:100%;border:1px solid #e0e0e0;border-radius:6px;padding:8px 10px;font-size:13px;height:68px;resize:none;font-family:inherit}
#ann-text:focus{outline:none;border-color:#1a237e}
.ann-btns{display:flex;gap:8px;margin-top:8px}
#ann-ok{flex:1;background:#1a237e;color:white;border:none;border-radius:6px;padding:8px;cursor:pointer;font-size:13px;font-weight:500}
#ann-ok:hover{background:#283593}
#ann-cancel-btn{background:#f5f5f5;border:1px solid #ddd;border-radius:6px;padding:8px 16px;cursor:pointer;font-size:13px}
#ann-msg{font-size:12px;margin-top:6px;display:none}
#hl-popup{position:fixed;display:none;background:white;border:1px solid #e0e0e0;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,.18);padding:12px 14px;z-index:2000;min-width:220px;max-width:320px}
#hl-popup-body{font-size:13px;color:#333;margin-bottom:10px;line-height:1.6;border-left:3px solid #F9A825;padding-left:8px}
.hl-btns{display:flex;gap:6px;flex-wrap:wrap}
.hl-btn{border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:12px;font-weight:500}
.hl-btn-edit{background:#E3F2FD;color:#1565C0}.hl-btn-done{background:#E8F5E9;color:#2E7D32}.hl-btn-del{background:#FFEBEE;color:#C62828}
.hl-btn:hover{filter:brightness(.93)}
#hl-edit-row{display:none;margin-top:8px}
#hl-edit-input{width:100%;border:1px solid #e0e0e0;border-radius:6px;padding:6px 8px;font-size:13px;font-family:inherit}
#hl-edit-save{margin-top:6px;background:#1a237e;color:white;border:none;border-radius:6px;padding:6px 14px;cursor:pointer;font-size:12px;font-weight:500}"""

    js = f"""var _sel='',_annVis=false,CARD_ID={card_id},TOKEN='{token}',BACKEND='{backend_url}',_curNid=null,_popTimer=null;
document.addEventListener('mouseup',function(e){{var s=window.getSelection(),t=s?s.toString().trim():'';var btn=document.getElementById('sel-btn');if(t.length>1&&!_annVis){{_sel=t;btn.style.display='block';btn.style.top=Math.max(8,e.clientY-44)+'px';btn.style.left=Math.min(e.clientX-60,window.innerWidth-200)+'px';}}else if(!_annVis){{btn.style.display='none';}}}});
document.addEventListener('mousedown',function(e){{if(!document.getElementById('sel-btn').contains(e.target)&&!_annVis)document.getElementById('sel-btn').style.display='none';}});
document.getElementById('sel-btn').addEventListener('click',function(){{if(!_sel)return;this.style.display='none';document.getElementById('ann-quote').textContent='"'+_sel+'"';document.getElementById('ann-text').value='';document.getElementById('ann-msg').style.display='none';document.getElementById('ann-panel').style.display='block';_annVis=true;document.getElementById('ann-text').focus();}});
document.getElementById('ann-cancel-btn').addEventListener('click',function(){{document.getElementById('ann-panel').style.display='none';_annVis=false;_sel='';}});
document.getElementById('ann-ok').addEventListener('click',function(){{var content=document.getElementById('ann-text').value.trim();if(!content){{document.getElementById('ann-text').style.borderColor='#f44336';return;}}document.getElementById('ann-text').style.borderColor='#e0e0e0';var btn=this;btn.disabled=true;btn.textContent='提交中...';fetch(BACKEND+'/api/admin/cards/'+CARD_ID+'/notes',{{method:'POST',headers:{{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN}},body:JSON.stringify({{content:content,selected_text:_sel}})}}).then(function(r){{return r.json();}}).then(function(d){{if(d.ok){{document.getElementById('ann-msg').textContent='✅ 批注已保存，刷新中...';document.getElementById('ann-msg').style.color='#388E3C';document.getElementById('ann-msg').style.display='block';btn.textContent='已保存';_annVis=false;setTimeout(function(){{window.location.reload();}},600);}}else{{document.getElementById('ann-msg').textContent='❌ '+(d.error||'提交失败');document.getElementById('ann-msg').style.color='#D32F2F';document.getElementById('ann-msg').style.display='block';btn.disabled=false;btn.textContent='确认批注';}}}}).catch(function(){{document.getElementById('ann-msg').textContent='❌ 网络错误';document.getElementById('ann-msg').style.display='block';btn.disabled=false;btn.textContent='确认批注';}});}});
var popup=document.getElementById('hl-popup');
function _showPopup(el,e){{_curNid=el.getAttribute('data-nid');var content=el.getAttribute('data-content')||'';var completed=el.getAttribute('data-completed')==='true';document.getElementById('hl-popup-body').textContent=content;document.getElementById('hl-edit-row').style.display='none';document.getElementById('hl-edit-input').value=content;var db=document.getElementById('hl-btn-done');db.textContent=completed?'✓ 已完成':'✅ 标记完成';db.style.display=completed?'none':'inline-block';popup.style.display='block';var px=Math.min(e.clientX+10,window.innerWidth-340);var py=e.clientY-popup.offsetHeight-10;if(py<10)py=e.clientY+20;popup.style.left=px+'px';popup.style.top=py+'px';}}
function _hidePopup(){{popup.style.display='none';_curNid=null;}}
document.querySelectorAll('mark.ann-hl,mark.ann-done').forEach(function(m){{m.addEventListener('mouseenter',function(e){{clearTimeout(_popTimer);_showPopup(this,e);}});m.addEventListener('mouseleave',function(){{_popTimer=setTimeout(function(){{_hidePopup();}},300);}});}});
popup.addEventListener('mouseenter',function(){{clearTimeout(_popTimer);}});popup.addEventListener('mouseleave',function(){{_popTimer=setTimeout(_hidePopup,300);}});
document.getElementById('hl-btn-edit').addEventListener('click',function(){{document.getElementById('hl-edit-row').style.display='block';document.getElementById('hl-edit-input').focus();}});
document.getElementById('hl-edit-save').addEventListener('click',function(){{var nc=document.getElementById('hl-edit-input').value.trim();if(!nc||!_curNid)return;this.disabled=true;fetch(BACKEND+'/api/admin/cards/'+CARD_ID+'/notes/'+_curNid,{{method:'PUT',headers:{{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN}},body:JSON.stringify({{content:nc}})}}).then(function(r){{return r.json();}}).then(function(d){{if(d.ok)window.location.reload();else alert('保存失败: '+(d.error||''));}});}});
document.getElementById('hl-btn-done').addEventListener('click',function(){{if(!_curNid)return;this.disabled=true;fetch(BACKEND+'/api/admin/cards/'+CARD_ID+'/notes/'+_curNid,{{method:'PUT',headers:{{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN}},body:JSON.stringify({{completed:true}})}}).then(function(r){{return r.json();}}).then(function(d){{if(d.ok)window.location.reload();else alert('操作失败: '+(d.error||''));}});}});
document.getElementById('hl-btn-del').addEventListener('click',function(){{if(!_curNid)return;if(!confirm('确认删除该批注？'))return;this.disabled=true;fetch(BACKEND+'/api/admin/cards/'+CARD_ID+'/notes/'+_curNid,{{method:'DELETE',headers:{{'Authorization':'Bearer '+TOKEN}}}}).then(function(r){{return r.json();}}).then(function(d){{if(d.ok)window.location.reload();else alert('删除失败: '+(d.error||''));}});}});"""

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
        f'<div id="sel-btn">✍️ 批注</div>'
        f'<div id="ann-panel">'
        f'<div id="ann-quote"></div>'
        f'<textarea id="ann-text" placeholder="写下批注内容..."></textarea>'
        f'<div class="ann-btns"><button id="ann-ok">确认批注</button>'
        f'<button id="ann-cancel-btn">取消</button></div>'
        f'<div id="ann-msg"></div>'
        f'</div>'
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

    tab1, tab2, tab3, tab4 = st.tabs(["📄 卡牌详情", "✏️ 卡牌编辑", "💬 批注历史", "📜 版本历史"])

    # ── Tab 1: 详情 ──
    with tab1:
        import streamlit.components.v1 as stc
        stc.html(
            _build_card_view_html(
                card, notes,
                token=st.session_state.get('token', ''),
                backend_url=BACKEND_URL
            ),
            height=560, scrolling=True
        )
        st.divider()
        a1, a2, a3, a4 = st.columns(4)
        if a2.button("🔵 建测试版", use_container_width=True, key=f"dlg_draft_{card_id}"):
            res = requests.post(f"{BACKEND_URL}/api/admin/cards/{card_id}/branch", headers=headers)
            if res.ok:
                st.success(f"测试版已创建: {res.json().get('version_label')}")
                time.sleep(0.5); st.rerun()
            else:
                st.error(res.text)
        if card.get('branch') == 'draft' and a3.button("🚀 发布", use_container_width=True, key=f"dlg_pub_{card_id}"):
            if st.session_state.get('confirm_pub_dlg'):
                res = requests.post(f"{BACKEND_URL}/api/admin/cards/{card_id}/publish", headers=headers)
                if res.ok:
                    st.success("已发布！"); st.session_state.confirm_pub_dlg = False
                    time.sleep(0.5); st.rerun()
                else:
                    st.error(res.text)
            else:
                st.session_state.confirm_pub_dlg = True
                st.warning("⚠️ 再次点击确认覆盖线上版本")
        status = card.get('status')
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
        safety_opts = ['身体安全', '网络安全', '心理安全', '隐私安全', '社会安全']
        phase_opts = ['启蒙期', '成长期', '青春期']
        attrs = ['安全力', '脑波力', '实感力', '创心力', '沟通力']
        options = card.get('options', {})
        e_safety = st.selectbox("安全类型", safety_opts,
            index=safety_opts.index(card['safetyType']) if card.get('safetyType') in safety_opts else 0,
            key=f"e_safety_{card_id}")
        e_phase = st.selectbox("年龄阶段", phase_opts,
            index=phase_opts.index(card['phase']) if card.get('phase') in phase_opts else 0,
            key=f"e_phase_{card_id}")
        e_event = st.text_area("📖 事件描述", value=card.get('event', ''), height=130, key=f"e_event_{card_id}")
        e_vlabel = st.text_input("版本标签（可选）",
            value=card.get('versionLabel') or card.get('version_label') or '', key=f"e_vlabel_{card_id}")
        e_audio = st.text_input("🔊 音频 OSS 链接（可选）",
            value=card.get('audio_url') or card.get('audioUrl') or '', key=f"e_audio_{card_id}")
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
        if st.button("💾 保存", use_container_width=True, type="primary", key=f"e_save_{card_id}"):
            if not e_event.strip():
                st.error("事件描述不能为空")
            else:
                try:
                    updated = {
                        "safetyType": e_safety, "phase": e_phase, "event": e_event,
                        "options": new_options, "version_label": e_vlabel, "audio_url": e_audio
                    }
                    res = requests.put(f"{BACKEND_URL}/api/cards/{card_id}", json=updated, headers=headers)
                    if res.ok:
                        st.success("✅ 保存成功！")
                        time.sleep(0.5); st.rerun()
                    else:
                        st.error(f"保存失败: {res.text}")
                except Exception as e:
                    st.error(str(e))

    # ── Tab 3: 批注历史 ──
    with tab3:
        if not notes:
            st.info("暂无批注")
        else:
            for n in reversed(notes):
                ts = format_ts(n.get('created_at'))
                sel = n.get('selected_text', '')
                completed = n.get('completed', False)
                if sel:
                    st.markdown(
                        f'<div style="background:#FFFDE7;border-left:3px solid #F9A825;'
                        f'border-radius:0 6px 6px 0;padding:6px 10px;margin:4px 0;font-size:13px">'
                        f'{"✅" if completed else "📌"} <em>"{html_lib.escape(sel)}"</em></div>',
                        unsafe_allow_html=True
                    )
                st.markdown(f"**{ts}** — {n.get('content', '')}")
                st.divider()
        st.caption("💡 在「卡牌详情」中选中文字后点「✍️ 批注」可带高亮批注")
        with st.form(f"note_dlg_{card_id}"):
            note_content = st.text_area("添加批注", height=70, placeholder="整体评价或无引用批注...",
                                        key=f"note_inp_{card_id}")
            if st.form_submit_button("📝 提交", use_container_width=True):
                if note_content.strip():
                    res = requests.post(f"{BACKEND_URL}/api/admin/cards/{card_id}/notes",
                        json={"content": note_content}, headers=headers)
                    if res.ok:
                        st.success("✅ 批注已添加"); st.rerun()
                    else:
                        st.error(res.text)
                else:
                    st.warning("请填写批注内容")

    # ── Tab 4: 版本历史 ──
    with tab4:
        try:
            res = requests.get(f"{BACKEND_URL}/api/admin/cards/{card_id}/versions", headers=headers)
            versions = res.json().get('versions', []) if res.ok else []
            if versions:
                for v in versions:
                    icon = '🟢' if v.get('branch') == 'release' else '🔵'
                    label = v.get('version_label') or f"v{v['version']}"
                    with st.expander(f"{icon} {label}  [{v['status']}]  {format_ts(v.get('updated_at'))}"):
                        st.caption(v.get('event', '')[:300])
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

    # ── 顶部筛选栏 ──
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 2, 1, 1])
    with fc1:
        branch_filter = st.selectbox("分支", ['全部', 'release', 'draft'], key="card_branch_f")
    with fc2:
        status_filter = st.selectbox("状态", ['全部', 'active', 'pending', 'rejected', 'deleted'], key="card_status_f")
    with fc3:
        safety_opts = ['全部', '身体安全', '网络安全', '心理安全', '隐私安全', '社会安全']
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
        params = {}
        if status_filter != '全部':
            params['status'] = status_filter
        res = requests.get(f"{BACKEND_URL}/api/admin/cards", params=params, headers=headers)
        all_cards = res.json().get('cards', []) if res.ok else []
    except Exception as e:
        st.error(f"获取卡牌失败: {e}"); return

    if branch_filter != '全部':
        all_cards = [c for c in all_cards if (c.get('branch') or 'release') == branch_filter]
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
                n_safety = st.selectbox("安全类型", ['身体安全', '网络安全', '心理安全', '隐私安全', '社会安全'])
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

    # ── 全宽卡牌网格 ──
    if not all_cards:
        st.info("没有符合条件的卡牌")
    else:
        for row_start in range(0, len(all_cards), 3):
            row_cards = all_cards[row_start:row_start + 3]
            cols = st.columns(3)
            for i, card in enumerate(row_cards):
                with cols[i]:
                    st.markdown(_render_card_visual(card, False), unsafe_allow_html=True)
                    if st.button("查看详情", key=f"view_{card['id']}_{row_start}"):
                        st.session_state._open_card_dialog = card['id']
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

'''

def main():
    with open(APP_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    start_marker = 'def _render_card_options_full(options):'
    end_marker = '\ndef activity_management_page():'

    start = content.find(start_marker)
    end = content.find(end_marker)

    if start == -1:
        print("ERROR: start marker not found")
        return
    if end == -1:
        print("ERROR: end marker not found")
        return

    new_content = content[:start] + NEW_SECTION + content[end:]

    with open(APP_PATH, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Done. Replaced {end - start} chars with {len(NEW_SECTION)} chars.")
    print(f"File size: {len(new_content)} chars")

if __name__ == '__main__':
    main()
