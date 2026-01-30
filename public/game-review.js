(function () {
  const REVIEW_STATE = {
    working: false
  };

  function getToken() {
    return localStorage.getItem("WQT_AUTH_TOKEN") || "";
  }

  function getSessionId() {
    const cached = Number(localStorage.getItem("WQT_SESSION_ID"));
    return Number.isFinite(cached) && cached > 0 ? cached : null;
  }

  function setSessionId(sessionId) {
    if (sessionId) {
      localStorage.setItem("WQT_SESSION_ID", String(sessionId));
    } else {
      localStorage.removeItem("WQT_SESSION_ID");
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
        phase: payload.phase || "",
        eventText: payload.eventText || "",
        choice: payload.choice || "",
        optionText: payload.optionText || "",
        consequence: payload.consequence || "",
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

    return {
      session: {
        id: session.id,
        startedAt,
        endedAt,
        finalScore,
        location: session.location,
        players,
        mode: session.game_mode,
        settings
      },
      cards,
      skills,
      durationMs
    };
  }

  function buildExtractPrompt(data) {
    const payload = {
      sessionId: data.session.id,
      location: data.session.location,
      players: data.session.players,
      mode: data.session.mode,
      startedAt: data.session.startedAt,
      endedAt: data.session.endedAt,
      duration: formatDurationMs(data.durationMs),
      finalScore: data.session.finalScore,
      cards: data.cards.map((card) => ({
        cardId: card.cardId,
        phase: card.phase,
        event: card.eventText,
        choice: card.choice,
        optionText: card.optionText,
        consequence: card.consequence,
        delta: card.attributeDelta,
        timeSpentSec: card.timeSpentSec,
        wasFailure: card.wasFailure,
        isCreativeOption: card.isCreativeOption
      })),
      skills: data.skills.map((skill) => ({
        skill: skill.skill,
        cardId: skill.cardId,
        optionD: skill.optionD,
        rescued: skill.rescued,
        attributeChange: skill.attributeChange,
        scoreChange: Object.values(skill.attributeChange || {}).reduce((sum, val) => sum + val, 0)
      }))
    };

    return [
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
      JSON.stringify(payload, null, 2),
      "```"
    ].join("\n");
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

  function buildStoryPromptPart1(data, extractMd) {
    const meta = [
      `地点: ${data.session.location || "未知"}`,
      `玩家: ${formatPlayers(data.session.players)}`,
      `模式: ${data.session.mode === 'standard' ? '标准版' : (data.session.mode === 'essence' ? '精华版' : data.session.mode || '未知')}`,
      `游戏开始: ${formatTs(data.session.startedAt) || "未知"}`,
      `游戏结束: ${formatTs(data.session.endedAt) || "未知"}`,
      `总时长: ${formatDurationMs(data.durationMs) || "未知"}`,
      `最终得分: ${data.session.finalScore}`
    ].join(" | ");

    return [
      "你是叙事写手。请基于“精炼数据”写这场游戏的复盘故事第一部分。",
      "要求：",
      "- 输出标准 Markdown。",
      "- 标题必须是：# 游戏复盘：回顾",
      "- 篇幅在 600-900 字之间（数据不足可略短，但不要少于 400 字）。",
      "- 叙述顺序尽量按卡牌顺序，穿插关键分数变化与决策原因。",
      "- 开头请简要提及本次游戏的背景信息（地点、玩家构成等）。",
      "- 不要写成纯清单。",
      "",
      `基础信息：${meta}`,
      "",
      "精炼数据：",
      extractMd
    ].join("\n");
  }

  function buildStoryPromptPart2(extractMd) {
    return [
      "你是叙事写手。请基于“精炼数据”输出第二部分：有意思的点与整体启示。",
      "要求：",
      "- 输出标准 Markdown。",
      "- 标题必须是：# 游戏复盘：有意思的点与启示",
      "- 篇幅在 400-700 字之间（数据不足可略短，但不要少于 300 字）。",
      "- 至少包含 3-6 个“有意思的点”、1-2 个整体趋势、1 条可行动的启示。",
      "- 可使用列表，但不要只堆叠要点。",
      "",
      "精炼数据：",
      extractMd
    ].join("\n");
  }

  function escapeHtml(input) {
    return String(input)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function buildReportHtml(markdown, data) {
    const title = "小伍的AI成长日记";
    const meta = [
      `复盘生成时间: ${new Date().toLocaleString()}`,
      `游戏开始: ${formatTs(data.session.startedAt) || "未知"}`,
      `游戏结束: ${formatTs(data.session.endedAt) || "未知"}`,
      `总时长: ${formatDurationMs(data.durationMs) || "未知"}`,
      `最终得分: ${data.session.finalScore}`
    ].join(" | ");

    return [
      "<!DOCTYPE html>",
      '<html lang="zh-CN">',
      "<head>",
      '  <meta charset="UTF-8" />',
      '  <meta name="viewport" content="width=device-width, initial-scale=1.0" />',
      `  <title>${escapeHtml(title)}</title>`,
      '  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>',
      "  <style>",
      "    body { font-family: 'Noto Serif SC', 'Songti SC', serif; margin: 40px auto; max-width: 800px; color: #1f1f1f; line-height: 1.6; }",
      "    h1 { font-size: 2.5rem; margin-bottom: 10px; color: #2c3e50; text-align: center; }",
      "    h2 { font-size: 1.8rem; color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 8px; margin-top: 2rem; }",
      "    h3 { font-size: 1.4rem; color: #2980b9; margin-top: 1.5rem; }",
      "    h4 { font-size: 1.2rem; color: #8e44ad; }",
      "    .meta { color: #7f8c8d; font-size: 14px; margin-bottom: 30px; text-align: center; padding: 15px; background: #ecf0f1; border-radius: 8px; }",
      "    .content { background: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }",
      "    p { margin: 1rem 0; }",
      "    ul, ol { margin: 1rem 0; padding-left: 2rem; }",
      "    li { margin: 0.5rem 0; }",
      "    blockquote { border-left: 4px solid #3498db; margin: 1.5rem 0; padding: 1rem 1.5rem; background: #f8f9fa; font-style: italic; }",
      "    code { background: #f1f2f6; padding: 2px 6px; border-radius: 4px; font-family: 'Courier New', monospace; }",
      "    pre { background: #2c3e50; color: #ecf0f1; padding: 1.5rem; border-radius: 8px; overflow-x: auto; }",
      "    strong { color: #e74c3c; }",
      "    em { color: #9b59b6; }",
      "    .highlight { background: linear-gradient(120deg, #a8e6cf 0%, #dcedc1 100%); padding: 2px 6px; border-radius: 4px; }",
      "    @media (max-width: 768px) { body { margin: 20px; } h1 { font-size: 2rem; } }",
      "  </style>",
      "</head>",
      "<body>",
      `  <h1>${escapeHtml(title)}</h1>`,
      `  <div class=\"meta\">${escapeHtml(meta)}</div>`,
      "  <div class=\"content\" id=\"markdown-content\"></div>",
      "  <script>",
      `    const markdown = ${JSON.stringify(markdown)};`,
      "    document.getElementById('markdown-content').innerHTML = marked.parse(markdown);",
      "  </script>",
      "</body>",
      "</html>"
    ].join("\n");
  }

  function renderStatus(target, text) {
    if (!target) return;
    target.innerHTML = `<div style="padding: 12px 0; line-height: 1.6;">${escapeHtml(text)}</div>`;
  }

  function renderResult(target, { markdown, reportUrl, extractMd }) {
    if (!target) return;
    const preview = escapeHtml(markdown);
    const extractPreview = extractMd ? escapeHtml(extractMd) : "";
    target.innerHTML = `
      <div style="max-height: 460px; overflow-y: auto; line-height: 1.7;">
        <h4>复盘报告已生成</h4>
        <div style="margin: 12px 0; white-space: pre-wrap; max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 4px;">${preview}</div>
        ${extractPreview
        ? `<details style="margin-top: 12px;">
                <summary style="cursor: pointer;">查看精炼数据</summary>
                <div style="margin-top: 8px; white-space: pre-wrap; max-height: 200px; overflow-y: auto; border: 1px solid #ddd; padding: 8px; border-radius: 4px;">${extractPreview}</div>
              </details>`
        : ""
      }
        <div style="display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap;">
          <button id="review-open-report" style="padding: 10px 16px; background: #2b6cb0; color: #fff; border: none; border-radius: 6px; cursor: pointer;">打开复盘报告</button>
          <button id="review-download-report" style="padding: 10px 16px; background: #2f855a; color: #fff; border: none; border-radius: 6px; cursor: pointer;">下载 HTML</button>
          <button id="review-download-md" style="padding: 10px 16px; background: #4a5568; color: #fff; border: none; border-radius: 6px; cursor: pointer;">下载 Markdown</button>
        </div>
      </div>
    `;

    const openBtn = document.getElementById("review-open-report");
    const downloadBtn = document.getElementById("review-download-report");
    const downloadMdBtn = document.getElementById("review-download-md");

    if (openBtn) openBtn.onclick = () => window.open(reportUrl, "_blank");
    if (downloadBtn) {
      downloadBtn.onclick = () => {
        const a = document.createElement("a");
        a.href = reportUrl;
        a.download = `game_review_${new Date().toISOString().slice(0, 10)}.html`;
        a.click();
      };
    }
    if (downloadMdBtn) {
      downloadMdBtn.onclick = () => {
        const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `game_review_${new Date().toISOString().slice(0, 10)}.md`;
        a.click();
        URL.revokeObjectURL(url);
      };
    }
  }

  async function callLlm(prompt, { maxTokens = 1200, temperature = 0.7 } = {}) {
    const ret = await api("/api/llm/story", {
      method: "POST",
      body: {
        prompt,
        max_tokens: maxTokens,
        temperature
      }
    });
    return ret.story || "";
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
        const last = await api("/api/game/last-session");
        sessionId = last?.session?.id || null;
        if (sessionId) setSessionId(sessionId);
      }
      if (!sessionId) {
        renderStatus(target, "暂无可复盘的游戏记录。");
        return;
      }

      const sessionData = await api(`/api/game/session/${sessionId}`);
      const session = sessionData.session;
      const events = sessionData.events || [];
      if (!session) {
        renderStatus(target, "未找到对应的游戏记录。");
        return;
      }

      const reviewData = buildReviewData(session, events);

      // 检查数据是否足够
      if (reviewData.cards.length < 7) {
        renderStatus(target, `数据不足：至少需要完成 7 张卡牌才能生成有意义的复盘报告。当前只有 ${reviewData.cards.length} 张卡牌。`);
        return;
      }

      renderStatus(target, "正在提取有意思的数据...");
      const extractPrompt = buildExtractPrompt(reviewData);
      const extractResult = await callLlm(extractPrompt, { maxTokens: 900, temperature: 0.2 });

      // 解析JSON结果
      let extractData;
      try {
        const jsonMatch = extractResult.match(/```json\s*([\s\S]*?)\s*```/);
        if (jsonMatch) {
          extractData = JSON.parse(jsonMatch[1]);
        } else {
          extractData = JSON.parse(extractResult);
        }
      } catch {
        // 如果解析失败，使用原始文本作为Markdown
        extractData = { markdown: extractResult };
      }

      const extractMd = extractData.markdown || JSON.stringify(extractData, null, 2);

      renderStatus(target, "正在生成复盘故事（第 1 部分）...");
      const part1 = await callLlm(buildStoryPromptPart1(reviewData, extractMd), {
        maxTokens: 1400,
        temperature: 0.7
      });

      renderStatus(target, "正在生成复盘故事（第 2 部分）...");
      const part2 = await callLlm(buildStoryPromptPart2(extractMd), {
        maxTokens: 1200,
        temperature: 0.7
      });

      const markdown = [part1.trim(), "", part2.trim()].join("\n\n").trim();
      const reportHtml = buildReportHtml(markdown, reviewData);
      const reportBlob = new Blob([reportHtml], { type: "text/html;charset=utf-8" });
      const reportUrl = URL.createObjectURL(reportBlob);

      renderResult(target, { markdown, reportUrl, extractMd });
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
      await api("/api/game/event", {
        method: "POST",
        body: { sessionId, type, payload }
      });
    } catch (error) {
      console.warn("记录复盘事件失败:", error.message);
    }
  }

  async function finishSession({ finalScore = 0, endedAt = Date.now(), payload = {} } = {}) {
    const sessionId = getSessionId();
    if (!sessionId) return;
    try {
      await api("/api/game/finish", {
        method: "POST",
        body: { sessionId, finalScore, endedAt, payload }
      });
      await recordEvent("game_finish", { finalScore, endedAt, payload });
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
    // 测试页面需要的方法
    generateFullReport: async (gameHistory, gameAnalytics) => {
      const mockData = {
        session: { id: 1, startedAt: Date.now() - 360000, endedAt: Date.now(), finalScore: 18 },
        cards: gameHistory || [],
        skills: gameAnalytics?.skillUsage || [],
        durationMs: 360000
      };

      const extractPrompt = buildExtractPrompt(mockData);
      const extractMd = await callLlm(extractPrompt, { maxTokens: 900, temperature: 0.2 });

      const part1 = await callLlm(buildStoryPromptPart1(mockData, extractMd), {
        maxTokens: 1400,
        temperature: 0.7
      });

      const part2 = await callLlm(buildStoryPromptPart2(extractMd), {
        maxTokens: 1200,
        temperature: 0.7
      });

      const markdown = [part1.trim(), "", part2.trim()].join("\n\n").trim();
      const reportHtml = buildReportHtml(markdown, mockData);

      return { markdown, reportHtml };
    },
    extractInterestingData: async (gameHistory, gameAnalytics) => {
      const mockData = {
        session: { id: 1, startedAt: Date.now() - 360000, endedAt: Date.now(), finalScore: 18 },
        cards: gameHistory || [],
        skills: gameAnalytics?.skillUsage || [],
        durationMs: 360000
      };

      const extractPrompt = buildExtractPrompt(mockData);
      const result = await callLlm(extractPrompt, { maxTokens: 900, temperature: 0.2 });

      try {
        const jsonMatch = result.match(/```json\s*([\s\S]*?)\s*```/);
        if (jsonMatch) {
          return JSON.parse(jsonMatch[1]);
        }
        return JSON.parse(result);
      } catch {
        return {
          keyMoments: [{ type: 'analysis', description: result.substring(0, 100) }],
          decisionPatterns: [],
          growthHighlights: [],
          reflectionPoints: []
        };
      }
    },
    generateStoryParts: async (analysisData, gameStats) => {
      const mockData = {
        session: { id: 1, startedAt: Date.now() - 360000, endedAt: Date.now(), finalScore: gameStats?.finalScore || 18 },
        cards: [],
        skills: [],
        durationMs: gameStats?.totalTime || 360000
      };

      const extractMd = JSON.stringify(analysisData, null, 2);

      const part1 = await callLlm(buildStoryPromptPart1(mockData, extractMd), {
        maxTokens: 1400,
        temperature: 0.7
      });

      const part2 = await callLlm(buildStoryPromptPart2(extractMd), {
        maxTokens: 1200,
        temperature: 0.7
      });

      return { part1, part2 };
    },
    generateHTMLReport: (storyParts, gameStats) => {
      const markdown = [storyParts.part1.trim(), "", storyParts.part2.trim()].join("\n\n").trim();
      const mockData = {
        session: { id: 1, startedAt: Date.now() - 360000, endedAt: Date.now(), finalScore: gameStats?.finalScore || 18 },
        cards: [],
        skills: [],
        durationMs: gameStats?.totalTime || 360000
      };

      return buildReportHtml(markdown, mockData);
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