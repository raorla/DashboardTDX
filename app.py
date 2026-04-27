#!/usr/bin/env python3
"""
TDX Dashboard — FastAPI backend (mode hybride)

Architecture :
  Frontend (filtres dates) → FastAPI → Cache mémoire (TTL 5 min) → Subgraph GraphQL
                                              ↓ fallback
                                         CSV existants
"""

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("tdx_dashboard")
UTC = timezone.utc

# ── Chemins ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
ANALYSE_DIR = BASE_DIR.parent
OUTPUT_DIR = ANALYSE_DIR / "deal_output"

# ── Workerpools TDX ───────────────────────────────────────────
WORKERPOOL_TDX_MAINNET = "0x8ef2ec3ef9535d4b4349bfec7d8b31a580e60244"
WORKERPOOL_TDX_SEPOLIA = "0x2956f0cb779904795a5f30d3b3ea88b714c3123f"

# ── Endpoints GraphQL ──────────────────────────────────────────
URL_ARB_MAINNET = "https://thegraph.arbitrum.iex.ec/api/subgraphs/id/B1comLe9SANBLrjdnoNTJSubbeC7cY7EoNu6zD82HeKy"
URL_ARB_SEPOLIA = "https://thegraph.arbitrum-sepolia-testnet.iex.ec/api/subgraphs/id/2GCj8gzLCihsiEDq8cYvC5nUgK6VfwZ6hm3Wj8A3kcxz"

GRAPHQL_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

NETWORKS = {
    "mainnet": {
        "label": "Arbitrum Mainnet",
        "workerpool": WORKERPOOL_TDX_MAINNET,
        "url": URL_ARB_MAINNET,
        "tasks_prefix": "arbitrum_mainnet_tdx_raw_tasks.csv",
        "datasets_prefix": "arbitrum_mainnet_tdx_raw_datasets.csv",
    },
    "sepolia": {
        "label": "Arbitrum Sepolia",
        "workerpool": WORKERPOOL_TDX_SEPOLIA,
        "url": URL_ARB_SEPOLIA,
        "tasks_prefix": "arbitrum_sepolia_tdx_raw_tasks.csv",
        "datasets_prefix": "arbitrum_sepolia_tdx_raw_datasets.csv",
    },
}

# ── GraphQL queries ────────────────────────────────────────────
TASKS_QUERY = """{
  taskInitializes(first:500, skip: SKIP_PARAM, orderBy: timestamp, orderDirection: desc){
    task{
      id,
      deal{
        requester { id }
        app{ name multiaddr }
        dataset{ name id }
        workerpool{ id }
        tag
      }
      status,
    }
    timestamp
  }
}"""

DATASETS_QUERY = """
{
  datasets(first:FIRST_PARAM, skip:SKIP_PARAM,
           orderBy:timestamp, orderDirection:desc) {
    id
    owner { id }
    timestamp
    name
    usages(first:1000, orderBy:timestamp, orderDirection:desc) {
      id
      datasetPrice
      timestamp
    }
  }
}
"""

# ── Cache en mémoire ──────────────────────────────────────────
CACHE_TTL = 300  # 5 minutes
_cache: dict[str, tuple[float, object]] = {}


def _cache_key(prefix: str, network: str, date_from: str, date_to: str) -> str:
    raw = f"{prefix}:{network}:{date_from}:{date_to}"
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, value):
    _cache[key] = (time.time(), value)


# ── Utilitaires ────────────────────────────────────────────────
def hex_to_string(value) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if v.startswith("0x"):
        try:
            return bytes.fromhex(v[2:]).decode("utf-8", errors="ignore")
        except ValueError:
            return None
    return v


def _parse_date(s: Optional[str], end_of_day: bool = False) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=UTC)
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt
    except ValueError:
        return None


def _default_date_range() -> tuple[datetime, datetime]:
    """Défaut : 35 derniers jours."""
    end = datetime.now(UTC)
    begin = end - timedelta(days=35)
    return begin, end


