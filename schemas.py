from pydantic import BaseModel, Field, constr
from typing import Literal
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
class Sport(BaseModel):
    """Sport type model"""
    sport_key: str
    sport_name: str
    event_count: int = Field(description="Current event count")

class BookmakerOdds(BaseModel):
    """Bookmaker odds"""
    bookmaker_key: str
    bookmaker_title: Optional[str]
    h2h: Dict[str, Optional[float]] = Field(description="Head to head odds")
    spreads: Dict[str, Any] = Field(description="Spread odds")
    totals: Dict[str, Any] = Field(description="Over/under odds")
    last_update: Optional[datetime] = Field(description="Last update time")

class Event(BaseModel):
    """Event model (including all bookmaker odds)"""
    event_id: str
    sport_key: str
    home_team: Optional[str]
    away_team: Optional[str]
    commence_time: datetime
    bookmakers: List[BookmakerOdds]
    is_live: bool = Field(description="Is currently live")
    
class EventDetail(BaseModel):
    """Event detail (for detail page)"""
    event_id: str
    sport_key: str
    home_team: Optional[str]
    away_team: Optional[str]
    commence_time: datetime
    current_odds: List[BookmakerOdds]
    odds_comparison: Dict[str, Any] = Field(description="Odds comparison analysis")

class OddsHistoryPoint(BaseModel):
    """Odds history data point"""
    timestamp: datetime
    bookmaker: str
    market_type: str
    values: Dict[str, Any]

class OddsHistory(BaseModel):
    """Odds history (for charts)"""
    event_id: str
    home_team: Optional[str]
    away_team: Optional[str]
    market_type: str
    bookmaker: Optional[str]
    history: List[OddsHistoryPoint]
    
