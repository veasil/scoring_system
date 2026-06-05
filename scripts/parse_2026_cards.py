# -*- coding: utf-8 -*-
"""
2026 精选卡牌 dry-run 解析器（只读，不写库）。
读 xlsx -> 按列名映射 -> 五力分归一化 -> 逐行校验 -> 输出 cards_2026.json + 校验报告。

用法：
  python scripts/parse_2026_cards.py "<xlsx路径>" <输出json路径>
"""
import sys, os, json, re

import openpyxl

# 五力维度 -> 别名（长别名在前，优先匹配）
DIM_ALIASES = {
    "安全力": ["安全力", "安全", "守", "安"],
    "脑波力": ["脑波力", "脑波", "波力", "脑", "波"],
    "实感力": ["实感力", "实感", "实"],
    "创心力": ["创心力", "创心", "创"],
    "沟通力": ["沟通力", "沟通", "沟"],
}
DIMS = list(DIM_ALIASES.keys())

# sheet 名 -> 规范 safety_type（与 admin-web SAFETY_TYPES 对齐）
SAFETY_MAP = {
    "身体安全": "身体安全",
    "心理安全": "心理安全",
    "社交安全": "社交安全",
    "经济安全": "经济安全",
    "数字权益安全": "数字权益",
}
PHASES = ["启蒙期", "成长期", "青春期"]


def norm(v):
    return "" if v is None else str(v).strip()


def parse_scores(raw):
    """把 '安全力-1 / 脑波力-1 / 实感力0 / 创心力0 / 沟通力0' 或缩写 '守-1 / 脑-1 ...'
    解析成 {安全力:-1,...}。返回 (dict, problems[])"""
    problems = []
    effects = {d: 0 for d in DIMS}
    seen = set()
    s = norm(raw)
    if not s:
        return effects, ["五力分为空"]
    # 多种分隔符：/ ／ 、 ; ； 换行 • · ・ 以及连续空格
    pieces = re.split(r"[／/、;；\n•·・]+", s)
    for p in pieces:
        p = p.strip()
        if not p:
            continue
        # 先按别名认维度（长别名优先），再从片段里抓第一个带符号整数
        dim = None
        for d, aliases in DIM_ALIASES.items():
            if any(p.startswith(a) for a in aliases):
                dim = d
                break
        if dim is None:
            problems.append(f"未知维度: {p!r}")
            continue
        m = re.search(r"[+\-﹣－]?\s*\d+", p)
        if not m:
            problems.append(f"无分值: {p!r}")
            continue
        num = m.group(0).replace(" ", "").replace("﹣", "-").replace("－", "-")
        val = int(num)
        if dim in seen and effects[dim] != val:
            problems.append(f"维度 {dim} 重复且分值冲突")
        effects[dim] = val
        seen.add(dim)
    missing = [d for d in DIMS if d not in seen]
    if missing:
        problems.append("缺维度: " + ",".join(missing))
    return effects, problems


def parse_reason_scores(raw):
    """从五力理由里抽分数：理由格式形如 '安全力 -1：...'，作为五力分缺失时的回填来源。"""
    s = norm(raw)
    found = {}
    for dim in DIMS:
        m = re.search(dim + r"\s*([+\-﹣－]?\s*\d+)\s*[：:]", s)
        if m:
            num = m.group(1).replace(" ", "").replace("﹣", "-").replace("－", "-")
            found[dim] = int(num)
    return found


def looks_like_reason(text):
    """结果列若混入了五力理由（P01 错位），通常含 '力 +N：' 或 '力-N：' 这种打分解释模式"""
    return bool(re.search(r"力\s*[+\-]?\d+\s*[：:]", norm(text)))