# ── Fetch GraphQL — Tâches ─────────────────────────────────────
async def _fetch_tasks_subgraph(
    url: str, workerpool: str, date_begin: datetime, date_end: datetime,
) -> pd.DataFrame:
    """Requête le subgraph pour les tâches TDX dans la période."""
    begin_ts = int(date_begin.timestamp())
    end_ts = int(date_end.timestamp())
    total_data = []
    skip = 0
    page_size = 500
    max_skip = 200_000
    detected = False

    async with httpx.AsyncClient(timeout=30) as client:
        while skip < max_skip:
            query = TASKS_QUERY.replace("SKIP_PARAM", str(skip))
            try:
                r = await client.post(url, headers=GRAPHQL_HEADERS, json={"query": query})
                r.raise_for_status()
                body = r.json()
            except Exception as e:
                logger.warning("Subgraph tasks error skip=%d: %s", skip, e)
                break

            if "errors" in body:
                logger.warning("GraphQL errors: %s", body["errors"])
                break

            items = (body.get("data") or {}).get("taskInitializes") or []
            if not detected and not items:
                skip += page_size
                continue
            if detected and not items:
                break
            if items:
                ts_list = [int(e.get("timestamp", 0)) for e in items]
                if max(ts_list) < begin_ts:
                    break
            detected = True

            for e in items:
                ts = int(e.get("timestamp", 0))
                if not (begin_ts <= ts <= end_ts):
                    continue
                wp_id = e["task"]["deal"]["workerpool"]["id"]
                if wp_id != workerpool:
                    continue
                total_data.append([
                    e["task"]["id"],
                    e["task"]["deal"]["app"]["name"],
                    hex_to_string(e["task"]["deal"]["app"]["multiaddr"]),
                    e["task"]["deal"]["tag"],
                    e["task"]["status"],
                    ts,
                    wp_id,
                    e["task"]["deal"]["requester"]["id"],
                    (e["task"]["deal"].get("dataset") or {}).get("name"),
                    (e["task"]["deal"].get("dataset") or {}).get("id"),
                ])
            skip += page_size

    columns = [
        "TASK_ID", "APP NAME", "APP MULTIADDR", "TAG", "STATUS",
        "DATE", "WORKERPOOL ID", "REQUESTER ID", "DATASET_NAME", "DATASET_ID",
    ]
    if not total_data:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(total_data, columns=columns)
    df["DATE"] = df["DATE"].astype(int).apply(lambda x: datetime.fromtimestamp(x, UTC))
    return df


# ── Fetch GraphQL — Datasets ──────────────────────────────────
async def _fetch_datasets_subgraph(
    url: str, date_begin: datetime, date_end: datetime,
) -> pd.DataFrame:
    begin_ts = int(date_begin.timestamp())
    end_ts = int(date_end.timestamp())
    total_data = []
    skip = 0
    first = 1000

    async with httpx.AsyncClient(timeout=30) as client:
        while skip < 20_000:
            query = DATASETS_QUERY.replace("FIRST_PARAM", str(first)).replace("SKIP_PARAM", str(skip))
            try:
                r = await client.post(url, headers=GRAPHQL_HEADERS, json={"query": query})
                r.raise_for_status()
                page = (r.json().get("data") or {}).get("datasets") or []
            except Exception as e:
                logger.warning("Subgraph datasets error skip=%d: %s", skip, e)
                break

            if not page:
                break

            for d in page:
                dataset_ts = int(d["timestamp"])
                if not (begin_ts <= dataset_ts <= end_ts):
                    continue
                usages = d.get("usages") or []
                if not usages:
                    total_data.append([
                        d["id"], d.get("name", ""), d["owner"]["id"],
                        dataset_ts, None, None, None,
                    ])
                else:
                    for u in usages:
                        total_data.append([
                            d["id"], d.get("name", ""), d["owner"]["id"],
                            dataset_ts, u["id"], float(u["datasetPrice"]),
                            int(u["timestamp"]),
                        ])
            skip += first

    columns = [
        "DATASET_ID", "DATASET_NAME", "DATASET_OWNER", "DATASET_TIMESTAMP",
        "DEAL_ID", "DATASET_PRICE", "DEAL_TIMESTAMP",
    ]
    if not total_data:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(total_data, columns=columns)
    df["DATE"] = df["DATASET_TIMESTAMP"].apply(lambda x: datetime.fromtimestamp(int(x), UTC))
    df["DEAL_DATE"] = pd.to_datetime(df["DEAL_TIMESTAMP"], unit="s", errors="coerce", utc=True)
    return df


