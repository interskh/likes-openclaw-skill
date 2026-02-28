#!/usr/bin/env python3
"""Likes Training Platform CLI (趣跑运动).

Self-contained CLI for the Likes open API at my.likes.com.cn/api/open.
Reads LIKES_API_KEY from environment.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from cache import LikesCache

try:
    import requests
except ImportError:
    print("Error: 'requests' library required. Install with: uv pip install requests", file=sys.stderr)
    sys.exit(1)

# ── API Client ────────────────────────────────────────────────────────

BASE_URL = "https://my.likes.com.cn/api/open"

RATE_LIMITS = {
    "/activity": 121,
}
DEFAULT_COOLDOWN = 0.6


class LikesAPI:
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = api_key
        self._last_call: dict[str, float] = {}

    def _wait_for_rate_limit(self, path: str):
        cooldown = RATE_LIMITS.get(path, DEFAULT_COOLDOWN)
        last = self._last_call.get(path, 0)
        elapsed = time.time() - last
        if elapsed < cooldown:
            wait = cooldown - elapsed
            if wait > 5:
                print(f"  ⏳ rate limit: waiting {wait:.0f}s for {path}...", file=sys.stderr)
            time.sleep(wait)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        self._wait_for_rate_limit(path)
        max_retries = 3
        for attempt in range(max_retries):
            resp = self.session.request(method, f"{BASE_URL}{path}", **kwargs)
            self._last_call[path] = time.time()
            if resp.status_code == 429:
                wait = RATE_LIMITS.get(path, 60)
                if attempt < max_retries - 1:
                    print(f"  ⚠ 429 on {path}, retrying in {wait}s... ({attempt + 1}/{max_retries})", file=sys.stderr)
                    time.sleep(wait)
                    continue
            resp.raise_for_status()
            return resp.json()

    def get_activities(self, start_date=None, end_date=None, page=1, limit=100, order="desc"):
        params = {"page": page, "limit": limit, "order_by": "sign_date", "order": order}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._request("GET", "/activity", params=params)

    def get_plans(self, start=None, game_id=None):
        params = {}
        if start:
            params["start"] = start
        if game_id is not None:
            params["game_id"] = game_id
        return self._request("GET", "/plans", params=params)

    def get_feedback(self, start: str, end: str):
        return self._request("GET", "/feedback", params={"start": start, "end": end})

    def push_plans(self, plans: list[dict]):
        if len(plans) > 200:
            raise ValueError(f"Max 200 plans per push, got {len(plans)}")
        return self._request("POST", "/plans/push", json={"plans": plans})


# ── Formatters ────────────────────────────────────────────────────────

def fmt_ts(ts):
    """Format unix timestamp to YYYY-MM-DD."""
    if not ts:
        return "—"
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def fmt_duration(seconds):
    """Format seconds to H:MM:SS or MM:SS."""
    if not seconds:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fmt_pace(pace_val):
    """Format pace (seconds per km) to M'SS\"."""
    if not pace_val:
        return "—"
    pace_val = int(pace_val)
    m, s = divmod(pace_val, 60)
    return f"{m}'{s:02d}\""


WEIGHT_LABELS = {
    "q1": "🔴 高强度",
    "q2": "🟠 中强度",
    "q3": "🟢 低强度",
    "xuanxiu": "🔵 选修",
}

TYPE_LABELS = {
    "qingsong": "轻松跑", "xiuxi": "休息日", "e": "有氧", "lsd": "长距离",
    "m": "马拉松配速", "t": "乳酸阈", "i": "间歇", "r": "速度",
    "ft": "法特莱克", "com": "组合", "ch": "变速", "jili": "肌力",
    "max": "最大心率测试", "drift": "有氧稳定测试", "other": "其他",
}


# ── Subcommands ───────────────────────────────────────────────────────