def main():
    xlsx = sys.argv[1] if len(sys.argv) > 1 else r"c:\Users\BibbTwigs\Downloads\2026精选卡牌 (1).xlsx"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "cards_2026.json"

    wb = openpyxl.load_workbook(xlsx, data_only=True)
    cards = []
    flags = []  # (code, level, msg)

    for ws in wb.worksheets:
        safety = SAFETY_MAP.get(ws.title.strip())
        if not safety:
            flags.append((ws.title, "WARN", f"sheet 名未识别为安全类型，跳过"))
            continue
        rows = list(ws.iter_rows(values_only=True))
        # 表头：第一行非空
        hdr = None
        hdr_idx = 0
        for i, r in enumerate(rows):
            if any(c is not None for c in r):
                hdr = r; hdr_idx = i; break
        # 列名 -> 索引
        col = {}
        for i, c in enumerate(hdr):
            name = norm(c)
            if name:
                col[name] = i
        col.setdefault("卡牌标题", 0)  # 身体安全 sheet 表头 col0 为空

        def cell(row, name):
            i = col.get(name)
            return norm(row[i]) if (i is not None and i < len(row)) else ""

        for r in rows[hdr_idx + 1:]:
            if not any(c is not None for c in r):
                continue
            code = cell(r, "卡牌编号")
            if not code or not code.startswith("2026"):
                continue  # 非卡牌数据行

            phase = cell(r, "主要适龄阶段")
            # 取第一个命中的标准阶段（单元格可能写 "启蒙期" 或带杂字）
            phase_norm = next((p for p in PHASES if p in phase), phase)
            if phase_norm not in PHASES:
                flags.append((code, "WARN", f"阶段无法归一: {phase!r}"))

            options = {}
            for opt in ("A", "B", "C"):
                text = cell(r, f"{opt}选项")
                reason = cell(r, f"{opt}五力理由")
                consequence = cell(r, f"{opt}结果")
                effects, probs = parse_scores(cell(r, f"{opt}五力分"))
                # 缺维度 -> 从五力理由回填（理由是权威打分说明）
                if any("缺维度" in pr for pr in probs):
                    rec = parse_reason_scores(reason)
                    filled = []
                    remaining = []
                    for pr in probs:
                        if pr.startswith("缺维度"):
                            still = []
                            for d in pr.replace("缺维度:", "").split(","):
                                d = d.strip()
                                if d in rec:
                                    effects[d] = rec[d]
                                    filled.append(f"{d}={rec[d]}")
                                else:
                                    still.append(d)
                            if still:
                                remaining.append("缺维度:" + ",".join(still))
                        else:
                            remaining.append(pr)
                    probs = remaining
                    if filled:
                        flags.append((code, "WARN", f"选项{opt} 五力分单元格残缺，已从理由回填: {','.join(filled)}"))
                for pr in probs:
                    flags.append((code, "ERR", f"选项{opt} 五力分: {pr}"))
                if not text:
                    flags.append((code, "ERR", f"选项{opt} 文本为空"))
                if not reason:
                    flags.append((code, "WARN", f"选项{opt} 五力理由为空"))
                if looks_like_reason(consequence):
                    flags.append((code, "WARN", f"选项{opt} 结果列疑似混入五力理由(列错位?)"))
                options[opt] = {
                    "text": text,
                    "consequence": consequence,
                    "attributeEffects": effects,
                    "reason": reason,
                }

            trainer = {
                "mentor_index": cell(r, "导师索引"),
                "trainer_notes": cell(r, "培训师机制点"),
                "extra_cases": cell(r, "补充案例"),
            }

            cards.append({
                "card_code": code,
                "workbench": "2026版",
                "safety_type": safety,
                "title": cell(r, "卡牌标题"),
                "subtopic": cell(r, "二级子议题"),
                "phase": phase_norm,
                "whitepaper_ref": cell(r, "白皮书章节"),
                "event": cell(r, "事件描述"),
                "guide_text": cell(r, "引导语"),
                "options": options,
                "trainer_material": trainer,
            })

    # 编号唯一性校验
    seen_codes = {}
    for c in cards:
        seen_codes.setdefault(c["card_code"], 0)
        seen_codes[c["card_code"]] += 1
    for code, n in seen_codes.items():
        if n > 1:
            flags.append((code, "ERR", f"卡牌编号重复 {n} 次"))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)

    # 报告写文件（控制台 GBK 编码会崩）
    from collections import Counter
    by_safety = Counter(c["safety_type"] for c in cards)
    by_phase = Counter(c["phase"] for c in cards)
    errs = [f for f in flags if f[1] == "ERR"]
    warns = [f for f in flags if f[1] == "WARN"]
    rep = []
    rep.append(f"解析完成：共 {len(cards)} 张卡，输出 -> {out_path}")
    rep.append("按安全类型: " + str(dict(by_safety)))
    rep.append("按阶段: " + str(dict(by_phase)))
    rep.append(f"\n校验：{len(errs)} 个 ERR，{len(warns)} 个 WARN")
    for code, lvl, msg in errs:
        rep.append(f"  [ERR] {code}: {msg}")
    for code, lvl, msg in warns:
        rep.append(f"  [WARN] {code}: {msg}")
    rep_path = os.path.join(os.path.dirname(out_path) or ".", "report_2026.txt")
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write("\n".join(rep))
    print("report ->", rep_path)


if __name__ == "__main__":
    main()
