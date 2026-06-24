(function () {
  const REVIEW_STATE = {
    working: false
  };

  function getToken() {
    return localStorage.getItem("WQT_AUTH_TOKEN") || "";
  }

  // 会话 ID 用 sessionStorage（按标签页隔离），避免多标签页互相覆盖：
  // 否则新标签页开新游戏会改写 localStorage 里的 WQT_SESSION_ID，
  // 导致原标签页复盘时读到别的标签页的对局数据。
  function getSessionId() {
    const cached = Number(sessionStorage.getItem("WQT_SESSION_ID"));
    return Number.isFinite(cached) && cached > 0 ? cached : null;
  }

  function setSessionId(sessionId) {
    if (sessionId) {
      sessionStorage.setItem("WQT_SESSION_ID", String(sessionId));
    } else {
      sessionStorage.removeItem("WQT_SESSION_ID");
    }
  }

  async function api(path, { method = "GET", body = null } = {}) {
    const headers = { "Content-Type": "application/json" };
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : null
    });
    let data = null;
    try {
      data = await res.json();
    } catch (_) { }
    if (!res.ok) {
      const msg = data && data.error ? data.error : `请求失败(${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  function parsePayload(payload) {
    if (!payload) return {};
    if (typeof payload === "object") return payload;
    try {
      return JSON.parse(payload);
    } catch (_) {
      return {};
    }
  }

  function sumAttributes(attrs) {
    if (!attrs || typeof attrs !== "object") return 0;
    return Object.values(attrs).reduce((sum, value) => sum + Number(value || 0), 0);
  }

  function formatTs(ts) {
    if (!ts) return "";
    const d = new Date(Number(ts));
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleString();
  }

  function formatDurationMs(ms) {
    if (!Number.isFinite(ms) || ms <= 0) return "";
    const totalSec = Math.round(ms / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m}分${s}秒`;
  }

  function buildReviewData(session, events) {
    const parsedEvents = (events || []).map((ev) => ({
      ...ev,
      payload: parsePayload(ev.payload)
    }));

    const cardEvents = parsedEvents.filter((ev) => ev.type === "card_choice");
    const skillEvents = parsedEvents.filter((ev) => ev.type === "skill_use");
    const startEvent = parsedEvents.find((ev) => ev.type === "game_start");
    const finishEvent = parsedEvents.find((ev) => ev.type === "game_finish");

    const cards = cardEvents.map((ev, index) => {
      const payload = ev.payload || {};
      const before = payload.attributesBefore || {};
      const after = payload.attributesAfter || {};
      const delta = payload.attributeDelta || payload.attributeEffects || {};
      return {
        index: index + 1,
        cardId: payload.cardId || null,
        cardCode: payload.cardCode || null,
        phase: payload.phase || "",
        safetyType: payload.safetyType || "",
        eventText: payload.eventText || "",
        choice: payload.choice || "",
        optionText: payload.optionText || "",
        consequence: payload.consequence || "",
        reason: payload.reason || "",
        allOptions: payload.allOptions || null,
        subtopic: payload.subtopic || "",
        whitepaperRef: payload.whitepaperRef || "",
        timeSpentSec: payload.timeSpentSec ?? null,
        attributeDelta: delta,
        attributesBefore: before,
        attributesAfter: after,
        wasFailure: Boolean(payload.wasFailure),
        isCreativeOption: Boolean(payload.isCreativeOption),
        ts: ev.ts || null
      };
    });

    const skills = skillEvents.map((ev) => {
      const payload = ev.payload || {};
      return {
        ts: ev.ts || null,
        skill: payload.skill || "",
        cardId: payload.cardId || null,
        optionD: payload.optionD || "",
        rescued: payload.rescued || [],
        attributeChange: payload.attributeChange || {},
        attributesBefore: payload.attributesBefore || {},
        attributesAfter: payload.attributesAfter || {}
      };
    });

    const finalScore = Number.isFinite(session.final_score)
      ? Number(session.final_score)
      : cards.length
        ? sumAttributes(cards[cards.length - 1].attributesAfter)
        : 0;

    const startedAt = session.started_at || (startEvent && startEvent.ts) || null;
    const endedAt = session.ended_at || (finishEvent && finishEvent.ts) || null;
    const durationMs = startedAt && endedAt ? Number(endedAt) - Number(startedAt) : null;

    // Parse new fields
    let players = null;
    try { players = session.players_json ? JSON.parse(session.players_json) : null; } catch (_) { }

    let settings = null;
    try { settings = session.game_settings_json ? JSON.parse(session.game_settings_json) : null; } catch (_) { }

    // 本局卡组/版本：优先 game_start 记录的 cardGroup，回退按 card_code 前缀推断
    const cardGroup = (startEvent && startEvent.payload && startEvent.payload.cardGroup) || null;
    const versionLabel = resolveVersionLabel(cardGroup, cards);

    return {
      session: {
        id: session.id,
        startedAt,
        endedAt,
        finalScore,
        location: session.location,
        players,
        mode: session.game_mode,
        settings,
        cardGroup,
        versionLabel
      },
      cards,
      skills,
      durationMs
    };
  }

  // 推断本局卡牌版本名：有记录用记录名；否则按 card_code 前缀（2026/2025…）兜底
  function resolveVersionLabel(cardGroup, cards) {
    if (cardGroup && cardGroup.name) return cardGroup.name;
    const codes = (cards || []).map((c) => c.cardCode || "").filter(Boolean);
    if (codes.some((c) => c.startsWith("2026"))) return "2026 精选卡牌";
    if (codes.some((c) => c.startsWith("2025"))) return "2025版";
    return "";
  }

  // 五维伍力轴 & 五类风险轴（与海报参考图一致）
  const ABILITY_AXES = ["安全力", "脑波力", "实感力", "创心力", "沟通力"];
  const RISK_AXES = ["身体安全", "心理安全", "社交安全", "经济安全", "社会安全"];

  // 把卡牌的 safety_type 文案归一到 5 类风险轴；命中不了就返回 null
  function normalizeRiskAxis(raw) {
    const s = String(raw || "");
    if (!s) return null;
    if (/身体|人身|健康|生理/.test(s)) return "身体安全";
    if (/心理|情绪|精神|心灵/.test(s)) return "心理安全";
    if (/社交|交友|社会交往|人际|网络社交/.test(s)) return "社交安全";
    if (/经济|财产|金钱|财务|消费|诈骗|钱/.test(s)) return "经济安全";
    if (/社会|公共|法律|规则|公德/.test(s)) return "社会安全";
    // 精确匹配兜底
    if (RISK_AXES.includes(s)) return s;
    return null;
  }

  // 本地计算两组雷达数据：伍力调动（按 attributeDelta 正向累计）与风险遭遇（按 safetyType 计数）
  function computeRadars(data, llmRiskRadar) {
    const ability = {};
    ABILITY_AXES.forEach((k) => (ability[k] = 0));
    const risk = {};
    RISK_AXES.forEach((k) => (risk[k] = 0));

    (data.cards || []).forEach((card) => {
      const delta = card.attributeDelta || {};
      ABILITY_AXES.forEach((k) => {
        const v = Number(delta[k] || 0);
        if (v > 0) ability[k] += v;
      });
      const axis = normalizeRiskAxis(card.safetyType);
      if (axis) risk[axis] += 1;
    });
    (data.skills || []).forEach((skill) => {
      const ch = skill.attributeChange || {};
      ABILITY_AXES.forEach((k) => {
        const v = Number(ch[k] || 0);
        if (v > 0) ability[k] += v;
      });
    });

    // 风险数据若本地全为 0（老对局无 safetyType），回退到 LLM 给的分布
    const riskSum = RISK_AXES.reduce((s, k) => s + risk[k], 0);
    if (riskSum === 0 && llmRiskRadar && typeof llmRiskRadar === "object") {
      RISK_AXES.forEach((k) => {
        risk[k] = Number(llmRiskRadar[k] || 0);
      });
    }

    return { ability, risk };
  }

  // 生成结构化复盘 JSON 的 prompt（对应海报 01/02/03/04/05 板块）
  function buildStructuredPrompt(data) {
    const payload = {
      location: data.session.location,
      players: formatPlayers(data.session.players),
      mode: data.session.mode,
      duration: formatDurationMs(data.durationMs),
      finalScore: data.session.finalScore,
      cards: data.cards.map((card) => {
        let alternatives = null;
        if (card.allOptions) {
          alternatives = Object.entries(card.allOptions)
            .filter(([k]) => k !== card.choice)
            .map(([k, o]) => ({ option: k, text: o.text, reason: o.reason || "" }));
        }
        return {
          phase: card.phase,
          safetyType: card.safetyType,
          event: card.eventText,
          choice: card.choice,
          optionText: card.optionText,
          consequence: card.consequence,
          chosenReason: card.reason || "",
          alternatives,
          delta: card.attributeDelta,
          wasFailure: card.wasFailure,
          isCreativeOption: card.isCreativeOption
        };
      }),
      skills: data.skills.map((s) => ({ skill: s.skill, optionD: s.optionD, rescued: s.rescued }))
    };

    return [
      "你是儿童数智安全教育桌游《AI在5000天·伍力全开》的复盘分析师，面向家长与孩子写一份温暖、积极、可阅读的单轮复盘。主角统一称为「小伍」。",
      "",
      "【最重要的铁律 · 严禁虚构，违反即不合格】",
      "- 你只能依据下方『游戏数据』里真实存在的卡牌情境、选项、后果、五力变化来写，绝对不能编造数据里没有的事实。",
      "- 人物白名单：故事里只允许出现『游戏数据』中实际涉及的角色（小伍本人、小伍的爸爸/妈妈、老师，以及各卡牌情境里出现的对象如陌生人、网友、同学、上门的人）。",
      "  严禁新增数据中不存在的任何人物——例如奶奶、爷爷、弟弟、妹妹、邻居、宠物、给同学起的名字等，一律不许出现。",
      "  也不要为了烘托气氛而添加任何路人、旁观者、背景人物（如『一位老奶奶也在等红灯』这类都不允许）。场景里只有卡牌情境本身涉及的人。",
      "- 不得添加数据中不存在的具体名词：不要凭空起品牌名/商品名（如把『糖』写成某款具体的糖）、不要虚构地名、人名、时间、对话台词或数据里没发生的情节。",
      "- 允许的只是：在忠于卡牌情境的前提下，做合理的心理描写、情绪刻画与语言润色；任何超出卡牌信息范围的具体事实都不许出现。宁可写得概括，也不要编造。",
      "- story.scenes 的 imagePrompt：只描绘卡牌里确有的元素。可以把小伍统一画成一个戴圆框眼镜、穿日常便装的小男孩（这是固定人物设定），但不要添加暗示具体事实的道具或服饰（如睡衣、某种特定食物、特定玩具）。",
      "",
      "请严格输出 JSON（不要 markdown 代码块外的任何文字），结构如下：",
      "```json",
      "{",
      '  "overview": {',
      '    "experienced": "用2-3句话讲小伍这一轮大致经历了什么（场景化、口语化）",',
      '    "summary": "一句话本轮结论（25字内，朗朗上口）"',
      "  },",
      '  "riskRadar": {"身体安全":数字,"心理安全":数字,"社交安全":数字,"经济安全":数字,"社会安全":数字},',
      '  "riskComment": "针对本轮风险遭遇的一句话点评（30字内）",',
      '  "abilityComment": "针对本轮伍力调动的一句话点评（30字内）",',
      '  "story": {',
      '    "paragraphs": ["闯关故事段落1","段落2","……（8-14段，逐关详写）"],',
      '    "scenes": [',
      '      {"caption":"配图说明（10字内，点出这是哪一幕）","imagePrompt":"具体画面的中文描述：谁、在哪、在做什么、表情动作、关键道具，越具象越好"}',
      "    ],",
      '    "tips": ["成长小贴士1","小贴士2","小贴士3"]',
      "  },",
      '  "pact": {',
      '    "items": ["数智行动公约1","公约2","公约3","公约4"],',
      '    "takeaway": "本轮带回家的一句话（家长可对孩子说，30字内）"',
      "  }",
      "}",
      "```",
      "要求：",
      "- riskRadar：按卡牌 safetyType 估算本轮各类风险出现的相对强度（0-5 的整数即可），无法判断时给 0。",
      "- story.paragraphs：这是报告的核心，必须写得详实丰满。【至少 8-14 个自然段、合计不少于 1500 字】。",
      "  篇幅的丰满必须来自把每张卡的真实字段讲透——每张卡数据都给了：情境(event)、所选选项(optionText)、该选项后果(consequence)、五力增减(delta 的具体数值)、小伍选它的理由(chosenReason)、以及未选选项(alternatives)。",
      "  按卡牌顺序逐关展开：交代情境 → 小伍怎么想（用 chosenReason）→ 选了什么 → 后果如何（用 consequence）→ 五力具体怎么变（点出 delta 的力与数值，如『安全力+2』）→ 必要时对比『本可以怎么选』。",
      "  靠讲透这些真实字段来写长，而不是靠添加数据里没有的细节。可做心理与情绪刻画，但不得引入新的人物/事物/事件。段落之间自然衔接，写成有起承转合的成长故事而非要点罗列。",
      "- story.scenes：挑出故事里 2-3 个最具画面感的关键时刻，每个给 caption（这一幕叫什么）和 imagePrompt（具体到人物/场景/动作/道具的中文画面描述，供文生图使用，要能一眼看出在讲什么故事，避免空泛）。scenes 要与 paragraphs 的情节对应。",
      "- story.tips：3 条具体可执行的成长小贴士。",
      "- pact.items：4 条把游戏经验带回真实生活的行动公约，第一人称「我会…」。",
      "- 全程语气温暖、鼓励，适合 6-12 岁孩子家庭共读。",
      "",
      "游戏数据：",
      "```json",
      JSON.stringify(payload, null, 2),
      "```"
    ].join("\n");
  }

  // 统一的插画风格前缀（保证多张配图视觉一致）
  const ILLU_STYLE = "扁平矢量儿童绘本插画，蓝紫色科技感配色，柔和光影，主角是一个戴圆框眼镜、活泼勇敢的中国小男孩「小伍」，画面温暖治愈、积极阳光、构图饱满，画面中不要出现任何文字。具体场景：";

  // 单个故事场景的生图 prompt（具象到画面，表达一个具体故事时刻）
  function buildScenePrompt(scene, structured) {
    const desc = (scene && (scene.imagePrompt || scene.caption)) ||
      (structured?.overview?.experienced || "小伍在数字世界中做出机智而勇敢的选择");
    return ILLU_STYLE + String(desc).slice(0, 200);
  }

  // 从结构化数据里取出要配图的场景列表（兜底：用总览造一个场景）
  function pickScenes(structured) {
    const raw = (structured && structured.story && Array.isArray(structured.story.scenes))
      ? structured.story.scenes.filter((s) => s && (s.imagePrompt || s.caption))
      : [];
    if (raw.length) return raw.slice(0, 3);
    return [{ caption: "本轮闯关", imagePrompt: structured?.overview?.experienced || "" }];
  }

  function formatPlayers(p) {
    if (!p) return "未知";
    let s = [];
    if (p.enlightenment) s.push(`启蒙期${p.enlightenment}人`);
    if (p.growth) s.push(`成长期${p.growth}人`);
    if (p.adolescence) s.push(`青春期${p.adolescence}人`);
    if (p.adults) s.push(`成年人${p.adults}人`);
    return s.length ? s.join(", ") : "无详细数据";
  }

  function escapeHtml(input) {
    return String(input)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // 生成五边形雷达图 SVG（自包含，无运行期依赖，便于 html2canvas 截图）
  function radarSvg(axes, valuesObj, color) {
    const size = 260, cx = size / 2, cy = size / 2 + 6, R = 84;
    const n = axes.length;
    const vals = axes.map((a) => Number(valuesObj[a] || 0));
    const max = Math.max(...vals, 1);
    const angle = (i) => (-90 + (360 / n) * i) * Math.PI / 180;
    const pt = (i, r) => [cx + r * Math.cos(angle(i)), cy + r * Math.sin(angle(i))];

    let grid = "";
    [0.25, 0.5, 0.75, 1].forEach((ring) => {
      const poly = axes.map((_, i) => pt(i, R * ring).map((v) => v.toFixed(1)).join(",")).join(" ");
      grid += `<polygon points="${poly}" fill="none" stroke="#c9d6f0" stroke-width="1"/>`;
    });
    let spokes = "";
    axes.forEach((_, i) => {
      const [x, y] = pt(i, R);
      spokes += `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="#c9d6f0" stroke-width="1"/>`;
    });
    const dataPoly = axes
      .map((_, i) => pt(i, R * (vals[i] / max)).map((v) => v.toFixed(1)).join(","))
      .join(" ");
    let dots = "";
    let labels = "";
    axes.forEach((a, i) => {
      const [dx, dy] = pt(i, R * (vals[i] / max));
      dots += `<circle cx="${dx.toFixed(1)}" cy="${dy.toFixed(1)}" r="3" fill="${color}"/>`;
      const [lx, ly] = pt(i, R + 18);
      const anchor = Math.abs(lx - cx) < 6 ? "middle" : (lx > cx ? "start" : "end");
      labels += `<text x="${lx.toFixed(1)}" y="${(ly + 4).toFixed(1)}" font-size="12" font-weight="600" fill="#2b3a67" text-anchor="${anchor}">${a} ${vals[i]}</text>`;
    });

    // 左右各留 PAD 像素，避免 start/end 对齐的边缘标签被裁切
    const PAD = 62;
    return [
      `<svg viewBox="${-PAD} -8 ${size + 2 * PAD} ${size + 16}" width="100%" style="max-width:340px;display:block;margin:0 auto;">`,
      grid, spokes,
      `<polygon points="${dataPoly}" fill="${color}33" stroke="${color}" stroke-width="2"/>`,
      dots, labels,
      "</svg>"
    ].join("");
  }

  function phaseFromPlayers(players) {
    if (!players) return "—";
    const arr = [];
    if (players.enlightenment) arr.push("启蒙期");
    if (players.growth) arr.push("成长期");
    if (players.adolescence) arr.push("青春期");
    if (players.adults) arr.push("成年人");
    return arr.length ? arr.join(" / ") : "—";
  }

  // 把段落与场景插画交错排版：图片浮动（左右交替），正文绕排，杂志式更密集
  function buildStoryBody(paras, sceneImages) {
    const E = escapeHtml;
    if (!paras.length) return "<p>—</p>";
    const imgs = (sceneImages || []).filter((s) => s && s.dataUri);
    // 计算每张图插入到第几段之前（均匀分布，首图靠前）
    const slots = {};
    const n = imgs.length;
    for (let i = 0; i < n; i++) {
      let idx = Math.floor((i + 0.5) * paras.length / (n + 1));
      idx = Math.min(Math.max(idx, i === 0 ? 1 : 0), paras.length - 1);
      while (slots[idx] !== undefined && idx < paras.length) idx++;
      slots[idx] = i;
    }
    let out = "";
    paras.forEach((p, pi) => {
      if (slots[pi] !== undefined) {
        const img = imgs[slots[pi]];
        const side = slots[pi] % 2 === 0 ? "illu-right" : "illu-left";
        out += `<figure class="illu ${side}"><img src="${img.dataUri}" alt="${E(img.caption || "故事插画")}"/>`
          + (img.caption ? `<figcaption>${E(img.caption)}</figcaption>` : "")
          + "</figure>";
      }
      out += `<p>${E(p)}</p>`;
    });
    out += '<div style="clear:both"></div>';
    return out;
  }

  function buildReportHtml(structured, data, radars, sceneImages, cardFaces) {
    const s = structured || {};
    const overview = s.overview || {};
    const story = s.story || {};
    const pact = s.pact || {};
    const players = data.session.players;

    const dateStr = formatTs(data.session.startedAt) || new Date().toLocaleString();
    const playersStr = formatPlayers(players);
    const phaseStr = phaseFromPlayers(players);
    const versionStr = data.session.versionLabel || "—";

    const tips = Array.isArray(story.tips) ? story.tips : [];
    const paras = Array.isArray(story.paragraphs) ? story.paragraphs : (story.paragraphs ? [String(story.paragraphs)] : []);
    const pactItems = Array.isArray(pact.items) ? pact.items : [];

    const riskSvg = radarSvg(RISK_AXES, (radars && radars.risk) || {}, "#5b8def");
    const abilitySvg = radarSvg(ABILITY_AXES, (radars && radars.ability) || {}, "#ffb020");

    const E = escapeHtml;
    const tipsHtml = tips.map((t) => `<li>${E(t)}</li>`).join("");
    const storyBodyHtml = buildStoryBody(paras, sceneImages);
    const pactHtml = pactItems.map((p, i) => `<div class="pact-item"><span class="pact-no">${i + 1}</span>${E(p)}</div>`).join("");

    // 本轮真实卡面图条带
    const faces = Array.isArray(cardFaces) ? cardFaces.filter((f) => f && f.dataUri) : [];
    const cardStripHtml = faces.length
      ? `<div class="cardstrip">
           <div class="cardstrip-title">🃏 本轮玩过的卡牌（共 ${faces.length} 张，点击放大）· 版本：${E(versionStr)}</div>
           <div class="cardstrip-row">${faces.map((f) => `<div class="cardface"><img class="cf-img" src="${f.dataUri}" alt="${E(f.code || "卡面")}" data-code="${E(f.code || "")}" title="点击放大"/><span>${E(f.code || "")}</span></div>`).join("")}</div>
         </div>`
      : "";

    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>小伍5000天数智成长评估报告</title>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<style>
  * { box-sizing: border-box; }
  body { margin:0; padding:24px 12px; font-family:'PingFang SC','Microsoft YaHei',sans-serif;
         background:#0b1b3a; color:#22304f; }
  #poster { max-width:720px; margin:0 auto; background:
            radial-gradient(circle at 20% 0%, #1c3a73 0%, transparent 45%),
            radial-gradient(circle at 100% 100%, #142a55 0%, transparent 40%),
            linear-gradient(160deg,#0e2350 0%,#0a1a3c 100%);
            border-radius:18px; overflow:hidden; padding:0 0 6px;
            box-shadow:0 20px 60px rgba(0,0,0,.5); }
  .banner { position:relative; padding:26px 28px 22px; text-align:center;
            background:linear-gradient(120deg,#2455c6 0%,#3a7bff 50%,#7a4bff 100%); }
  .banner .logo { display:inline-block; font-weight:800; font-size:13px; letter-spacing:1px;
            color:#fff; background:rgba(255,255,255,.15); border:1px solid rgba(255,255,255,.45);
            border-radius:8px; padding:5px 12px; margin-bottom:12px; }
  .banner h1 { margin:0; font-size:30px; color:#fff; font-weight:900; letter-spacing:2px;
            text-shadow:0 2px 0 rgba(0,0,0,.18); }
  .banner .sub { margin-top:8px; display:inline-block; font-size:14px; color:#0b1b3a;
            background:#ffd54a; border-radius:20px; padding:4px 16px; font-weight:700; }
  .meta { display:flex; flex-wrap:wrap; gap:10px; justify-content:center; padding:16px 20px 4px; }
  .meta .chip { background:rgba(255,255,255,.92); border-radius:10px; padding:8px 14px;
            font-size:13px; color:#22304f; box-shadow:0 4px 14px rgba(0,0,0,.2); }
  .meta .chip b { color:#2455c6; }
  .cardstrip { margin:12px 18px 0; padding:12px 14px; border-radius:14px;
            background:rgba(255,255,255,.10); border:1px solid rgba(255,255,255,.18); }
  .cardstrip-title { font-size:13px; font-weight:700; color:#cfe0ff; margin-bottom:10px; }
  .cardstrip-row { display:flex; gap:10px; overflow-x:auto; padding-bottom:2px; }
  .cardface { flex:0 0 auto; width:96px; text-align:center; }
  .cardface img { width:96px; height:auto; border-radius:8px; display:block; cursor:zoom-in;
            box-shadow:0 4px 12px rgba(0,0,0,.35); background:#fff; transition:transform .15s; }
  .cardface img:hover { transform:translateY(-3px) scale(1.03); }
  .cardface span { display:block; margin-top:4px; font-size:11px; color:#9fb3e0; }
  #lightbox { position:fixed; inset:0; z-index:9999; display:none; align-items:center;
            justify-content:center; background:rgba(6,12,30,.86); cursor:zoom-out; padding:24px; }
  #lightbox.show { display:flex; }
  #lightbox img { max-width:92vw; max-height:88vh; border-radius:14px;
            box-shadow:0 24px 60px rgba(0,0,0,.6); background:#fff; }
  #lightbox .lb-close { position:fixed; top:18px; right:24px; color:#fff; font-size:34px;
            line-height:1; font-weight:300; cursor:pointer; opacity:.85; }
  .grid2 { display:flex; flex-wrap:wrap; gap:14px; padding:0 18px; }
  .grid2 > .section { flex:1 1 300px; }
  .section { background:rgba(255,255,255,.96); margin:14px 18px; border-radius:14px;
            padding:16px 18px; box-shadow:0 8px 24px rgba(0,0,0,.25); }
  .grid2 > .section { margin:14px 0; }
  .sec-head { display:flex; align-items:center; gap:10px; margin-bottom:12px; }
  .sec-no { font-size:20px; font-weight:900; color:#fff; background:#2455c6;
            width:38px; height:30px; display:flex; align-items:center; justify-content:center;
            border-radius:8px; letter-spacing:1px; }
  .sec-title { font-size:17px; font-weight:800; color:#16244a; }
  .sec-sub { font-size:12px; color:#7585a8; margin-left:4px; }
  .summary-box { background:linear-gradient(120deg,#fff6da,#ffe9b0); border:1px dashed #f0b400;
            border-radius:10px; padding:12px 14px; font-size:16px; font-weight:800; color:#a05a00;
            text-align:center; margin-top:12px; }
  .comment { font-size:13px; color:#46557d; margin-top:10px; line-height:1.6;
            background:#eef3ff; border-radius:8px; padding:8px 12px; }
  p { margin:8px 0; font-size:14px; line-height:1.85; color:#2b3a5e; }
  .story-body { font-family:"Source Han Serif SC","Noto Serif SC","Songti SC","STSong","SimSun",serif;
            font-size:15.5px; line-height:2.05; letter-spacing:.02em; color:#2a3550; }
  .story-body p { margin:0 0 13px; text-align:justify; text-justify:inter-ideograph; }
  .story-body p:first-of-type::first-letter { font-size:1.1em; font-weight:700; color:#2455c6; }
  .story-body::after { content:""; display:block; clear:both; }
  .illu { width:40%; max-width:240px; margin:2px 0 10px; }
  .illu-right { float:right; margin-left:18px; shape-outside:margin-box; shape-margin:10px; }
  .illu-left { float:left; margin-right:18px; shape-outside:margin-box; shape-margin:10px; }
  .illu img { width:100%; display:block; border-radius:12px; box-shadow:0 6px 18px rgba(0,0,0,.22); }
  .illu figcaption { margin-top:6px; font-size:12px; color:#7585a8; text-align:center;
            background:#eef3ff; border-radius:6px; padding:3px 8px; }
  @media (max-width:560px){ .illu{ width:46%; } }
  .tips { background:#eef8f0; border-radius:10px; padding:10px 14px 10px 30px; margin-top:12px; }
  .tips-title { font-weight:800; color:#1f8a4c; font-size:14px; margin:0 0 6px -16px; list-style:none; }
  .tips li { font-size:13px; color:#2b6b45; line-height:1.7; }
  .pact-item { display:flex; align-items:flex-start; gap:10px; font-size:14px; color:#2b3a5e;
            padding:8px 0; border-bottom:1px dashed #d9e1f5; line-height:1.6; }
  .pact-item:last-child { border-bottom:none; }
  .pact-no { flex:0 0 auto; width:22px; height:22px; border-radius:50%; background:#2455c6;
            color:#fff; font-size:12px; font-weight:800; display:flex; align-items:center;
            justify-content:center; margin-top:1px; }
  .takeaway { margin-top:12px; background:linear-gradient(120deg,#2455c6,#7a4bff); color:#fff;
            border-radius:10px; padding:12px 16px; font-size:15px; font-weight:800; text-align:center; }
  .footer { text-align:center; padding:20px 10px 14px; }
  .footer .big { font-size:30px; font-weight:900; letter-spacing:4px;
            background:linear-gradient(90deg,#ffd54a,#ff9d3c); -webkit-background-clip:text;
            background-clip:text; color:transparent; }
  .footer .en { font-size:13px; letter-spacing:3px; color:#9fb3e0; margin-top:4px; }
  .toolbar { max-width:720px; margin:16px auto 0; text-align:center; }
  .toolbar button { background:#ffd54a; color:#0b1b3a; border:none; border-radius:24px;
            padding:12px 26px; font-size:15px; font-weight:800; cursor:pointer; margin:0 6px;
            box-shadow:0 8px 20px rgba(0,0,0,.3); }
  .toolbar button.ghost { background:rgba(255,255,255,.15); color:#fff; }
  @media print { .toolbar { display:none; } body { background:#fff; } }
</style>
</head>
<body>
  <div id="poster">
    <div class="banner">
      <div class="logo">AI在5000天 · 数智免疫力 · 伍力全开</div>
      <h1>小伍5000天数智成长评估报告</h1>
      <div class="sub">桌游单轮复盘阅读版</div>
    </div>

    <div class="meta">
      <div class="chip"><b>闯关日期</b>　${E(dateStr)}</div>
      <div class="chip"><b>玩家</b>　${E(playersStr)}</div>
      <div class="chip"><b>成长阶段</b>　${E(phaseStr)}</div>
      <div class="chip"><b>卡牌版本</b>　${E(versionStr)}</div>
      <div class="chip"><b>本轮得分</b>　${E(String(data.session.finalScore))}</div>
    </div>

    ${cardStripHtml}

    <div class="section">
      <div class="sec-head"><span class="sec-no">01</span>
        <span class="sec-title">本轮总览</span><span class="sec-sub">小伍这轮经历了什么？</span></div>
      <p>${E(overview.experienced || "—")}</p>
      <div class="summary-box">${E(overview.summary || "")}</div>
    </div>

    <div class="grid2">
      <div class="section">
        <div class="sec-head"><span class="sec-no">02</span>
          <span class="sec-title">风险遭遇</span><span class="sec-sub">遇到了哪些风险？</span></div>
        ${riskSvg}
        <div class="comment">${E(s.riskComment || "")}</div>
      </div>
      <div class="section">
        <div class="sec-head"><span class="sec-no">03</span>
          <span class="sec-title">伍力召唤</span><span class="sec-sub">调动了哪些能力？</span></div>
        ${abilitySvg}
        <div class="comment">${E(s.abilityComment || "")}</div>
      </div>
    </div>

    <div class="section">
      <div class="sec-head"><span class="sec-no">04</span>
        <span class="sec-title">闯关故事</span><span class="sec-sub">小伍这一轮的数字成长故事</span></div>
      <div class="story-body">${storyBodyHtml}</div>
      ${tips.length ? `<ul class="tips"><li class="tips-title">🌱 小伍的成长小贴士</li>${tipsHtml}</ul>` : ""}
    </div>

    <div class="section">
      <div class="sec-head"><span class="sec-no">05</span>
        <span class="sec-title">数智行动公约</span><span class="sec-sub">把游戏经验带回真实生活</span></div>
      ${pactHtml || "<p>—</p>"}
      ${pact.takeaway ? `<div class="takeaway">📣 本轮带回家的一句话：${E(pact.takeaway)}</div>` : ""}
    </div>

    <div class="footer">
      <div class="big">伍力全开</div>
      <div class="en">GIVE ME FIVE · RAISE POWER UP</div>
    </div>
  </div>

  <div class="toolbar">
    <button id="export-btn">📥 导出为图片</button>
    <button class="ghost" onclick="window.print()">🖨️ 打印 / 存PDF</button>
  </div>

  <div id="lightbox"><span class="lb-close">×</span><img alt="卡面放大"/></div>

  <script>
    document.getElementById('export-btn').addEventListener('click', async function () {
      var btn = this; var old = btn.textContent; btn.textContent = '正在生成图片…'; btn.disabled = true;
      try {
        var node = document.getElementById('poster');
        var canvas = await html2canvas(node, { scale: 2, useCORS: true, backgroundColor: '#0b1b3a' });
        var link = document.createElement('a');
        link.download = '小伍数智成长复盘_' + new Date().toISOString().slice(0,10) + '.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
      } catch (e) {
        alert('导出失败：' + e.message);
      } finally {
        btn.textContent = old; btn.disabled = false;
      }
    });

    // 卡面点击放大悬浮窗
    (function () {
      var lb = document.getElementById('lightbox');
      var lbImg = lb.querySelector('img');
      document.querySelectorAll('.cf-img').forEach(function (im) {
        im.addEventListener('click', function () {
          lbImg.src = this.src;
          lbImg.alt = this.getAttribute('data-code') || '卡面';
          lb.classList.add('show');
        });
      });
      function close() { lb.classList.remove('show'); lbImg.src = ''; }
      lb.addEventListener('click', close);
      document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    })();
  </script>
</body>
</html>`;
  }

  function renderStatus(target, text) {
    if (!target) return;
    target.innerHTML = `<div style="padding: 12px 0; line-height: 1.6;">${escapeHtml(text)}</div>`;
  }

  async function uploadReport(html, markdown) {
    return api("api/upload/report", {
      method: "POST",
      body: { html, markdown }
    });
  }

  function renderResult(target, { structured, reportUrl }) {
    if (!target) return;
    const s = structured || {};
    const overview = s.overview || {};
    const summary = escapeHtml(overview.summary || "本轮复盘已生成");
    const experienced = escapeHtml(overview.experienced || "");
    const takeaway = s.pact && s.pact.takeaway ? escapeHtml(s.pact.takeaway) : "";

    target.innerHTML = `
      <div style="line-height: 1.7;">
        <h4 style="margin:0 0 8px;">🎉 复盘报告已生成</h4>
        <div style="background:linear-gradient(120deg,#fff6da,#ffe9b0);border:1px dashed #f0b400;border-radius:10px;padding:10px 14px;font-weight:800;color:#a05a00;text-align:center;">${summary}</div>
        ${experienced ? `<p style="margin:12px 0;color:#444;">${experienced}</p>` : ""}
        ${takeaway ? `<div style="margin:8px 0;background:#eef3ff;border-radius:8px;padding:8px 12px;color:#2455c6;font-weight:700;">📣 ${takeaway}</div>` : ""}
        <p style="color:#777;font-size:13px;margin-top:10px;">打开报告后可<strong>一键导出为图片</strong>，得到一张可分享的宣传海报。</p>
        <div style="display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap;">
          <button id="review-open-report" style="padding: 10px 18px; background: #2455c6; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-weight:700;">
            📄 查看 / 导出海报报告
          </button>
        </div>
      </div>
    `;

    const openBtn = document.getElementById("review-open-report");
    if (openBtn) openBtn.onclick = () => window.open(reportUrl, "_blank");
  }

  async function callLlm(prompt, { maxTokens = 1200, temperature = 0.7 } = {}) {
    const ret = await api("api/llm/story", {
      method: "POST",
      body: {
        prompt,
        max_tokens: maxTokens,
        temperature
      }
    });
    return ret.story || "";
  }

  // 调用文生图，返回 data URI；失败/未配置时返回空串（优雅降级，不阻断复盘）
  async function callImage(prompt, { size = "1024*1024" } = {}) {
    try {
      const ret = await api("api/llm/image", {
        method: "POST",
        body: { prompt, size }
      });
      return ret.dataUri || ret.url || "";
    } catch (e) {
      console.warn("生图失败，跳过插画:", e.message);
      return "";
    }
  }

  // 同源图片 URL → dataURI（卡面图与游戏页同源，可直接读，便于导出时自包含）
  async function imgUrlToDataUri(url) {
    try {
      const res = await fetch(url);
      if (!res.ok) return "";
      const blob = await res.blob();
      return await new Promise((resolve) => {
        const fr = new FileReader();
        fr.onloadend = () => resolve(fr.result || "");
        fr.onerror = () => resolve("");
        fr.readAsDataURL(blob);
      });
    } catch (_) {
      return "";
    }
  }

  // 收集本局所有玩过、且有卡面图的卡牌（按出牌顺序去重），抓成 dataURI
  async function collectCardFaces(cards) {
    if (typeof window.getCardImage !== "function") return [];
    const seen = new Set();
    const withImg = [];
    (cards || []).forEach((c) => {
      const code = c.cardCode;
      if (!code || seen.has(code)) return;
      const url = window.getCardImage(code);
      if (url) { seen.add(code); withImg.push({ code, url }); }
    });
    if (!withImg.length) return [];
    const faces = await Promise.all(withImg.map(async (p) => ({ code: p.code, dataUri: await imgUrlToDataUri(p.url) })));
    return faces.filter((f) => f.dataUri);
  }

  function parseJsonLoose(text) {
    if (!text) return null;
    const fenced = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
    const raw = fenced ? fenced[1] : text;
    try {
      return JSON.parse(raw);
    } catch (_) {
      const start = raw.indexOf("{");
      const end = raw.lastIndexOf("}");
      if (start >= 0 && end > start) {
        try { return JSON.parse(raw.slice(start, end + 1)); } catch (_) { }
      }
    }
    return null;
  }

  // 核心：生成结构化复盘 + 雷达数据 + 插画 → 海报 HTML
  async function generateReport(reviewData, onStatus) {
    const status = onStatus || (() => { });

    status("正在分析本轮闯关数据…");
    const structuredText = await callLlm(buildStructuredPrompt(reviewData), {
      maxTokens: 7000,
      temperature: 0.4
    });
    let structured = parseJsonLoose(structuredText) || {};

    // 容错：缺字段时给出兜底，保证报告不空
    structured.overview = structured.overview || {};
    structured.story = structured.story || {};
    structured.pact = structured.pact || {};

    const radars = computeRadars(reviewData, structured.riskRadar);

    // 多张具象场景插画，并行生成（每张约 10s，并行后整体仍≈一张的耗时）
    const scenes = pickScenes(structured);
    status(`正在生成闯关故事插画（${scenes.length} 张）…`);
    const dataUris = await Promise.all(
      scenes.map((sc) => callImage(buildScenePrompt(sc, structured), { size: "768*768" }))
    );
    const sceneImages = scenes
      .map((sc, i) => ({ caption: sc.caption || "", dataUri: dataUris[i] || "" }))
      .filter((s) => s.dataUri);

    // 真实卡面图（印刷版）：本局玩过的全放进去，可点击放大
    const cardFaces = await collectCardFaces(reviewData.cards);

    const reportHtml = buildReportHtml(structured, reviewData, radars, sceneImages, cardFaces);
    return { structured, radars, reportHtml };
  }

  async function openReview() {
    if (REVIEW_STATE.working) return;
    REVIEW_STATE.working = true;
    const target = document.getElementById("choice-display");

    try {
      if (!getToken()) {
        renderStatus(target, "请先登录后再复盘。");
        if (typeof window.openAuthModal === "function") {
          window.openAuthModal();
        }
        return;
      }

      renderStatus(target, "正在准备复盘数据...");
      let sessionId = getSessionId();
      if (!sessionId) {
        const last = await api("api/game/last-session");
        sessionId = last?.session?.id || null;
        if (sessionId) setSessionId(sessionId);
      }
      if (!sessionId) {
        renderStatus(target, "暂无可复盘的游戏记录。");
        return;
      }

      let sessionData;
      try {
        sessionData = await api(`api/game/session/${sessionId}`);
      } catch (e) {
        // sessionId 可能已失效，尝试 fallback 到最近一局
        setSessionId(null);
        const last = await api("api/game/last-session");
        sessionId = last?.session?.id || null;
        if (!sessionId) {
          renderStatus(target, "暂无可复盘的游戏记录。");
          return;
        }
        setSessionId(sessionId);
        sessionData = await api(`api/game/session/${sessionId}`);
      }
      const session = sessionData.session;
      const events = sessionData.events || [];
      if (!session) {
        renderStatus(target, "未找到对应的游戏记录。");
        return;
      }

      const reviewData = buildReviewData(session, events);

      // 从系统设置获取最低卡牌数，默认 7
      let minCards = 7;
      try {
        const settingsRes = await api("api/settings");
        if (settingsRes.ok && settingsRes.settings) {
          const row = settingsRes.settings.find(s => s.key === "REVIEW_MIN_CARDS");
          if (row) minCards = Math.max(1, parseInt(row.value, 10) || 7);
        }
      } catch (_) { /* 拿不到就用默认值 */ }

      // 检查数据是否足够
      if (reviewData.cards.length < minCards) {
        renderStatus(target, `数据不足：至少需要完成 ${minCards} 张卡牌才能生成有意义的复盘报告。当前只有 ${reviewData.cards.length} 张卡牌。`);
        return;
      }

      const { structured, reportHtml } = await generateReport(reviewData, (msg) => renderStatus(target, msg));

      // 上传到 OSS
      renderStatus(target, "正在上传复盘报告...");
      let reportUrl = "";
      try {
        const uploadRes = await uploadReport(reportHtml, null);
        if (uploadRes && uploadRes.ok) {
          reportUrl = uploadRes.htmlUrl;
          console.log("报告上传成功:", uploadRes);
        } else {
          throw new Error("上传失败");
        }
      } catch (e) {
        console.error("报告上传出错，回退到本地Blob:", e);
        const reportBlob = new Blob([reportHtml], { type: "text/html;charset=utf-8" });
        reportUrl = URL.createObjectURL(reportBlob);
      }

      renderResult(target, { structured, reportUrl });
    } catch (error) {
      renderStatus(target, `复盘生成失败：${error.message}`);
    } finally {
      REVIEW_STATE.working = false;
    }
  }

  async function recordEvent(type, payload) {
    const sessionId = getSessionId();
    if (!sessionId || !type) return;
    try {
      await api("api/game/event", {
        method: "POST",
        body: { sessionId, type, payload }
      });
    } catch (error) {
      console.warn("记录复盘事件失败:", error.message);
    }
  }

  async function finishSession({ finalScore = 0, endedAt = Date.now(), attributes = null, payload = {} } = {}) {
    const sessionId = getSessionId();
    if (!sessionId) return;
    try {
      const result = await api("api/game/finish", {
        method: "POST",
        body: { sessionId, finalScore, endedAt, attributes, payload }
      });
      await recordEvent("game_finish", { finalScore, endedAt, scoreRate: result?.finalScore, scoreDetails: result?.scoreDetails, payload });
    } catch (error) {
      console.warn("结束游戏记录失败:", error.message);
    }
  }

  // 导出API
  const moduleAPI = {
    openReview,
    recordEvent,
    finishSession,
    setSessionId,
    getSessionId,
    // 暴露内部能力（测试 / 复用）
    generateReport,
    buildReviewData,
    buildStructuredPrompt,
    computeRadars,
    collectCardFaces,
    buildReportHtml,
    // 测试页面兼容方法
    generateFullReport: async (gameHistory, gameAnalytics) => {
      const mockData = {
        session: { id: 1, startedAt: Date.now() - 360000, endedAt: Date.now(), finalScore: 18, players: null, location: null, mode: "standard" },
        cards: gameHistory || [],
        skills: gameAnalytics?.skillUsage || [],
        durationMs: 360000
      };
      const { structured, reportHtml } = await generateReport(mockData);
      return { structured, reportHtml };
    },
    extractInterestingData: async (gameHistory, gameAnalytics) => {
      const mockData = {
        session: { id: 1, startedAt: Date.now() - 360000, endedAt: Date.now(), finalScore: 18, players: null, location: null, mode: "standard" },
        cards: gameHistory || [],
        skills: gameAnalytics?.skillUsage || [],
        durationMs: 360000
      };
      const result = await callLlm(buildStructuredPrompt(mockData), { maxTokens: 2000, temperature: 0.6 });
      return parseJsonLoose(result) || { raw: result };
    },
    generateHTMLReport: (structured, gameStats) => {
      const mockData = {
        session: { id: 1, startedAt: Date.now() - 360000, endedAt: Date.now(), finalScore: gameStats?.finalScore || 18, players: null, location: null, mode: "standard" },
        cards: [],
        skills: [],
        durationMs: gameStats?.totalTime || 360000
      };
      return buildReportHtml(structured || {}, mockData, computeRadars(mockData), "");
    },
    downloadHTMLReport: (html) => {
      const blob = new Blob([html], { type: "text/html;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `game_review_${new Date().toISOString().slice(0, 10)}.html`;
      a.click();
      URL.revokeObjectURL(url);
    },
    callLLMAPI: callLlm,
    showProgress: (message, isComplete, isError) => {
      console.log(`Progress: ${message}`, { isComplete, isError });
    }
  };

  window.GameReview = moduleAPI;
  window.gameReviewModule = moduleAPI;
})();