def cmd_activities(api: LikesAPI, args, cache: LikesCache):
    data = cache.fetch_activities(
        api,
        start_date=args.start,
        end_date=args.end,
        limit=None,
        no_cache=args.no_cache,
    )
    if not args.all_types:
        data["list"] = [a for a in data["list"] if a.get("run_type") == 1]
    data["list"] = data["list"][:args.limit]
    data["total"] = len(data["list"])
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    print(f"活动记录 ({data['total']} total, showing {len(data['list'])})")
    print("─" * 60)
    for a in data["list"]:
        date_str = fmt_ts(a.get("sign_date"))
        km = a.get("run_km", 0)
        duration = fmt_duration(a.get("run_time"))
        pace = fmt_pace(a.get("run_pace"))
        hr = a.get("run_avg_hr", "—")
        cadence = a.get("run_avg_step_freq", "—")
        tss = a.get("tss", "—")
        title = a.get("title", "")
        print(f"  {date_str}  {km:.1f}km  {duration}  配速 {pace}  心率 {hr}  步频 {cadence}  TSS {tss}")
        if title:
            print(f"             {title}")


def cmd_plans(api: LikesAPI, args, cache: LikesCache):
    data = cache.fetch_plans(api, start=args.start, game_id=args.game_id, no_cache=args.no_cache)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    print(f"训练计划 ({data['total']} plans)")
    print("─" * 60)
    for p in data["rows"]:
        date_str = p.get("start", "—")
        title = p.get("title", "—")
        weight = p.get("weight", "")
        weight_label = WEIGHT_LABELS.get(weight.lower() if weight else "", weight)
        ptype = p.get("type", "")
        type_label = TYPE_LABELS.get(ptype, ptype)
        name = p.get("name", "")
        desc = p.get("description", "")
        print(f"  {date_str}  {weight_label}  {title}")
        if type_label:
            print(f"             类型: {type_label}")
        if name:
            print(f"             课表: {name}")
        if desc:
            print(f"             备注: {desc}")


def cmd_feedback(api: LikesAPI, args, cache: LikesCache):
    data = cache.fetch_feedback(api, start=args.start, end=args.end, no_cache=args.no_cache)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    print(f"训练反馈 ({data['total']} entries)")
    print("─" * 60)
    for f in data["rows"]:
        date_str = fmt_ts(f.get("created_time"))
        content = f.get("content", "—")
        plan_title = f.get("plan_title", "")
        img = f.get("img", "")
        print(f"  {date_str}  {plan_title}")
        print(f"             反馈: {content}")
        if img:
            print(f"             图片: {img}")


def cmd_push(api: LikesAPI, args):
    plan = {
        "title": args.title,
        "start": args.start,
        "name": args.name,
    }
    if args.weight:
        plan["weight"] = args.weight
    if args.type:
        plan["type"] = args.type
    if args.sports is not None:
        plan["sports"] = args.sports
    if args.description:
        plan["description"] = args.description
    if args.game_id is not None:
        plan["game_id"] = args.game_id

    data = api.push_plans([plan])
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    print(f"推送结果: {data.get('parse_ok', 0)} ok, {data.get('parse_failed', 0)} parse errors")
    for r in data.get("results", []):
        status = r.get("status", "?")
        title = r.get("title", "")
        msg = r.get("message", "")
        icon = "✅" if status == "ok" else "⚠️"
        print(f"  {icon} {title} [{status}] {msg}")


def cmd_cache(args, cache: LikesCache):
    if args.cache_action == "stats":
        stats = cache.stats()
        print("Cache statistics")
        print("─" * 60)
        for name, info in stats.items():
            dr = info["date_range"] or "empty"
            print(f"  {name:12s}  {info['records']:>5} records  {info['size_kb']:>7.1f} KB  {dr}")
    elif args.cache_action == "clear":
        cache.clear(before=args.before)
        if args.before:
            print(f"Cleared cache records before {args.before}")
        else:
            print("Cache cleared")


