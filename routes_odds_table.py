# app/routes_odds_table.py
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import httpx
from typing import Any, Dict, List, Optional
from .config import settings
from backend.bookmaker import get_bookmaker_meta  

router = APIRouter()
ODDS_BASE = settings.ODDS_API_BASE
API_KEY = settings.ODDS_API_KEY

def _pick_market(markets: List[Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
    for m in markets:
        if m.get("key") == key:
            return m
    return None

def _format_h2h(market: Dict[str, Any]) -> str:
    try:
        outs = market.get("outcomes", [])
        return " / ".join(f"{o['name']}: {o['price']}" for o in outs if "name" in o and "price" in o)
    except Exception:
        return ""

def _format_spreads(market: Dict[str, Any]) -> str:
    try:
        outs = market.get("outcomes", [])
        return " / ".join(
            f"{o['name']}({o['point']}): {o['price']}"
            for o in outs if all(k in o for k in ("name", "point", "price"))
        )
    except Exception:
        return ""

def _format_totals(market: Dict[str, Any]) -> str:
    try:
        outs = market.get("outcomes", [])
        return " / ".join(
            f"{o['name']} {o['point']}: {o['price']}"
            for o in outs if all(k in o for k in ("name", "point", "price"))
        )
    except Exception:
        return ""

@router.get("/api/odds_table")
async def odds_table(
    sport: str = Query(..., description="sport key, e.g. aussierules_afl"),
    regions: List[str] = Query(["au"]),
    markets: List[str] = Query(["h2h","spreads","totals"]),
    oddsFormat: str = Query("decimal"),
    dateFormat: str = Query("iso"),
):
    url = f"{ODDS_BASE}/sports/{sport}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": ",".join(regions),
        "markets": ",".join(markets),
        "oddsFormat": oddsFormat,
        "dateFormat": dateFormat,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params)
    if r.status_code != 200:
        return JSONResponse({"error": r.text}, status_code=r.status_code)

    events = r.json()  # list[event]
    columns = ["bookmaker", "match", "h2h", "spreads", "totals", "start", "bookmaker_url"]

    matches: List[Dict[str, Any]] = []
    for ev in events:
        match_label = f"{ev.get('home_team','?')} vs {ev.get('away_team','?')}"
        start = ev.get("commence_time", "")
        rows: List[Dict[str, Any]] = []

        for bm in ev.get("bookmakers", []):
            meta = get_bookmaker_meta(bm.get("key"), bm.get("title"))  # 👈 正規化 + 官網
            bm_markets = bm.get("markets", [])

            row = {
                "bookmaker": meta["name"],          # 用統一名稱
                "bookmaker_url": meta["url"],       # 官網（可能為 None）
                "match": match_label,
                "start": start,
                "h2h": _format_h2h(_pick_market(bm_markets, "h2h")) or "",
                "spreads": _format_spreads(_pick_market(bm_markets, "spreads")) or "",
                "totals": _format_totals(_pick_market(bm_markets, "totals")) or "",
            }
            rows.append(row)

        # 👇 按字母順序排列（大小寫不敏感）
        rows.sort(key=lambda r: (r["bookmaker"] or "").lower())

        matches.append({
            "id": ev.get("id"),
            "match": match_label,
            "start": start,
            "rows": rows,
        })
    print(JSONResponse({"columns": columns, "matches": matches}).body)
    return JSONResponse({"columns": columns, "matches": matches})
