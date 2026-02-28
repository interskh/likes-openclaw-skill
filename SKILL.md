---
name: likes-running
description: "Interact with the Likes Training / 趣跑运动 platform (my.likes.com.cn). Use when the user wants to view training plans (查看训练计划), check running activities (查看跑步数据), read training feedback (查看训练反馈), or push workout plans to their Likes calendar (推送训练计划). Triggers on: likes, 趣跑, training plan, running data, workout calendar, 课表, 训练计划."
metadata: {"openclaw": {"emoji": "🏃", "requires": {"env": ["LIKES_API_KEY"], "anyBins": ["python3", "python"]}, "primaryEnv": "LIKES_API_KEY", "install": [{"id": "uv-requests", "kind": "uv", "package": "requests", "label": "Install requests library"}]}}
---

# Likes Running Skill / 趣跑运动技能

Interact with the Likes Training platform (趣跑运动, my.likes.com.cn) — a Chinese coach-athlete platform for structured running training that syncs with Garmin/Suunto/Coros watches.

## Commands

Use the bundled CLI at `scripts/likes.py`. Always run via the Bash tool.

### View Activities / 查看活动记录

Show recent training activities with distance, pace, heart rate, and TSS.

```bash
python {{skill_dir}}/scripts/likes.py activities --limit 5
python {{skill_dir}}/scripts/likes.py activities --start 2025-01-01 --end 2025-01-31
```

**⚠️ Rate limit:** The activity endpoint allows only 1 request per 2 minutes. Caching reduces this impact — see [Caching](#caching) below.

### View Plans / 查看训练计划

Show upcoming training plans from the calendar (42 days from start date).

```bash
python {{skill_dir}}/scripts/likes.py plans
python {{skill_dir}}/scripts/likes.py plans --start 2025-03-01
python {{skill_dir}}/scripts/likes.py plans --start 2025-03-01 --game-id 123
```

### View Feedback / 查看训练反馈

Show user training feedback for a date range (max 30 days). **Read-only (反馈仅支持读取).**

```bash
python {{skill_dir}}/scripts/likes.py feedback --start 2025-01-01 --end 2025-01-30
```

### Push Plans / 推送训练计划

Push a workout plan to the Likes calendar. Requires a workout code — see `references/workout-codes.md` for the full code syntax.

```bash
python {{skill_dir}}/scripts/likes.py push \
  --title "有氧间歇" \
  --start 2025-06-10 \
  --name "10min@(HRR+1.0~2.0);{5min@(HRR+3.0~4.0);1min@(rest)}x3;5min@(HRR+1.0~2.0)" \
  --weight q2 \
  --type i
```

**Push parameters:**

| Flag | Required | Description |
|------|----------|-------------|
| `--title` | Yes | Plan title, max 20 chars |
| `--start` | Yes | Date (YYYY-MM-DD) |
| `--name` | Yes | Workout code (see `references/workout-codes.md`) |
| `--weight` | No | q1 (high/red), q2 (mid/orange), q3 (low/green), xuanxiu (recovery/blue) |
| `--type` | No | Workout type: e, t, i, r, lsd, m, ft, com, ch, jili, etc. |
| `--sports` | No | 1=run 2=bike 3=strength 5=swim 254=other (default: 1) |
| `--description` | No | Notes |
| `--game-id` | No | Game/plan ID (default: 0) |

## Caching

The CLI caches API responses locally in `~/.cache/likes-running/`. Past activities and feedback are immutable, so historical data is served from cache without hitting the API. Data from the last 7 days is always fetched fresh.

### Bypass Cache

Add `--no-cache` before the subcommand to skip the cache and hit the API directly (results still update the cache):

```bash
python {{skill_dir}}/scripts/likes.py --no-cache activities --limit 5
```

### Cache Management

```bash
python {{skill_dir}}/scripts/likes.py cache stats
python {{skill_dir}}/scripts/likes.py cache clear
python {{skill_dir}}/scripts/likes.py cache clear --before 2025-01-01
```

### Backfill History

Pre-populate the cache by walking backwards through API history. Auto mode stops after 6 consecutive empty chunks; use `--months` to set an explicit range.

```bash
python {{skill_dir}}/scripts/likes.py backfill --endpoint activities
python {{skill_dir}}/scripts/likes.py backfill --endpoint activities --months 6
python {{skill_dir}}/scripts/likes.py backfill --endpoint feedback --months 3
python {{skill_dir}}/scripts/likes.py backfill --endpoint plans --months 2
```

### Fallback Behavior

When the API is unavailable, the CLI automatically serves stale cached data with a `⚠ Using cached data` warning. This makes the skill usable even when rate-limited or offline.

## Raw JSON Output

Add `--json` before the subcommand for raw API response:

```bash
python {{skill_dir}}/scripts/likes.py --json activities --limit 3
python {{skill_dir}}/scripts/likes.py --json plans
```

## Usage Notes

- **Date ranges**: Activity and feedback endpoints have a 30-day max range. The CLI handles single requests — for longer ranges, make multiple calls with different date windows.
- **Rate limits**: General API is 100 req/min. The `/activity` endpoint is limited to 1 request per 2 minutes — the CLI handles waiting automatically. Caching significantly reduces API calls for repeated queries.
- **Platform language**: The Likes platform is Chinese-native. CLI output uses Chinese labels (计划/实际训练/反馈) matching the platform.
- **Feedback is read-only**: There is no API endpoint to write or modify feedback.
- **Workout codes**: When pushing plans, refer to `references/workout-codes.md` in the skill directory for the full workout code syntax, intensity types, and examples.

## Trigger Examples

English:
- "Show my recent runs from Likes"
- "What's on my training plan this week?"
- "Push an interval workout to my Likes calendar for next Tuesday"
- "Show my training feedback for January"

中文:
- "看一下最近的跑步记录"
- "查看本周训练计划"
- "推送一个间歇训练到下周二"
- "查看一月份的训练反馈"