def cmd_backfill(api: LikesAPI, args, cache: LikesCache):
    endpoint = args.endpoint or "activities"
    months = args.months
    print(f"Backfilling {endpoint}" + (f" ({months} months)" if months else " (auto-stop after empty chunks)"), file=sys.stderr)
    cache.backfill(api, endpoint=endpoint, months=months)
    print("Done. Run 'cache stats' to see results.")


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Likes Training Platform CLI (趣跑运动)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--no-cache", action="store_true", help="Bypass cache, always hit API")
    sub = parser.add_subparsers(dest="command", required=True)

    # activities
    p_act = sub.add_parser("activities", help="查看活动记录 / View training activities")
    p_act.add_argument("--start", help="Start date (YYYY-MM-DD)")
    p_act.add_argument("--end", help="End date (YYYY-MM-DD)")
    p_act.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    p_act.add_argument("--all-types", action="store_true", dest="all_types", help="Include non-running activities (default: running only)")

    # plans
    p_plans = sub.add_parser("plans", help="查看训练计划 / View training plans")
    p_plans.add_argument("--start", help="Start date (YYYY-MM-DD)")
    p_plans.add_argument("--game-id", type=int, dest="game_id", help="Filter by game/plan ID")

    # feedback
    p_fb = sub.add_parser("feedback", help="查看训练反馈 / View training feedback (read-only)")
    p_fb.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    p_fb.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")

    # push
    p_push = sub.add_parser("push", help="推送训练计划 / Push a workout plan to calendar")
    p_push.add_argument("--title", required=True, help="Plan title (max 20 chars)")
    p_push.add_argument("--start", required=True, help="Date (YYYY-MM-DD)")
    p_push.add_argument("--name", required=True, help="Workout code (see references/workout-codes.md)")
    p_push.add_argument("--weight", choices=["q1", "q2", "q3", "xuanxiu"], help="Intensity: q1=high q2=mid q3=low xuanxiu=recovery")
    p_push.add_argument("--type", help="Workout type: e, t, i, r, lsd, m, ft, com, etc.")
    p_push.add_argument("--sports", type=int, help="1=run 2=bike 3=strength 5=swim 254=other")
    p_push.add_argument("--description", help="Notes/description")
    p_push.add_argument("--game-id", type=int, dest="game_id", help="Game/plan ID (default: 0)")

    # cache
    p_cache = sub.add_parser("cache", help="Manage local cache")
    p_cache_sub = p_cache.add_subparsers(dest="cache_action", required=True)
    p_cache_sub.add_parser("stats", help="Show cache statistics")
    p_cache_clear = p_cache_sub.add_parser("clear", help="Clear cache")
    p_cache_clear.add_argument("--before", help="Only clear records before this date (YYYY-MM-DD)")

    # backfill
    p_backfill = sub.add_parser("backfill", help="Backfill cache from API history")
    p_backfill.add_argument("--endpoint", choices=["activities", "feedback", "plans"], default="activities", help="Endpoint to backfill (default: activities)")
    p_backfill.add_argument("--months", type=int, help="Months to backfill (default: auto-stop after empty chunks)")

    args = parser.parse_args()
    cache = LikesCache()

    # cache subcommand doesn't need API key
    if args.command == "cache":
        cmd_cache(args, cache)
        return

    api_key = os.environ.get("LIKES_API_KEY")
    if not api_key:
        print("Error: LIKES_API_KEY environment variable not set.", file=sys.stderr)
        print("Get your key at: https://my.likes.com.cn (设置 → 申请 API Key)", file=sys.stderr)
        sys.exit(1)

    api = LikesAPI(api_key)

    try:
        if args.command == "activities":
            cmd_activities(api, args, cache)
        elif args.command == "plans":
            cmd_plans(api, args, cache)
        elif args.command == "feedback":
            cmd_feedback(api, args, cache)
        elif args.command == "push":
            cmd_push(api, args)
        elif args.command == "backfill":
            cmd_backfill(api, args, cache)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            print("Error: Invalid API key (401 Unauthorized).", file=sys.stderr)
        elif e.response is not None and e.response.status_code == 429:
            print("Error: Rate limited (429). The /activity endpoint allows 1 req per 2 minutes.", file=sys.stderr)
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
