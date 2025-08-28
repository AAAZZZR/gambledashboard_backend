# app/bookmakers.py
from typing import Dict, Optional

# 你可以持續擴充（key 用 Odds API 的 bookmaker.key）
BOOKMAKER_URLS: Dict[str, str] = {
    "betright":       "https://www.betright.com.au/",
    "betfair_ex_au":  "https://www.betfair.com.au/exchange/",
    "betr":           "https://www.betr.com.au/",
    "boombet":        "https://www.boombet.com.au/",
    "ladbrokes":      "https://www.ladbrokes.com.au/",
    "neds":           "https://www.neds.com.au/",
    "playup":         "https://www.playup.com.au/",
    "pointsbetau":    "https://pointsbet.com.au/",
    "sportsbet":      "https://www.sportsbet.com.au/",
    "tab":            "https://www.tab.com.au/",
    "tabtouch":       "https://www.tabtouch.com.au/",
    "unibet":         "https://www.unibet.com.au/",
}

# 可能出現的別名 → 正規 key
ALIASES: Dict[str, str] = {
    "bet_right":     "betright",
    "betfair":       "betfair_ex_au",
    "pointsbet":     "pointsbetau",
    "sportsbet_au":  "sportsbet",
    "unibet_au":     "unibet",
    "tab_au":        "tab",
}

# 部分品牌的慣用顯示名稱（可依你喜好調整）
CANONICAL_NAME: Dict[str, str] = {
    "betfair_ex_au": "Betfair",
    "pointsbetau":   "PointsBet (AU)",
    "sportsbet":     "SportsBet",
    "tab":           "TAB",
}

def normalize_key(key: Optional[str]) -> str:
    if not key:
        return ""
    k = key.strip().lower()
    return ALIASES.get(k, k)

def get_bookmaker_meta(key: Optional[str], title: Optional[str] = None) -> dict:
    nk = normalize_key(key)
    url = BOOKMAKER_URLS.get(nk)
    name = CANONICAL_NAME.get(nk) or title or (key or "")
    return {"key": nk or (key or ""), "name": name, "url": url}
