# 🏃 Likes Running Skill / 趣跑运动技能

An [OpenClaw](https://github.com/anthropics/openclaw) skill for interacting with the [Likes Training platform](https://www.likes.com.cn/) (趣跑运动, my.likes.com.cn) — a Chinese coach-athlete platform for structured running training.

查看跑步数据、训练计划、训练反馈，以及推送课表到趣跑日历。

## Install / 安装

```bash
openclaw skills add https://github.com/interskh/likes-openclaw-skill
```

Or paste the repo URL directly in chat when Claude asks for a skill source.

## Setup / 配置

1. Get your API key from the Likes platform: log in to [my.likes.com.cn](https://my.likes.com.cn), go to **设置 → 申请 API Key**.

2. Set the key in your OpenClaw environment config, or export it:
   ```bash
   export LIKES_API_KEY=your_key_here
   ```

## What You Can Do / 功能

| Command | Description |
|---------|-------------|
| **activities** | View recent training activities with pace, HR, TSS / 查看活动记录 |
| **plans** | View upcoming training plans from calendar / 查看训练计划 |
| **feedback** | Read training feedback (read-only) / 查看训练反馈 |
| **push** | Push workout plans to your Likes calendar / 推送训练计划 |
| **cache stats** | Show cache statistics / 查看缓存状态 |
| **cache clear** | Clear cached data / 清除缓存 |
| **backfill** | Pre-populate cache from API history / 预填充历史缓存 |

## Example Conversations / 示例对话

**English:**
> "Show my last 5 runs from Likes"
>
> "What's on my training plan this week?"
>
> "Push an easy 10k run to next Monday"

**中文:**
> "看一下最近5次跑步记录"
>
> "查看本周训练计划"
>
> "推送一个轻松跑10公里到下周一"

## Direct CLI Usage / 命令行直接使用

```bash
# Recent activities
python scripts/likes.py activities --limit 5

# Upcoming plans
python scripts/likes.py plans

# Feedback for a date range
python scripts/likes.py feedback --start 2025-01-01 --end 2025-01-30

# Push a workout
python scripts/likes.py push --title "间歇训练" --start 2025-06-10 \
  --name "10min@(HRR+1.0~2.0);{1000m@(VDOT+4.0~5.0);2min@(rest)}x5;10min@(HRR+1.0~2.0)" \
  --weight q2 --type i

# Raw JSON output
python scripts/likes.py --json activities --limit 3
```

## Caching / 缓存

API responses are cached locally in `~/.cache/likes-running/`. Historical data (older than 7 days) is served from cache; recent data always fetches fresh. This dramatically reduces rate limit pain — cached queries return in ~100ms vs 2+ minutes.

```bash
# Backfill 6 months of history
python scripts/likes.py backfill --endpoint activities --months 6

# Check what's cached
python scripts/likes.py cache stats

# Bypass cache for a fresh call
python scripts/likes.py --no-cache activities --limit 5
```

## Rate Limits / 速率限制

- General: 100 requests/min
- `/activity` endpoint: 1 request per 2 minutes (the CLI handles waiting automatically, caching minimizes impact)
- Date ranges for activities and feedback: max 30 days per request

## License

MIT