# ── Fallback CSV ───────────────────────────────────────────────
def _find_latest_tdx_dir() -> Path | None:
    candidates = sorted(OUTPUT_DIR.glob("tdx_analysis_*"), reverse=True)
    return candidates[0] if candidates else None


def _load_csv_tasks(network: str) -> pd.DataFrame:
    d = _find_latest_tdx_dir()
    if not d:
        return pd.DataFrame()
    csv_path = d / NETWORKS[network]["tasks_prefix"]
    if not csv_path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(csv_path, parse_dates=["DATE"])
        return df
    except Exception:
        return pd.DataFrame()


def _load_csv_datasets(network: str) -> pd.DataFrame:
    d = _find_latest_tdx_dir()
    if not d:
        return pd.DataFrame()
    csv_path = d / NETWORKS[network]["datasets_prefix"]
    if not csv_path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(csv_path)
        if "DATE" in df.columns:
            df["DATE"] = pd.to_datetime(df["DATE"])
        if "DEAL_DATE" in df.columns:
            df["DEAL_DATE"] = pd.to_datetime(df["DEAL_DATE"])
        return df
    except Exception:
        return pd.DataFrame()


# ── Remap statuts ──────────────────────────────────────────────
def _remap_status(df: pd.DataFrame) -> pd.DataFrame:
    """ACTIVE et REVEALING (claimed mais jamais terminé) → FAILLED."""
    if df.empty or "STATUS" not in df.columns:
        return df
    df = df.copy()
    df["STATUS"] = df["STATUS"].replace({"ACTIVE": "FAILLED", "REVEALING": "FAILLED"})
    return df


# ── Données (cache → subgraph → CSV fallback) ─────────────────
async def get_tasks(network: str, date_from: str, date_to: str) -> tuple[pd.DataFrame, str]:
    """
    Retourne (df_tasks, source).  source ∈ {'live', 'cache', 'csv'}
    """
    key = _cache_key("tasks", network, date_from, date_to)
    cached = _cache_get(key)
    if cached is not None:
        return cached, "cache"

    d_begin = _parse_date(date_from)
    d_end = _parse_date(date_to, end_of_day=True)
    if not d_begin or not d_end:
        d_begin, d_end = _default_date_range()

    net = NETWORKS.get(network, NETWORKS["mainnet"])
    try:
        df = await _fetch_tasks_subgraph(net["url"], net["workerpool"], d_begin, d_end)
        df = _remap_status(df)
        _cache_set(key, df)
        return df, "live"
    except Exception as e:
        logger.warning("Subgraph fallback CSV: %s", e)
        df = _load_csv_tasks(network)
        wp = net["workerpool"]
        if not df.empty and "WORKERPOOL ID" in df.columns:
            df = df[df["WORKERPOOL ID"] == wp]
        df = _remap_status(df)
        return df, "csv"


async def get_datasets(network: str, date_from: str, date_to: str) -> tuple[pd.DataFrame, str]:
    key = _cache_key("datasets", network, date_from, date_to)
    cached = _cache_get(key)
    if cached is not None:
        return cached, "cache"

    d_begin = _parse_date(date_from)
    d_end = _parse_date(date_to, end_of_day=True)
    if not d_begin or not d_end:
        d_begin, d_end = _default_date_range()

    net = NETWORKS.get(network, NETWORKS["mainnet"])
    try:
        df = await _fetch_datasets_subgraph(net["url"], d_begin, d_end)
        _cache_set(key, df)
        return df, "live"
    except Exception as e:
        logger.warning("Datasets fallback CSV: %s", e)
        return _load_csv_datasets(network), "csv"


# ── FastAPI ────────────────────────────────────────────────────
app = FastAPI(title="iExec TDX Dashboard")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# ── Routes HTML ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(str(BASE_DIR / "templates" / "index.html"))


# ── API JSON ───────────────────────────────────────────────────

