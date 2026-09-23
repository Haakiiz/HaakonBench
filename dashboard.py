"""
dashboard.py — local web dashboard for HåkonBench.

    python dashboard.py              # http://127.0.0.1:8765 (opens your browser)
    python dashboard.py --demo       # fake API calls on a scratch copy of results/ — costs nothing

Browse every bucket (leaderboard, answers, the judge's verdict, grade history),
plan and start a new run with any subset of contestants / effort tier / web
search / grader, and watch the answers land live.

It drives the SAME functions as the CLI (resolve_run_dir, plan_contestants,
run_contestant, save_result, grade_run, save_grades), so buckets, caching and
grading behave exactly like `python haakonbench.py` — a run started here and
one started from the terminal are interchangeable.
"""

import argparse
import asyncio
import json
import os
import random
import re
import shutil
import sys
import tempfile
import threading
import time
import traceback
import uuid
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# haakonbench / llm_client use cwd-relative paths (results/, config.yaml,
# wow_reference.yaml), so pin the cwd before importing them.
os.chdir(ROOT)

from flask import Flask, Response, abort, jsonify, request, send_from_directory, stream_with_context

import haakonbench as hb

STATIC_DIR = ROOT / "dashboard"
PROVIDERS = ("anthropic", "openai", "google", "xai")
PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "CHATGPT_API_KEY",
    "google": "GOOGLE_API_KEY",
    "xai": "XAI_API_KEY",
}
DIMENSIONS = ("accuracy", "strategy", "creativity", "structure", "fidelity", "total")
DEMO = False

HB_GRADE_RE = re.compile(r"<!-- HB_GRADE\n(.*?)\n-->\s*", re.DOTALL)
KEY_RE = re.compile(r"^\s*-\s*\*\*([A-Z])\*\*\s*→\s*`([^`]+)`", re.MULTILINE)


# ── Reading buckets ────────────────────────────────────────────────────────

def base_dir() -> Path:
    # Read the global at call time: --demo points it at a scratch copy.
    return Path(hb.BASE_RESULTS_DIR)


def safe_run_dir(name: str) -> Path:
    """Resolve a run folder name, refusing anything outside results/."""
    base = base_dir().resolve()
    path = (base / name).resolve()
    if path.parent != base or not path.is_dir():
        abort(404, f"No run folder named {name!r}")
    return path


def split_label(label: str) -> tuple[str, str]:
    provider, _, model = label.partition("__")
    return provider, model


def answer_files(run_dir: Path) -> list[Path]:
    return [p for p in sorted(run_dir.glob("*.md")) if not p.name.startswith("_")]


def read_answer(path: Path) -> dict:
    """Status + body of one result file (new BODY_SEP and legacy formats)."""
    text = path.read_text(encoding="utf-8")
    if "**FAILED" in text[:400]:
        m = re.search(r"```\n(.*?)\n```", text, re.DOTALL)
        return {"status": "failed", "error": (m.group(1) if m else text).strip(), "body": ""}
    for sep in (hb.BODY_SEP, "\n---\n\n"):
        if sep in text:
            body = text.split(sep, 1)[1].strip()
            return {"status": "ok" if body else "empty", "error": None, "body": body}
    return {"status": "unknown", "error": "Unrecognized file format", "body": ""}


def clean_meta(meta: dict) -> dict:
    """HB_META values → JSON-safe (yaml parses `date` into a datetime)."""
    return {k: (v if isinstance(v, (int, float, str, bool)) or v is None else str(v))
            for k, v in (meta or {}).items()}


def parse_score_rows(verdict: str) -> list[dict]:
    """Every scored row of the judge's first markdown table that has a Total
    column. More tolerant than hb.parse_grade_totals: also keeps the five
    dimensions and the one-line verdict."""
    header: list[str] | None = None
    rows: list[dict] = []
    for line in verdict.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            if rows:
                break                      # first scored table is over
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if header is None:
            low = [c.lower() for c in cells]
            if any("total" in c for c in low):
                header = low
            continue
        if not "".join(cells).strip("-: "):
            continue                       # |---|---| separator
        letter = cells[0].strip("*`_ ")
        if not re.fullmatch(r"[A-Z]", letter):
            continue
        row: dict = {"letter": letter}
        for i, h in enumerate(header[1:], start=1):
            if i >= len(cells):
                break
            dim = next((d for d in DIMENSIONS if d in h), None)
            if dim:
                m = re.search(r"\d+(?:\.\d+)?", cells[i])
                row[dim] = float(m.group()) if m else None
            elif "verdict" in h:
                row["verdict"] = cells[i].strip("*_ ")
        rows.append(row)
    return rows


