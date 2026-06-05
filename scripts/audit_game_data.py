#!/usr/bin/env python3
"""
游戏数据审计脚本 — 挑选测试数据和不完整数据
用法:
  在服务器项目目录下执行:
    python3 scripts/audit_game_data.py                    # 仅报告
    python3 scripts/audit_game_data.py --flag              # 自动标记为 flagged
    python3 scripts/audit_game_data.py --trash             # 自动标记为 trash
    python3 scripts/audit_game_data.py --db /path/to/wqt.db  # 指定数据库路径

  从本地通过 SSH 执行:
    bash scripts/run_audit_remote.sh
"""

import sqlite3
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))

# ── 审计规则配置 ──────────────────────────────────────────────
RULES = {
    "test_location":  {"label": "测试地点",         "severity": "trash",   "desc": "地点含 test/smoke 或无意义短字符串"},
    "no_cards":       {"label": "无卡牌记录",       "severity": "trash",   "desc": "没有任何 card_choice 事件"},
    "too_few_cards":  {"label": "卡牌过少(<3张)",   "severity": "flagged", "desc": "card_choice 事件少于 3 条"},
    "too_short":      {"label": "时长过短(<30s)",   "severity": "trash",   "desc": "游戏时长不到 30 秒"},
    "short_duration": {"label": "时长偏短(<2min)",  "severity": "flagged", "desc": "游戏时长不到 2 分钟"},
    "no_end":         {"label": "未正常结束",       "severity": "flagged", "desc": "无 ended_at 且无 final_score"},
    "zero_score":     {"label": "零分",             "severity": "flagged", "desc": "final_score 为 0"},
    "test_player":    {"label": "测试玩家名",       "severity": "flagged", "desc": "玩家名含 test/测试/admin"},
    "rapid_fire":     {"label": "连续刷局",         "severity": "flagged", "desc": "同用户 5 分钟内开始多局"},
    "no_start_event": {"label": "无开始事件",       "severity": "flagged", "desc": "缺少 game_start 事件"},
}


def format_ts(ms):
    if not ms:
        return "-"
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000, tz=BEIJING_TZ)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(ms)


def format_duration(ms):
    if not ms or ms <= 0:
        return "-"
    s = int(ms) // 1000
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m"