@app.get("/api/summary")
async def summary(
    network: str = "mainnet",
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    df, source = await get_tasks(network, date_from, date_to)
    ds_df, _ = await get_datasets(network, date_from, date_to)

    if df.empty:
        return {
            "source": source,
            "total": 0, "completed": 0, "failed": 0, "active": 0, "other": 0,
            "success_rate": 0, "apps": 0, "requesters": 0, "datasets": 0,
            "date_min": None, "date_max": None,
        }

    total = len(df)
    completed = int((df["STATUS"] == "COMPLETED").sum())
    failed = int((df["STATUS"] == "FAILLED").sum())
    other = total - completed - failed
    datasets = int(ds_df["DATASET_ID"].nunique()) if not ds_df.empty and "DATASET_ID" in ds_df.columns else 0

    return {
        "source": source,
        "total": total,
        "completed": completed,
        "failed": failed,
        "other": other,
        "success_rate": round(completed / total * 100, 1) if total else 0,
        "apps": int(df["APP NAME"].nunique()),
        "requesters": int(df["REQUESTER ID"].nunique()),
        "datasets": datasets,
        "date_min": str(df["DATE"].min()),
        "date_max": str(df["DATE"].max()),
    }


@app.get("/api/tasks_per_day")
async def tasks_per_day(
    network: str = "mainnet",
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    df, _ = await get_tasks(network, date_from, date_to)
    if df.empty:
        return []

    df = df.copy()
    df["DAY"] = df["DATE"].dt.strftime("%Y-%m-%d")
    grouped = df.groupby(["DAY", "STATUS"]).size().reset_index(name="count")

    result = {}
    for _, row in grouped.iterrows():
        day = row["DAY"]
        if day not in result:
            result[day] = {"day": day, "COMPLETED": 0, "FAILLED": 0, "OTHER": 0}
        status = row["STATUS"]
        if status in result[day]:
            result[day][status] = int(row["count"])
        else:
            result[day]["OTHER"] = result[day].get("OTHER", 0) + int(row["count"])

    return sorted(result.values(), key=lambda x: x["day"])


@app.get("/api/apps_breakdown")
async def apps_breakdown(
    network: str = "mainnet",
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    df, _ = await get_tasks(network, date_from, date_to)
    if df.empty:
        return []

    grouped = df.groupby(["APP NAME", "STATUS"]).size().reset_index(name="count")
    apps = {}
    for _, row in grouped.iterrows():
        app_name = row["APP NAME"]
        if app_name not in apps:
            apps[app_name] = {"app": app_name, "COMPLETED": 0, "FAILLED": 0, "total": 0}
        status = row["STATUS"]
        count = int(row["count"])
        if status in apps[app_name]:
            apps[app_name][status] = count
        apps[app_name]["total"] += count

    return sorted(apps.values(), key=lambda x: x["total"], reverse=True)


@app.get("/api/requesters")
async def requesters(
    network: str = "mainnet",
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    df, _ = await get_tasks(network, date_from, date_to)
    if df.empty:
        return []

    grouped = df.groupby(["REQUESTER ID", "STATUS"]).size().reset_index(name="count")
    reqs = {}
    for _, row in grouped.iterrows():
        rid = row["REQUESTER ID"]
        if rid not in reqs:
            reqs[rid] = {"requester": rid, "COMPLETED": 0, "FAILLED": 0, "total": 0}
        status = row["STATUS"]
        count = int(row["count"])
        if status in reqs[rid]:
            reqs[rid][status] = count
        reqs[rid]["total"] += count

    return sorted(reqs.values(), key=lambda x: x["total"], reverse=True)


@app.get("/api/export_csv")
async def export_csv(
    network: str = "mainnet",
    date_from: str = Query(None),
    date_to: str = Query(None),
):
    """Exporte les tâches en CSV téléchargeable."""
    df, _ = await get_tasks(network, date_from, date_to)
    if df.empty:
        return StreamingResponse(
            iter(["No data"]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=tdx_tasks.csv"},
        )
    csv_data = df.to_csv(index=False)
    filename = f"tdx_tasks_{network}_{date_from or 'all'}_{date_to or 'all'}.csv"
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/cache_status")
async def cache_status():
    """Info sur le cache."""
    now = time.time()
    entries = []
    for k, (ts, _) in _cache.items():
        age = round(now - ts)
        entries.append({"key": k, "age_seconds": age, "ttl_remaining": max(0, CACHE_TTL - age)})
    return {"ttl": CACHE_TTL, "entries": len(_cache), "details": entries}


@app.post("/api/clear_cache")
async def clear_cache():
    """Vide le cache pour forcer un refresh."""
    _cache.clear()
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8050, reload=True)