def parse_grades(text: str) -> dict:
    header = {}
    m = HB_GRADE_RE.search(text)
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            header[k.strip()] = v.strip()
    key = dict(KEY_RE.findall(text))
    rows = parse_score_rows(text)
    for r in rows:
        r["label"] = key.get(r["letter"])
    return {"header": header, "key": key, "rows": rows}


def strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->\s*", "", text, flags=re.DOTALL)


def leaderboard(run_dir: Path, grades_text: str | None = None) -> dict | None:
    """The latest verdict joined with each answer's HB_META (time / tokens)."""
    path = run_dir / "_grades.md"
    if grades_text is None:
        if not path.exists():
            return None
        grades_text = path.read_text(encoding="utf-8")
    g = parse_grades(grades_text)
    rows = []
    for r in g["rows"]:
        label = r.get("label")
        provider, model = split_label(label) if label else ("?", r["letter"])
        rows.append({**r, "provider": provider, "model": model,
                     "meta": clean_meta(hb.load_result_meta(run_dir, label)) if label else {}})
    rows.sort(key=lambda r: (r.get("total") is not None, r.get("total") or 0), reverse=True)
    return {"header": g["header"], "rows": rows, "graded_labels": sorted(g["key"].values())}


def summarize_run(run_dir: Path) -> dict:
    manifest = hb.read_manifest(run_dir)
    ok, failed = [], []
    for f in answer_files(run_dir):
        (ok if hb.has_valid_result(run_dir, f.stem) else failed).append(f.stem)
    board = leaderboard(run_dir)
    winner = None
    ungraded: list[str] = []
    if board:
        if board["rows"] and board["rows"][0].get("total") is not None:
            w = board["rows"][0]
            winner = {"provider": w["provider"], "model": w["model"], "total": w["total"]}
        if board["graded_labels"]:
            ungraded = sorted(set(ok) - set(board["graded_labels"]))
    header = (board or {}).get("header", {})
    graded = hb.latest_grade_date(run_dir)
    if graded == "yes":                      # legacy: _grades.md but no dated history
        graded = time.strftime("%Y-%m-%d", time.localtime((run_dir / "_grades.md").stat().st_mtime))
    return {
        "name": run_dir.name,
        "legacy": not manifest,
        "manifest": manifest,
        "current_prompt": manifest.get("prompt_sha") == hb.prompt_sha(),
        "ok": len(ok),
        "failed": len(failed),
        "graded": graded,
        "grader": header.get("grader"),
        "graded_at": header.get("graded"),
        "winner": winner,
        "ungraded": ungraded,
        "mtime": max((p.stat().st_mtime for p in run_dir.iterdir()), default=run_dir.stat().st_mtime),
    }


def all_runs() -> list[dict]:
    base = base_dir()
    base.mkdir(exist_ok=True)
    runs = [summarize_run(p) for p in base.iterdir() if p.is_dir()]
    runs.sort(key=lambda r: r["mtime"], reverse=True)
    return runs


def grade_history(run_dir: Path) -> list[dict]:
    hist = run_dir / hb.GRADES_DIR
    if not hist.is_dir():
        return []
    out = []
    for f in sorted(hist.glob("*.md"), reverse=True):
        m = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{6})_(.+)\.md$", f.name)
        grader = m.group(3).replace("__", "/", 1) if m else f.stem
        when = f"{m.group(1)} {m.group(2)[:2]}:{m.group(2)[2:4]}" if m else ""
        out.append({"file": f.name, "grader": grader, "when": when})
    return out


# ── Planning (the dry-run) ─────────────────────────────────────────────────

