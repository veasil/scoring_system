#!/usr/bin/env python3
"""
将本地 cards.db 中指定 safety_type 的卡牌同步到 staging（或任意远端）。

用法：
  python scripts/sync_cards_to_staging.py \
      --safety-type 经济安全 \
      --url https://www.ai5000days.com/staging \
      --secret-key <DEV_KEY> \
      [--keys 12,15,17] \
      [--db data/cards.db] \
      [--label "本地同步2026-04-08"] \
      [--dry-run]

逻辑：
  1. 从本地 cards.db 读 cards 表里指定 safety_type 的非 deleted 卡牌
  2. POST 到 <url>/api/admin/cards/bulk-upsert（按 key upsert，写入版本历史）
  3. 不发布、不影响远端其它 safety_type 的卡牌

发布到游戏需要后续在 admin panel 手动 release / 加入卡牌组。
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error


def load_local_cards(db_path: str, safety_type: str, keys_filter):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    sql = ("SELECT key, safety_type, phase, event, options_json "
           "FROM cards WHERE safety_type = ? AND (status IS NULL OR status != 'deleted')")
    params = [safety_type]
    if keys_filter:
        placeholders = ",".join("?" * len(keys_filter))
        sql += f" AND key IN ({placeholders})"
        params.extend(keys_filter)
    sql += " ORDER BY key ASC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    cards = []
    for r in rows:
        try:
            options = json.loads(r["options_json"])
        except Exception as e:
            print(f"⚠️  跳过 key={r['key']}：options_json 解析失败 {e}")
            continue
        cards.append({
            "key": r["key"],
            "safetyType": r["safety_type"],
            "phase": r["phase"],
            "event": r["event"],
            "options": options,
        })
    return cards


def post_bulk_upsert(base_url: str, secret_key: str, cards, label: str):
    url = base_url.rstrip("/") + "/api/admin/cards/bulk-upsert"
    payload = json.dumps({
        "secretKey": secret_key,
        "versionLabel": label,
        "status": "active",
        "cards": cards,
    }, ensure_ascii=False).encode("utf-8")

    # 优先使用 curl（更稳，避免某些 Python SSL 环境问题）
    if shutil.which("curl"):
        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".json") as f:
            f.write(payload)
            tmp_path = f.name
        try:
            proc = subprocess.run(
                ["curl", "-sS", "-X", "POST", url,
                 "-H", "Content-Type: application/json; charset=utf-8",
                 "--data-binary", "@" + tmp_path,
                 "-w", "__HTTP_STATUS__:%{http_code}"],
                capture_output=True, text=True, encoding="utf-8"
            )
        finally:
            os.unlink(tmp_path)
        out = (proc.stdout or "").strip()
        marker = "__HTTP_STATUS__:"
        idx = out.rfind(marker)
        if idx >= 0:
            body = out[:idx].rstrip()
            code = out[idx + len(marker):].strip()
            try:
                return int(code), body
            except ValueError:
                return -1, out
        return -1, (proc.stderr or out)

    # 回退：urllib
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--safety-type", required=True, help="例如 经济安全")
    ap.add_argument("--url", required=True, help="远端 base URL，例如 https://www.ai5000days.com/staging")
    ap.add_argument("--secret-key", required=True, help="DEV_KEY")
    ap.add_argument("--db", default="data/cards.db")
    ap.add_argument("--keys", default="", help="可选：逗号分隔的 key 列表，进一步过滤")
    ap.add_argument("--label", default="本地同步")
    ap.add_argument("--dry-run", action="store_true", help="只导出不上传")
    args = ap.parse_args()

    keys_filter = []
    if args.keys:
        keys_filter = [int(k.strip()) for k in args.keys.split(",") if k.strip()]

    cards = load_local_cards(args.db, args.safety_type, keys_filter)
    print(f"📦 本地匹配 {len(cards)} 张卡牌（safety_type={args.safety_type}）")
    for c in cards:
        print(f"   - key={c['key']:>3}  phase={c['phase'] or '-':<6}  event={c['event'][:40]}")

    if not cards:
        print("❌ 没有可同步的卡牌")
        sys.exit(1)

    if args.dry_run:
        print("\n🔍 dry-run 模式，未上传。预览 payload：")
        print(json.dumps(cards[:1], ensure_ascii=False, indent=2))
        return

    print(f"\n🚀 上传到 {args.url} ...")
    status, body = post_bulk_upsert(args.url, args.secret_key, cards, args.label)
    print(f"HTTP {status}")
    try:
        parsed = json.loads(body)
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
    except Exception:
        print(body)
    if status != 200:
        sys.exit(2)
    print("\n✅ 同步完成。请到 staging admin panel 发布这些卡牌（或加入卡牌组）。")


if __name__ == "__main__":
    main()
