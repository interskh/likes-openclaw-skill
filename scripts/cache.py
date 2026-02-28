"""Caching layer for Likes Training CLI.

Stores API responses as JSON in ~/.cache/likes-running/.
Activities/feedback older than FROZEN_DAYS are served from cache;
only gaps and recent data hit the API.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "likes-running"
FROZEN_DAYS = 7
CHUNK_DAYS = 30
PLAN_CHUNK_DAYS = 42
BACKFILL_EMPTY_STOP = 6


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _ts_to_date(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


class LikesCache:
    def __init__(self, cache_dir=None):
        self.dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self._stores = {}

    def _ensure_dir(self):
        self.dir.mkdir(parents=True, exist_ok=True)

    def _load(self, name):
        if name in self._stores:
            return self._stores[name]
        path = self.dir / f"{name}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {"records": {}, "_fetched_ranges": []}
        else:
            data = {"records": {}, "_fetched_ranges": []}
        if "records" not in data:
            data["records"] = {}
        if "_fetched_ranges" not in data:
            data["_fetched_ranges"] = []
        self._stores[name] = data
        return data

    def _save(self, name):
        self._ensure_dir()
        data = self._stores.get(name, {"records": {}, "_fetched_ranges": []})
        path = self.dir / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Merge helpers ────────────────────────────────────────────────

    def _merge_activities(self, items):
        store = self._load("activities")
        now = datetime.now(timezone.utc).isoformat()
        for item in items:
            key = str(item.get("id", ""))
            if not key:
                continue
            item["_cached_at"] = now
            store["records"][key] = item
        self._save("activities")

    def _merge_plans(self, items):
        store = self._load("plans")
        now = datetime.now(timezone.utc).isoformat()
        for item in items:
            key = item.get("start", "")
            if not key:
                continue
            item["_cached_at"] = now
            store["records"][key] = item
        self._save("plans")

    def _merge_feedback(self, items):
        store = self._load("feedback")
        now = datetime.now(timezone.utc).isoformat()
        for item in items:
            key = str(item.get("created_time", ""))
            if not key:
                continue
            item["_cached_at"] = now
            store["records"][key] = item
        self._save("feedback")

    # ── Query helpers ────────────────────────────────────────────────

    def _get_cached_activities(self, start, end):
        store = self._load("activities")
        start_dt = _parse_date(start)
        end_dt = _parse_date(end)
        results = []
        for rec in store["records"].values():
            sd = rec.get("sign_date")
            if sd is None:
                continue
            rec_date = datetime.fromtimestamp(int(sd), tz=timezone.utc)
            if start_dt <= rec_date <= end_dt + timedelta(days=1):
                results.append(rec)
        return results

    def _get_cached_plans(self, start, end):
        store = self._load("plans")
        results = []
        for rec in store["records"].values():
            s = rec.get("start", "")
            if not s:
                continue
            if start <= s <= end:
                results.append(rec)
        return results

    def _get_cached_feedback(self, start, end):
        store = self._load("feedback")
        start_dt = _parse_date(start)
        end_dt = _parse_date(end)
        results = []
        for rec in store["records"].values():
            ct = rec.get("created_time")
            if ct is None:
                continue
            rec_date = datetime.fromtimestamp(int(ct), tz=timezone.utc)
            if start_dt <= rec_date <= end_dt + timedelta(days=1):
                results.append(rec)
        return results

    # ── Gap detection ────────────────────────────────────────────────

    def _record_fetched_range(self, name, start, end):
        store = self._load(name)
        store["_fetched_ranges"].append([start, end])
        store["_fetched_ranges"] = self._merge_ranges(store["_fetched_ranges"])
        self._save(name)

    @staticmethod
    def _merge_ranges(ranges):
        if not ranges:
            return []
        sorted_r = sorted(ranges, key=lambda r: r[0])
        merged = [sorted_r[0]]
        for s, e in sorted_r[1:]:
            if s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        return merged

    def _detect_gaps(self, name, start, end):
        store = self._load(name)
        ranges = store.get("_fetched_ranges", [])
        if not ranges:
            return [[start, end]]
        gaps = []
        cursor = start
        for rs, re_ in sorted(ranges, key=lambda r: r[0]):
            if rs > cursor:
                gap_end = min(rs, end)
                if cursor < gap_end:
                    gaps.append([cursor, gap_end])
            cursor = max(cursor, re_)
        if cursor < end:
            gaps.append([cursor, end])
        return gaps

    # ── Cache-aware fetch: activities ────────────────────────────────

    def fetch_activities(self, api, start_date=None, end_date=None, limit=10, no_cache=False):
        import requests as req_lib

        today = _today()
        if end_date is None:
            end_date = today
        if start_date is None:
            start_date = (_parse_date(end_date) - timedelta(days=30)).strftime("%Y-%m-%d")

        if no_cache:
            try:
                data = api.get_activities(start_date=start_date, end_date=end_date, limit=limit)
                self._merge_activities(data.get("list", []))
                return data
            except req_lib.exceptions.RequestException:
                print("⚠ API unavailable and --no-cache set, cannot serve from cache", file=sys.stderr)
                return {"total": 0, "list": []}

        frozen_boundary = (_parse_date(today) - timedelta(days=FROZEN_DAYS)).strftime("%Y-%m-%d")
        all_records = []

        # Frozen portion: serve from cache, fetch only gaps
        if start_date < frozen_boundary:
            frozen_end = min(end_date, frozen_boundary)
            cached = self._get_cached_activities(start_date, frozen_end)
            all_records.extend(cached)

            gaps = self._detect_gaps("activities", start_date, frozen_end)
            for gap_start, gap_end in gaps:
                try:
                    data = api.get_activities(start_date=gap_start, end_date=gap_end, limit=100)
                    items = data.get("list", [])
                    self._merge_activities(items)
                    self._record_fetched_range("activities", gap_start, gap_end)
                    # Add newly fetched items (avoid dupes via ID)
                    existing_ids = {str(r.get("id")) for r in all_records}
                    for item in items:
                        if str(item.get("id")) not in existing_ids:
                            all_records.append(item)
                except req_lib.exceptions.RequestException:
                    print(f"⚠ Using cached data (API unavailable for {gap_start}..{gap_end})", file=sys.stderr)

        # Fresh portion: always hit API
        fresh_start = max(start_date, frozen_boundary)
        if fresh_start <= end_date:
            try:
                data = api.get_activities(start_date=fresh_start, end_date=end_date, limit=100)
                items = data.get("list", [])
                self._merge_activities(items)
                self._record_fetched_range("activities", fresh_start, end_date)
                existing_ids = {str(r.get("id")) for r in all_records}
                for item in items:
                    if str(item.get("id")) not in existing_ids:
                        all_records.append(item)
            except req_lib.exceptions.RequestException:
                print("⚠ Using cached data (API unavailable for recent window)", file=sys.stderr)
                cached = self._get_cached_activities(fresh_start, end_date)
                existing_ids = {str(r.get("id")) for r in all_records}
                for item in cached:
                    if str(item.get("id")) not in existing_ids:
                        all_records.append(item)

        # Dedup by ID, sort desc by sign_date, apply limit
        seen = {}
        for r in all_records:
            rid = str(r.get("id", id(r)))
            if rid not in seen:
                seen[rid] = r
        deduped = sorted(seen.values(), key=lambda r: int(r.get("sign_date", 0)), reverse=True)
        limited = deduped[:limit] if limit else deduped
        return {"total": len(deduped), "list": limited}

    # ── Cache-aware fetch: plans ─────────────────────────────────────

    def fetch_plans(self, api, start=None, game_id=None, no_cache=False):
        import requests as req_lib

        try:
            data = api.get_plans(start=start, game_id=game_id)
            self._merge_plans(data.get("rows", []))
            return data
        except req_lib.exceptions.RequestException:
            if no_cache:
                print("⚠ API unavailable and --no-cache set", file=sys.stderr)
                return {"total": 0, "rows": []}
            print("⚠ Using cached data (API unavailable)", file=sys.stderr)
            plan_start = start or _today()
            plan_end = (_parse_date(plan_start) + timedelta(days=PLAN_CHUNK_DAYS)).strftime("%Y-%m-%d")
            cached = self._get_cached_plans(plan_start, plan_end)
            cached.sort(key=lambda p: p.get("start", ""))
            return {"total": len(cached), "rows": cached}

    # ── Cache-aware fetch: feedback ──────────────────────────────────

    def fetch_feedback(self, api, start=None, end=None, no_cache=False):
        import requests as req_lib

        if not start or not end:
            return {"total": 0, "rows": []}

        if no_cache:
            try:
                data = api.get_feedback(start=start, end=end)
                self._merge_feedback(data.get("rows", []))
                return data
            except req_lib.exceptions.RequestException:
                print("⚠ API unavailable and --no-cache set", file=sys.stderr)
                return {"total": 0, "rows": []}

        today = _today()
        frozen_boundary = (_parse_date(today) - timedelta(days=FROZEN_DAYS)).strftime("%Y-%m-%d")
        all_records = []

        # Frozen portion
        if start < frozen_boundary:
            frozen_end = min(end, frozen_boundary)
            cached = self._get_cached_feedback(start, frozen_end)
            all_records.extend(cached)

            gaps = self._detect_gaps("feedback", start, frozen_end)
            for gap_start, gap_end in gaps:
                try:
                    data = api.get_feedback(start=gap_start, end=gap_end)
                    items = data.get("rows", [])
                    self._merge_feedback(items)
                    self._record_fetched_range("feedback", gap_start, gap_end)
                    existing_keys = {str(r.get("created_time")) for r in all_records}
                    for item in items:
                        if str(item.get("created_time")) not in existing_keys:
                            all_records.append(item)
                except req_lib.exceptions.RequestException:
                    print(f"⚠ Using cached data (API unavailable for {gap_start}..{gap_end})", file=sys.stderr)

        # Fresh portion
        fresh_start = max(start, frozen_boundary)
        if fresh_start <= end:
            try:
                data = api.get_feedback(start=fresh_start, end=end)
                items = data.get("rows", [])
                self._merge_feedback(items)
                self._record_fetched_range("feedback", fresh_start, end)
                existing_keys = {str(r.get("created_time")) for r in all_records}
                for item in items:
                    if str(item.get("created_time")) not in existing_keys:
                        all_records.append(item)
            except req_lib.exceptions.RequestException:
                print("⚠ Using cached data (API unavailable for recent window)", file=sys.stderr)
                cached = self._get_cached_feedback(fresh_start, end)
                existing_keys = {str(r.get("created_time")) for r in all_records}
                for item in cached:
                    if str(item.get("created_time")) not in existing_keys:
                        all_records.append(item)

        # Dedup by created_time, sort desc
        seen = {}
        for r in all_records:
            key = str(r.get("created_time", id(r)))
            if key not in seen:
                seen[key] = r
        deduped = sorted(seen.values(), key=lambda r: int(r.get("created_time", 0)), reverse=True)
        return {"total": len(deduped), "rows": deduped}

    # ── Backfill ─────────────────────────────────────────────────────

    def backfill(self, api, endpoint="activities", months=None):
        import requests as req_lib

        today_dt = _parse_date(_today())
        chunk_days = PLAN_CHUNK_DAYS if endpoint == "plans" else CHUNK_DAYS
        max_chunks = (months * 30 // chunk_days + 1) if months else 999
        empty_streak = 0

        for i in range(max_chunks):
            chunk_end_dt = today_dt - timedelta(days=i * chunk_days)
            chunk_start_dt = chunk_end_dt - timedelta(days=chunk_days)
            chunk_start = chunk_start_dt.strftime("%Y-%m-%d")
            chunk_end = chunk_end_dt.strftime("%Y-%m-%d")

            # Stop if we've gone past the requested range
            if months:
                earliest = (today_dt - timedelta(days=months * 30)).strftime("%Y-%m-%d")
                if chunk_end < earliest:
                    break

            print(f"  [{endpoint}] chunk {i + 1}: {chunk_start} to {chunk_end}...", end="", file=sys.stderr)

            try:
                if endpoint == "activities":
                    # Skip chunks fully covered by cache
                    gaps = self._detect_gaps("activities", chunk_start, chunk_end)
                    if not gaps:
                        print(" (cached)", file=sys.stderr)
                        continue
                    data = api.get_activities(start_date=chunk_start, end_date=chunk_end, limit=100)
                    items = data.get("list", [])
                    self._merge_activities(items)
                    self._record_fetched_range("activities", chunk_start, chunk_end)
                elif endpoint == "feedback":
                    gaps = self._detect_gaps("feedback", chunk_start, chunk_end)
                    if not gaps:
                        print(" (cached)", file=sys.stderr)
                        continue
                    data = api.get_feedback(start=chunk_start, end=chunk_end)
                    items = data.get("rows", [])
                    self._merge_feedback(items)
                    self._record_fetched_range("feedback", chunk_start, chunk_end)
                elif endpoint == "plans":
                    data = api.get_plans(start=chunk_start)
                    items = data.get("rows", [])
                    self._merge_plans(items)
                else:
                    print(f"\n⚠ Unknown endpoint: {endpoint}", file=sys.stderr)
                    return

                count = len(items)
                print(f" {count} records", file=sys.stderr)

                if count == 0:
                    empty_streak += 1
                else:
                    empty_streak = 0

                # Auto-stop after consecutive empty chunks (unless bounded by --months)
                if not months and empty_streak >= BACKFILL_EMPTY_STOP:
                    print(f"  Stopping: {BACKFILL_EMPTY_STOP} consecutive empty chunks", file=sys.stderr)
                    break

            except req_lib.exceptions.RequestException as e:
                print(f" ⚠ API error: {e}", file=sys.stderr)
                break

    # ── Cache management ─────────────────────────────────────────────

    def stats(self):
        result = {}
        for name in ("activities", "plans", "feedback"):
            path = self.dir / f"{name}.json"
            if not path.exists():
                result[name] = {"records": 0, "size_kb": 0, "date_range": None}
                continue
            store = self._load(name)
            records = store.get("records", {})
            size_kb = path.stat().st_size / 1024

            dates = []
            for rec in records.values():
                if name == "activities":
                    sd = rec.get("sign_date")
                    if sd:
                        dates.append(_ts_to_date(sd))
                elif name == "plans":
                    s = rec.get("start")
                    if s:
                        dates.append(s)
                elif name == "feedback":
                    ct = rec.get("created_time")
                    if ct:
                        dates.append(_ts_to_date(ct))

            date_range = f"{min(dates)} .. {max(dates)}" if dates else None
            result[name] = {"records": len(records), "size_kb": round(size_kb, 1), "date_range": date_range}
        return result

    def clear(self, before=None):
        if before is None:
            for name in ("activities", "plans", "feedback"):
                path = self.dir / f"{name}.json"
                if path.exists():
                    path.unlink()
            self._stores.clear()
            return

        before_dt = _parse_date(before)
        for name in ("activities", "plans", "feedback"):
            store = self._load(name)
            to_delete = []
            for key, rec in store["records"].items():
                if name == "activities":
                    sd = rec.get("sign_date")
                    if sd and datetime.fromtimestamp(int(sd), tz=timezone.utc) < before_dt:
                        to_delete.append(key)
                elif name == "plans":
                    s = rec.get("start")
                    if s and s < before:
                        to_delete.append(key)
                elif name == "feedback":
                    ct = rec.get("created_time")
                    if ct and datetime.fromtimestamp(int(ct), tz=timezone.utc) < before_dt:
                        to_delete.append(key)
            for key in to_delete:
                del store["records"][key]
            self._save(name)