def parse_models(raw) -> list[tuple[str, str]]:
    pairs = []
    for item in raw or []:
        spec = item if isinstance(item, str) else f"{item.get('provider')}/{item.get('model')}"
        provider, _, model = spec.partition("/")
        provider, model = provider.strip(), model.strip()
        if provider not in PROVIDERS or not model:
            abort(400, f"Bad model spec {spec!r} — expected provider/model with provider in {PROVIDERS}")
        if (provider, model) not in pairs:
            pairs.append((provider, model))
    return pairs


def parse_run_params(body: dict) -> dict:
    effort = body.get("effort", hb.DEFAULT_EFFORT)
    if effort not in hb.TIERS:
        abort(400, f"effort must be one of {hb.TIERS}")
    timeout = body.get("timeout")
    try:
        timeout = float(timeout) if timeout not in (None, "", 0) else None
    except (TypeError, ValueError):
        abort(400, "timeout must be a number of seconds")
    grader = (body.get("grader") or f"{hb.GRADER_PROVIDER}/{hb.GRADER_MODEL}").strip()
    gp, _, gm = grader.partition("/")
    if gp not in PROVIDERS or not gm:
        abort(400, f"grader must be provider/model, got {grader!r}")
    return {
        "models": parse_models(body.get("models")),
        "effort": effort,
        "web_search": bool(body.get("web_search")),
        "tag": (body.get("tag") or "").strip() or None,
        "refresh": bool(body.get("refresh")),
        "timeout": timeout,
        "grade": body.get("grade", True) is not False,
        "grader": (gp, gm),
    }


def build_plan(p: dict) -> dict:
    """What a run with these settings would do — calls nothing, writes nothing."""
    cfg = hb.run_config(p["effort"], p["web_search"], p["tag"])
    name = hb.bucket_name(cfg)
    run_dir = base_dir() / name
    exists = run_dir.is_dir()
    conflicts = hb.manifest_conflicts(hb.read_manifest(run_dir), cfg) if exists else []
    to_call, reused = hb.plan_contestants(run_dir, p["models"], refresh=p["refresh"])

    def knob(provider, model):
        max_tokens, level = hb.resolve_effort(provider, model, p["effort"])
        return {"max_tokens": max_tokens, "knob": level}

    call_rows = [{"provider": pr, "model": m, "label": hb.slug(pr, m), **knob(pr, m)} for pr, m in to_call]
    reuse_rows = []
    for pr, m in reused:
        meta = hb.load_result_meta(run_dir, hb.slug(pr, m))
        reuse_rows.append({"provider": pr, "model": m, "label": hb.slug(pr, m),
                           "date": str(meta.get("date", ""))[:10] or None})
    selected = {r["label"] for r in call_rows + reuse_rows}
    others = []
    if exists:
        others = [f.stem for f in answer_files(run_dir)
                  if f.stem not in selected and hb.has_valid_result(run_dir, f.stem)]
    return {
        "bucket": name,
        "exists": exists,
        "conflicts": conflicts,
        "to_call": call_rows,
        "reused": reuse_rows,
        "others": others,
        "grade_count": len(call_rows) + len(reuse_rows) + len(others),
    }


# ── Jobs (one run or regrade at a time, in a background thread) ────────────