def run_audit(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # ── 检测 status 列是否存在 ──
    cols = [r[1] for r in conn.execute("PRAGMA table_info(game_sessions)").fetchall()]
    has_status = "status" in cols

    # ── 拉取所有 session ──
    status_col = "gs.status" if has_status else "NULL as status"
    sessions = conn.execute(f"""
        SELECT
            gs.id, gs.user_id, gs.started_at, gs.ended_at,
            gs.final_score, gs.location, gs.players_json,
            gs.game_mode, {status_col},
            u.username, u.guardian_name, u.phone, u.role
        FROM game_sessions gs
        LEFT JOIN users u ON gs.user_id = u.id
        ORDER BY gs.id
    """).fetchall()

    # ── 预加载每个 session 的事件统计 ──
    event_stats = {}
    rows = conn.execute("""
        SELECT
            session_id,
            COUNT(*) AS total_events,
            SUM(CASE WHEN type = 'card_choice' THEN 1 ELSE 0 END) AS card_count,
            SUM(CASE WHEN type = 'game_start' THEN 1 ELSE 0 END) AS has_start,
            SUM(CASE WHEN type = 'game_end' THEN 1 ELSE 0 END) AS has_end,
            MAX(CASE WHEN type = 'card_choice' THEN ts END) AS last_card_ts
        FROM game_events
        GROUP BY session_id
    """).fetchall()
    for r in rows:
        event_stats[r["session_id"]] = dict(r)

    # ── 构建用户最近 session 列表用于"连续刷局"检测 ──
    user_sessions = {}
    for s in sessions:
        uid = s["user_id"]
        user_sessions.setdefault(uid, []).append(s)

    # ── 逐条审计 ──
    flagged_results = []  # (session_dict, [matched_rules])

    for s in sessions:
        sid = s["id"]
        matched = []
        stats = event_stats.get(sid, {})
        card_count = stats.get("card_count", 0) or 0
        has_start = stats.get("has_start", 0) or 0
        last_card_ts = stats.get("last_card_ts")

        # 计算时长
        started = s["started_at"]
        ended = s["ended_at"] or last_card_ts
        duration_ms = 0
        if started and ended:
            try:
                duration_ms = int(ended) - int(started)
            except:
                pass

        # Rule: test_location (地点含 test/smoke 或无意义短字符串)
        loc = (s["location"] or "").strip()
        loc_lower = loc.lower()
        test_loc_keywords = ["test", "smoke", "调试", "debug"]
        # 无意义短字符串：纯英文且长度 <=4 且不像真实地名
        is_junk_loc = (len(loc) <= 4 and loc.isascii() and loc.isalpha()) if loc else False
        if any(kw in loc_lower for kw in test_loc_keywords) or is_junk_loc:
            matched.append("test_location")

        # Rule: no_cards
        if card_count == 0:
            matched.append("no_cards")

        # Rule: too_few_cards (有卡但很少)
        elif card_count < 3:
            matched.append("too_few_cards")

        # Rule: too_short
        if duration_ms > 0 and duration_ms < 30_000:
            matched.append("too_short")
        elif duration_ms > 0 and duration_ms < 120_000:
            matched.append("short_duration")

        # Rule: no_end
        if not s["ended_at"] and not s["final_score"]:
            matched.append("no_end")

        # Rule: zero_score
        if s["final_score"] is not None and s["final_score"] == 0:
            matched.append("zero_score")

        # Rule: test_player
        players_str = (s["players_json"] or "").lower()
        guardian = (s["guardian_name"] or "").lower()
        username = (s["username"] or "").lower()
        test_keywords = ["test", "测试", "admin", "调试", "debug"]
        if any(kw in players_str or kw in guardian or kw in username for kw in test_keywords):
            matched.append("test_player")

        # Rule: rapid_fire (同用户 5 分钟内有另一局)
        if started:
            uid = s["user_id"]
            for other in user_sessions.get(uid, []):
                if other["id"] == sid:
                    continue
                other_start = other["started_at"]
                if other_start:
                    try:
                        gap = abs(int(started) - int(other_start))
                        if gap < 300_000 and gap > 0:  # 5 min
                            matched.append("rapid_fire")
                            break
                    except:
                        pass

        # Rule: no_start_event
        if has_start == 0 and card_count > 0:
            matched.append("no_start_event")

        if matched:
            # 计算最高严重级别
            max_severity = "flagged"
            if any(RULES[r]["severity"] == "trash" for r in matched):
                max_severity = "trash"

            flagged_results.append({
                "id": sid,
                "user_id": s["user_id"],
                "user_display": s["guardian_name"] or s["username"] or s["phone"] or f"uid:{s['user_id']}",
                "role": s["role"] or "watcher",
                "status": s["status"] or "-",
                "started_at": format_ts(started),
                "duration": format_duration(duration_ms),
                "card_count": card_count,
                "score": s["final_score"],
                "location": s["location"] or "-",
                "mode": s["game_mode"] or "-",
                "rules": matched,
                "severity": max_severity,
            })

    conn.close()
    return sessions, flagged_results


def print_report(all_sessions, results):
    total = len(all_sessions)
    flagged = [r for r in results if r["severity"] == "flagged"]
    trashed = [r for r in results if r["severity"] == "trash"]
    clean = total - len(results)

    print("=" * 80)
    print(f"  游戏数据审计报告")
    print(f"  生成时间: {datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    print("=" * 80)
    print(f"\n  总场次: {total}   干净: {clean}   可疑: {len(flagged)}   垃圾: {len(trashed)}")
    print()

    # ── 规则命中统计 ──
    rule_counts = {}
    for r in results:
        for rule in r["rules"]:
            rule_counts[rule] = rule_counts.get(rule, 0) + 1

    print("  规则命中统计:")
    print("  " + "-" * 50)
    for rule_id, count in sorted(rule_counts.items(), key=lambda x: -x[1]):
        info = RULES[rule_id]
        print(f"    [{info['severity']:7s}] {info['label']:15s}  {count:4d} 条  — {info['desc']}")
    print()

    # ── 垃圾数据明细 ──
    if trashed:
        print("-" * 80)
        print(f"  🗑️  建议直接丢弃 ({len(trashed)} 条)")
        print("-" * 80)
        _print_table(trashed)

    # ── 可疑数据明细 ──
    if flagged:
        print("-" * 80)
        print(f"  🟠 需要人工审核 ({len(flagged)} 条)")
        print("-" * 80)
        _print_table(flagged)


def _print_table(items):
    header = f"  {'ID':>5}  {'用户':12s}  {'角色':10s}  {'状态':14s}  {'开始时间':20s}  {'时长':8s}  {'卡牌':>4}  {'得分':>5}  {'命中规则'}"
    print(header)
    print("  " + "-" * (len(header) + 10))
    for r in items:
        rules_str = ", ".join(RULES[x]["label"] for x in r["rules"])
        score_str = str(r["score"]) if r["score"] is not None else "-"
        print(f"  {r['id']:>5}  {r['user_display']:12s}  {r['role']:10s}  {r['status']:14s}  {r['started_at']:20s}  {r['duration']:8s}  {r['card_count']:>4}  {score_str:>5}  {rules_str}")
    print()


def apply_status(db_path, results, target_severity):
    """将匹配的 session 标记为对应状态"""
    conn = sqlite3.connect(db_path)
    # 确保 status 列存在
    cols = [r[1] for r in conn.execute("PRAGMA table_info(game_sessions)").fetchall()]
    if "status" not in cols:
        conn.execute("ALTER TABLE game_sessions ADD COLUMN status TEXT DEFAULT 'active'")
        conn.commit()
    count = 0
    for r in results:
        if target_severity == "all" or r["severity"] == target_severity:
            new_status = r["severity"]
            conn.execute(
                "UPDATE game_sessions SET status = ? WHERE id = ?",
                (new_status, r["id"]),
            )
            count += 1
    conn.commit()
    conn.close()
    return count


def main():
    parser = argparse.ArgumentParser(description="游戏数据审计 — 挑选测试数据与不完整数据")
    parser.add_argument("--db", default="./data/wqt.db", help="数据库路径 (默认 ./data/wqt.db)")
    parser.add_argument("--flag", action="store_true", help="自动将可疑数据标记为 flagged")
    parser.add_argument("--trash", action="store_true", help="自动将垃圾数据标记为 trash")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    all_sessions, results = run_audit(args.db)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_report(all_sessions, results)

    if not results:
        print("  ✅ 没有发现异常数据！")
        return

    if args.flag or args.trash:
        if args.trash:
            n = apply_status(args.db, results, "trash")
            print(f"  ✅ 已将 {n} 条垃圾数据标记为 trash")
        if args.flag:
            n = apply_status(args.db, results, "flagged")
            print(f"  ✅ 已将 {n} 条可疑数据标记为 flagged")
    else:
        print("  💡 提示: 加 --flag 自动标记可疑, --trash 自动标记垃圾")
        print("          加 --json 输出 JSON 格式供程序处理")


if __name__ == "__main__":
    main()