class Job:
    def __init__(self, kind: str, params: dict):
        self.id = uuid.uuid4().hex[:10]
        self.kind = kind                      # "run" | "regrade"
        self.params = params
        self.status = "starting"              # starting|running|grading|done|error|cancelled
        self.bucket: str | None = params.get("run")
        self.models: dict[str, dict] = {}
        self.grading: dict | None = None
        self.board: dict | None = None
        self.error: str | None = None
        self.logs: list[dict] = []
        self.started = time.time()
        self.finished: float | None = None
        self.version = 0
        self.cond = threading.Condition()
        self.cancel_requested = False
        self.loop: asyncio.AbstractEventLoop | None = None
        self.tasks: set[asyncio.Task] = set()
        self.thread = threading.Thread(target=self._thread_main, name=f"hb-job-{self.id}", daemon=True)
        self._partial = ""

    # -- state ------------------------------------------------------------
    def _bump(self):
        self.version += 1
        self.cond.notify_all()

    def update(self, **fields):
        with self.cond:
            for k, v in fields.items():
                setattr(self, k, v)
            self._bump()

    def set_model(self, label: str, **fields):
        with self.cond:
            self.models.setdefault(label, {}).update(fields)
            self._bump()

    def set_grading(self, **fields):
        with self.cond:
            self.grading = {**(self.grading or {}), **fields}
            self._bump()

    def log(self, msg: str):
        with self.cond:
            self.logs.append({"t": time.time(), "msg": msg})
            del self.logs[:-500]
            self._bump()

    def capture(self, s: str):
        """Lines printed by haakonbench on this job's thread (grader retries etc.)."""
        self._partial += s
        while "\n" in self._partial:
            line, self._partial = self._partial.split("\n", 1)
            if line.strip():
                self.log(line.rstrip())

    @property
    def active(self) -> bool:
        return self.finished is None

    def snapshot(self) -> dict:
        p = self.params
        return {
            "id": self.id, "kind": self.kind, "status": self.status, "bucket": self.bucket,
            "active": self.active, "started": self.started, "finished": self.finished,
            "now": time.time(), "error": self.error, "cancel_requested": self.cancel_requested,
            "params": {
                "effort": p.get("effort"), "web_search": p.get("web_search"), "tag": p.get("tag"),
                "refresh": p.get("refresh"), "timeout": p.get("timeout"), "grade": p.get("grade"),
                "grader": "/".join(p["grader"]) if p.get("grader") else None,
            },
            "models": list(self.models.values()),
            "grading": self.grading, "board": self.board, "logs": self.logs[-300:],
        }

    def snapshot_json(self) -> tuple[int, str, bool]:
        with self.cond:
            return self.version, json.dumps(self.snapshot()), self.active

    # -- control ----------------------------------------------------------
    def start(self):
        self.thread.start()

    def cancel(self):
        with self.cond:
            self.cancel_requested = True
            self._bump()
        loop = self.loop
        if loop and not loop.is_closed():
            loop.call_soon_threadsafe(self._cancel_tasks)

    def _cancel_tasks(self):
        for t in list(self.tasks):
            if not t.done():
                t.cancel()

    # -- execution --------------------------------------------------------
    def _thread_main(self):
        try:
            asyncio.run(self._main())
        except BaseException as e:           # never let the thread die silently
            self.update(status="error", error=f"{type(e).__name__}: {e}", finished=time.time())

    async def _main(self):
        self.loop = asyncio.get_running_loop()
        try:
            if self.kind == "run":
                await self._execute_run()
            else:
                await self._execute_regrade()
        except SystemExit as e:              # hb raises SystemExit for config problems
            self.update(status="error", error=str(e).strip())
        except Exception as e:
            self.log(traceback.format_exc())
            self.update(status="error", error=f"{type(e).__name__}: {e}")
        finally:
            with self.cond:
                if self.cancel_requested and self.status not in ("error",):
                    self.status = "cancelled"
                elif self.status not in ("error", "cancelled"):
                    self.status = "done"
                self.finished = time.time()
                self._bump()

    async def _execute_run(self):
        p = self.params
        cfg = hb.run_config(p["effort"], p["web_search"], p["tag"])
        run_dir, is_new = hb.resolve_run_dir(None, cfg, creating=True, check_config=True, force=False)
        to_call, reused = hb.plan_contestants(run_dir, p["models"], refresh=p["refresh"])
        hb.write_manifest(run_dir, cfg)
        hb.write_prompt_copy(run_dir)
        with self.cond:
            self.bucket = run_dir.name
            for provider, model in reused:
                label = hb.slug(provider, model)
                meta = clean_meta(hb.load_result_meta(run_dir, label))
                self.models[label] = {"label": label, "provider": provider, "model": model,
                                      "state": "cached", "meta": meta}
            for provider, model in to_call:
                label = hb.slug(provider, model)
                _, knob = hb.resolve_effort(provider, model, p["effort"])
                self.models[label] = {"label": label, "provider": provider, "model": model,
                                      "state": "queued", "knob": knob}
            self.status = "running"
            self._bump()
        self.log(f"Bucket {run_dir.name} ({'new' if is_new else 'existing'}): "
                 f"{len(to_call)} to call, {len(reused)} reused")

        if to_call and not self.cancel_requested:
            tasks: dict[asyncio.Task, str] = {}
            for provider, model in to_call:
                label = hb.slug(provider, model)
                task = asyncio.create_task(
                    hb.run_contestant(provider, model, p["effort"], p["timeout"], p["web_search"]))
                tasks[task] = label
                self.set_model(label, state="running", started=time.time())
            self.tasks = set(tasks)
            pending = set(tasks)
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    label = tasks[task]
                    if task.cancelled():
                        # Nothing written, so the next run treats it as missing.
                        self.set_model(label, state="cancelled", finished=time.time())
                        self.log(f"  CANCELLED {label}")
                        continue
                    label, response, secs, err, usage = task.result()
                    msg = hb.save_result(run_dir, label, response, secs, err, usage,
                                         effort=p["effort"], web_search=p["web_search"])
                    self.log(msg.strip())
                    state = "failed" if err else ("empty" if not response.strip() else "done")
                    self.set_model(label, state=state, finished=time.time(), secs=secs, error=err,
                                   chars=len(response or ""),
                                   meta=clean_meta(hb.load_result_meta(run_dir, label)))
            self.tasks = set()

        if self.cancel_requested:
            self.log("Run cancelled — finished answers are saved; grading skipped.")
            return
        if p["grade"]:
            await self._grade(run_dir, *p["grader"])
        else:
            self.log("Grading skipped (not requested).")

    async def _execute_regrade(self):
        run_dir = base_dir() / self.params["run"]
        self.update(bucket=run_dir.name)
        await self._grade(run_dir, *self.params["grader"])

    async def _grade(self, run_dir: Path, gp: str, gm: str):
        n = len(hb.load_successful_results(run_dir))
        if n == 0:
            self.set_grading(state="skipped", grader=f"{gp}/{gm}", reason="No successful answers to grade.")
            return
        self.update(status="grading")
        self.set_grading(state="running", grader=f"{gp}/{gm}", count=n, started=time.time())
        task = asyncio.create_task(hb.grade_run(run_dir, grader_provider=gp, grader_model=gm))
        self.tasks = {task}
        try:
            verdict = await task
        except asyncio.CancelledError:
            self.set_grading(state="cancelled", finished=time.time())
            return
        except Exception as e:
            self.set_grading(state="failed", finished=time.time(), error=f"{type(e).__name__}: {e}")
            self.update(status="error",
                        error=f"Grading failed ({type(e).__name__}: {e}). The answers are safe on "
                              f"disk — re-grade the bucket to try again.")
            return
        finally:
            self.tasks = set()
        archived = hb.save_grades(run_dir, verdict, gp, gm)
        self.log(f"Grades written to {run_dir / '_grades.md'} (archived {archived.name})")
        self.set_grading(state="done", finished=time.time())
        self.update(board=leaderboard(run_dir, verdict))


class JobManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.jobs: dict[str, Job] = {}
        self.current: Job | None = None

    def start(self, kind: str, params: dict) -> Job:
        with self.lock:
            if self.current and self.current.active:
                abort(409, "A run is already in progress — wait for it or cancel it first.")
            job = Job(kind, params)
            self.jobs[job.id] = job
            self.current = job
        job.start()
        return job


JOBS = JobManager()


class _JobTee:
    """Wraps stdout/stderr: everything still reaches the console, and lines
    printed from the running job's thread are copied into that job's log (so
    the grader's retry notices etc. show up in the browser)."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, s):
        try:
            self._stream.write(s)
        except UnicodeEncodeError:
            self._stream.write(s.encode("ascii", "replace").decode("ascii"))
        job = JOBS.current
        if job and job.active and threading.current_thread() is job.thread:
            job.capture(s)
        return len(s)

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


# ── Demo mode ──────────────────────────────────────────────────────────────

class DemoLLMClient:
    """Stands in for LLMClient under --demo: sleeps, sometimes fails, returns
    plausible-looking answers and a correctly formatted verdict table, so the
    whole run → save → grade → leaderboard path runs for free."""

    def __init__(self, config_path: str = "config.yaml", provider=None, model=None):
        self.provider, self.model = provider, model
        self.max_tokens = 1024
        self.reasoning_effort = None
        self.web_search = False
        self.last_usage = None
        self.last_web_searches = None

    async def call(self, prompt: str, system: str | None = None) -> str:
        if system is not None:
            return await self._verdict(prompt)
        await asyncio.sleep(random.uniform(3, 14))
        if random.random() < 0.12:
            raise RuntimeError("Demo: simulated provider error (503 UNAVAILABLE)")
        out = random.randint(3000, 14000)
        reasoning = random.randint(0, 9000)
        inp = random.randint(900, 1200)
        self.last_usage = {"input_tokens": inp, "output_tokens": out,
                           "reasoning_tokens": reasoning, "total_tokens": inp + out}
        if self.web_search:
            self.last_web_searches = random.randint(1, 12)
        return (f"# The {self.model} Fishing Doctrine\n\n"
                f"_Demo answer — no API was called._\n\n"
                f"## 1. The one rule\n\nFish **Feralas** at night. Effort knob: `{self.reasoning_effort}`.\n\n"
                "| Spot | Safety | Gold/h |\n|---|---|---|\n| Feathermoon | 9/10 | 8–12g |\n"
                "| Jademir Lake | 8/10 | 6–10g |\n\n> **Callout:** cook everything you catch.\n")

    async def _verdict(self, prompt: str) -> str:
        await asyncio.sleep(random.uniform(4, 8))
        letters = re.findall(r"^## Response ([A-Z])$", prompt, re.MULTILINE)
        lines = ["### 1. Markdown Table", "",
                 "| Letter | Accuracy | Strategy | Creativity | Structure | Fidelity | Total | One-line verdict |",
                 "|---|---|---|---|---|---|---|---|"]
        for letter in letters:
            s = [random.randint(3, 10) for _ in range(5)]
            lines.append(f"| {letter} | {' | '.join(map(str, s))} | {sum(s)} | Demo verdict for response {letter}. |")
        lines += ["", "### 2. Rankings", "", "Demo mode — scores are random.", "",
                  "### 4. Hallucination Callouts", "", "None (demo)."]
        return "\n".join(lines)


def enable_demo():
    global DEMO
    DEMO = True
    scratch = Path(tempfile.mkdtemp(prefix="haakonbench-demo-"))
    target = scratch / "results"
    if hb.BASE_RESULTS_DIR.is_dir():
        shutil.copytree(hb.BASE_RESULTS_DIR, target)
    else:
        target.mkdir()
    hb.BASE_RESULTS_DIR = target
    hb.LLMClient = DemoLLMClient
    print(f"DEMO MODE: no API calls; working on a scratch copy of results/ in {target}")


# ── HTTP ───────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=None)


@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(409)
def _json_error(e):
    return jsonify({"error": e.description}), e.code


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/static/<path:name>")
def static_file(name):
    return send_from_directory(STATIC_DIR, name)


@app.get("/api/config")
def api_config():
    contestants = []
    for provider, model in hb.CONTESTANTS:
        contestants.append({
            "provider": provider, "model": model, "label": hb.slug(provider, model),
            "knobs": {t: hb.resolve_effort(provider, model, t)[1] for t in hb.TIERS},
        })
    graders = {f"{hb.GRADER_PROVIDER}/{hb.GRADER_MODEL}"}
    for run_dir in (p for p in base_dir().iterdir() if p.is_dir()):
        graders.update(h["grader"] for h in grade_history(run_dir) if "/" in h["grader"])
    graders.update(f"{c['provider']}/{c['model']}" for c in contestants)
    return jsonify({
        "demo": DEMO,
        "contestants": contestants,
        "default_grader": f"{hb.GRADER_PROVIDER}/{hb.GRADER_MODEL}",
        "graders": sorted(graders),
        "tiers": [{"name": t, "max_tokens": hb.TIER_MAX_TOKENS[t]} for t in hb.TIERS],
        "default_effort": hb.DEFAULT_EFFORT,
        "providers": {p: {"key": DEMO or bool(os.getenv(k))} for p, k in PROVIDER_KEYS.items()},
        "prompt": hb.PROMPT,
        "prompt_sha": hb.prompt_sha(),
    })


@app.get("/api/runs")
def api_runs():
    return jsonify(all_runs())


@app.get("/api/runs/<name>")
def api_run(name):
    run_dir = safe_run_dir(name)
    answers = []
    for f in answer_files(run_dir):
        a = read_answer(f)
        provider, model = split_label(f.stem)
        answers.append({"label": f.stem, "provider": provider, "model": model,
                        "status": a["status"], "error": a["error"],
                        "meta": clean_meta(hb.load_result_meta(run_dir, f.stem))})
    grades_path = run_dir / "_grades.md"
    prompt_path = run_dir / hb.PROMPT_COPY
    return jsonify({
        **summarize_run(run_dir),
        "answers": answers,
        "board": leaderboard(run_dir),
        "verdict": strip_comments(grades_path.read_text(encoding="utf-8")) if grades_path.exists() else None,
        "prompt": strip_comments(prompt_path.read_text(encoding="utf-8")).strip() if prompt_path.exists() else None,
        "history": grade_history(run_dir),
    })


@app.get("/api/runs/<name>/answers/<label>")
def api_answer(name, label):
    run_dir = safe_run_dir(name)
    path = run_dir / f"{label}.md"
    if path not in answer_files(run_dir):
        abort(404, f"No answer {label!r} in {name}")
    a = read_answer(path)
    provider, model = split_label(label)
    return jsonify({**a, "label": label, "provider": provider, "model": model,
                    "meta": clean_meta(hb.load_result_meta(run_dir, label))})


@app.get("/api/runs/<name>/grades/<file>")
def api_grade_file(name, file):
    run_dir = safe_run_dir(name)
    if file not in {h["file"] for h in grade_history(run_dir)}:
        abort(404, f"No archived verdict {file!r}")
    text = (run_dir / hb.GRADES_DIR / file).read_text(encoding="utf-8")
    return jsonify({"verdict": strip_comments(text), "board": leaderboard(run_dir, text)})


@app.post("/api/plan")
def api_plan():
    return jsonify(build_plan(parse_run_params(request.get_json(force=True) or {})))


@app.post("/api/jobs")
def api_start_job():
    body = request.get_json(force=True) or {}
    kind = body.get("kind", "run")
    if kind == "regrade":
        run_dir = safe_run_dir(body.get("run", ""))
        grader = parse_run_params({"grader": body.get("grader")})["grader"]
        job = JOBS.start("regrade", {"run": run_dir.name, "grader": grader})
    else:
        params = parse_run_params(body)
        if not params["models"]:
            abort(400, "Pick at least one model.")
        plan = build_plan(params)
        if plan["conflicts"]:
            abort(400, "Bucket config conflict: " + "; ".join(plan["conflicts"]))
        job = JOBS.start("run", params)
    return jsonify({"id": job.id})


@app.get("/api/jobs/current")
def api_current_job():
    job = JOBS.current
    if not job:
        return jsonify(None)
    return Response(job.snapshot_json()[1], mimetype="application/json")


@app.post("/api/jobs/<jid>/cancel")
def api_cancel(jid):
    job = JOBS.jobs.get(jid) or abort(404, "Unknown job")
    job.cancel()
    return jsonify({"ok": True})


@app.get("/api/jobs/<jid>/events")
def api_events(jid):
    job = JOBS.jobs.get(jid) or abort(404, "Unknown job")

    def stream():
        seen = -1
        while True:
            with job.cond:
                if job.version == seen and job.active:
                    job.cond.wait(timeout=15)
                changed = job.version != seen
            if not changed:
                yield ": keepalive\n\n"
                continue
            seen, payload, active = job.snapshot_json()
            yield f"data: {payload}\n\n"
            if not active:
                return

    return Response(stream_with_context(stream()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def main():
    parser = argparse.ArgumentParser(description="HåkonBench web dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="Don't open a browser tab on start.")
    parser.add_argument("--demo", action="store_true",
                        help="Fake every API call and work on a scratch copy of results/ — costs nothing.")
    args = parser.parse_args()

    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
        setattr(sys, name, _JobTee(stream))

    if args.demo:
        enable_demo()
    url = f"http://{args.host}:{args.port}"
    print(f"HåkonBench dashboard → {url}")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=args.host, port=args.port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
