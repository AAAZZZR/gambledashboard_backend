# main.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import pyodbc
from decimal import Decimal
import os
from dotenv import load_dotenv
from schemas import Sport, BookmakerOdds, Event, EventDetail, OddsHistory, OddsHistoryPoint

load_dotenv()

app = FastAPI(title="Sports Odds API", version="2.0.0")

# CORS settings (allow Next.js frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Database Connection ====================
def get_db_connection():
    """Establish Azure SQL Database connection"""
    connection_string = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={os.getenv('AZURE_SQL_SERVER')};"
        f"DATABASE={os.getenv('AZURE_SQL_DATABASE')};"
        f"UID={os.getenv('AZURE_SQL_USERNAME')};"
        f"PWD={os.getenv('AZURE_SQL_PASSWORD')};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=30;"
    )
    return pyodbc.connect(connection_string)



# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Sports Odds API Running", 
        "version": "2.0.0",
        "endpoints": {
            "/api/sports": "Get all sports",
            "/api/sports/{sport_key}/events": "Get all events and odds for specific sport",
            "/api/events/{event_id}": "Get event details",
            "/api/events/{event_id}/history": "Get event odds history"
        }
    }

@app.get("/api/sports", response_model=List[Sport])
async def get_sports():
    """
    Get all available sports
    For frontend sports menu
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        query = """
        WITH LatestSnapshot AS (
            SELECT MAX(snapshot_at) as latest_snapshot
            FROM dbo.AFL_2025_odds
        ),
        CurrentEvents AS (
            SELECT sport_key, COUNT(DISTINCT event_id) as event_count
            FROM dbo.AFL_2025_odds o
            CROSS JOIN LatestSnapshot ls
            WHERE o.snapshot_at = ls.latest_snapshot
                AND o.commence_time >= GETDATE()  -- Only count future events
            GROUP BY sport_key
        )
        SELECT 
            DISTINCT o.sport_key,
            COALESCE(ce.event_count, 0) as event_count
        FROM dbo.AFL_2025_odds o
        LEFT JOIN CurrentEvents ce ON o.sport_key = ce.sport_key
        ORDER BY o.sport_key
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Sport name mapping (can be expanded as needed)
        sport_names = {
            "australianfootball_afl": "Australian Football AFL",
            "soccer_epl": "English Premier League",
            "basketball_nba": "NBA Basketball",
            # Add more sports
        }
        
        sports = []
        for row in rows:
            sport_key = row[0]
            sports.append(Sport(
                sport_key=sport_key,
                sport_name=sport_names.get(sport_key, sport_key),
                event_count=row[1] or 0
            ))
        
        return sports
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/sports/{sport_key}/events", response_model=List[Event])
async def get_sport_events(
    sport_key: str,
    # include_live: bool = Query(True, description="Include live events"),
    # include_upcoming: bool = Query(True, description="Include upcoming events")
):
    """
    Get all events and bookmaker odds for specified sport
    This is the main event list endpoint
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Build time filter conditions
        time_filters = []
        time_filters.append("(o.commence_time > GETDATE())")
        
    
        if not time_filters:
            raise HTTPException(status_code=400, detail="Must select at least one event type")
        
        time_condition = " OR ".join(time_filters)
        
        query = f"""
        WITH LatestSnapshot AS (
            SELECT MAX(snapshot_at) as latest_snapshot
            FROM dbo.AFL_2025_odds
            WHERE sport_key = ?
        ),
        RelevantEvents AS (
            SELECT DISTINCT event_id, home_team, away_team, commence_time
            FROM dbo.AFL_2025_odds o
            CROSS JOIN LatestSnapshot ls
            WHERE o.sport_key = ?
                AND o.snapshot_at = ls.latest_snapshot
                AND ({time_condition})
        )
        SELECT 
            re.event_id,
            re.home_team,
            re.away_team,
            re.commence_time,
            o.bookmaker_key,
            o.bookmaker_title,
            o.snapshot_at,
            -- H2H odds
            o.home_h2h_price,
            o.away_h2h_price,
            -- Spreads odds
            o.home_spread_price,
            o.home_spread_point,
            o.away_spread_price,
            o.away_spread_point,
            -- Totals odds
            o.over_total_price,
            o.over_total_point,
            o.under_total_price,
            o.under_total_point,
            -- Check if live
            CASE 
                WHEN re.commence_time <= GETDATE() THEN 1 
                ELSE 0 
            END as is_live
        FROM RelevantEvents re
        JOIN dbo.AFL_2025_odds o ON re.event_id = o.event_id
        CROSS JOIN LatestSnapshot ls
        WHERE o.sport_key = ?
            AND o.snapshot_at = ls.latest_snapshot
        ORDER BY re.commence_time, re.event_id, o.bookmaker_key
        """
        
        cursor.execute(query, (sport_key, sport_key, sport_key))
        rows = cursor.fetchall()
        
        if not rows:
            return []
        
        # Organize data
        events_dict = {}
        for row in rows:
            event_id = row[0]
            
            if event_id not in events_dict:
                events_dict[event_id] = {
                    "event_id": event_id,
                    "sport_key": sport_key,
                    "home_team": row[1],
                    "away_team": row[2],
                    "commence_time": row[3],
                    "bookmakers": [],
                    "is_live": bool(row[17])
                }
            
            # Organize bookmaker odds
            bookmaker_odds = BookmakerOdds(
                bookmaker_key=row[4],
                bookmaker_title=row[5],
                last_update=row[6],
                h2h={
                    "home": float(row[7]) if row[7] else None,
                    "away": float(row[8]) if row[8] else None
                },
                spreads={
                    "home": {
                        "price": float(row[9]) if row[9] else None,
                        "point": float(row[10]) if row[10] else None
                    },
                    "away": {
                        "price": float(row[11]) if row[11] else None,
                        "point": float(row[12]) if row[12] else None
                    }
                },
                totals={
                    "over": {
                        "price": float(row[13]) if row[13] else None,
                        "point": float(row[14]) if row[14] else None
                    },
                    "under": {
                        "price": float(row[15]) if row[15] else None,
                        "point": float(row[16]) if row[16] else None
                    }
                }
            )
            
            events_dict[event_id]["bookmakers"].append(bookmaker_odds)
        
        # Convert to list and sort by time
        events = list(events_dict.values())
        events.sort(key=lambda x: x["commence_time"])
        
        return events
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/events/{event_id}", response_model=EventDetail)
async def get_event_detail(event_id: str):
    """
    Get single event details
    Including current odds and odds analysis
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        query = """
        WITH LatestSnapshot AS (
            SELECT MAX(snapshot_at) as latest_snapshot
            FROM dbo.AFL_2025_odds
            WHERE event_id = ?
        )
        SELECT 
            o.event_id,
            o.sport_key,
            o.home_team,
            o.away_team,
            o.commence_time,
            o.bookmaker_key,
            o.bookmaker_title,
            o.snapshot_at,
            o.home_h2h_price,
            o.away_h2h_price,
            o.home_spread_price,
            o.home_spread_point,
            o.away_spread_price,
            o.away_spread_point,
            o.over_total_price,
            o.over_total_point,
            o.under_total_price,
            o.under_total_point
        FROM dbo.AFL_2025_odds o
        CROSS JOIN LatestSnapshot ls
        WHERE o.event_id = ?
            AND o.snapshot_at = ls.latest_snapshot
        ORDER BY o.bookmaker_key
        """
        
        cursor.execute(query, (event_id, event_id))
        rows = cursor.fetchall()
        
        if not rows:
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Basic info
        first_row = rows[0]
        event_detail = {
            "event_id": event_id,
            "sport_key": first_row[1],
            "home_team": first_row[2],
            "away_team": first_row[3],
            "commence_time": first_row[4],
            "current_odds": [],
            "odds_comparison": {}
        }
        
        # Collect all odds for comparison
        h2h_home_prices = []
        h2h_away_prices = []
        
        for row in rows:
            bookmaker_odds = BookmakerOdds(
                bookmaker_key=row[5],
                bookmaker_title=row[6],
                last_update=row[7],
                h2h={
                    "home": float(row[8]) if row[8] else None,
                    "away": float(row[9]) if row[9] else None
                },
                spreads={
                    "home": {
                        "price": float(row[10]) if row[10] else None,
                        "point": float(row[11]) if row[11] else None
                    },
                    "away": {
                        "price": float(row[12]) if row[12] else None,
                        "point": float(row[13]) if row[13] else None
                    }
                },
                totals={
                    "over": {
                        "price": float(row[14]) if row[14] else None,
                        "point": float(row[15]) if row[15] else None
                    },
                    "under": {
                        "price": float(row[16]) if row[16] else None,
                        "point": float(row[17]) if row[17] else None
                    }
                }
            )
            event_detail["current_odds"].append(bookmaker_odds)
            
            # Collect H2H odds for analysis
            if row[8]:
                h2h_home_prices.append(float(row[8]))
            if row[9]:
                h2h_away_prices.append(float(row[9]))
        
        # Calculate odds comparison analysis
        if h2h_home_prices:
            event_detail["odds_comparison"]["h2h_home"] = {
                "best": max(h2h_home_prices),
                "worst": min(h2h_home_prices),
                "average": sum(h2h_home_prices) / len(h2h_home_prices)
            }
        
        if h2h_away_prices:
            event_detail["odds_comparison"]["h2h_away"] = {
                "best": max(h2h_away_prices),
                "worst": min(h2h_away_prices),
                "average": sum(h2h_away_prices) / len(h2h_away_prices)
            }
        
        return event_detail
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/events/{event_id}/history", response_model=OddsHistory)
async def get_event_history(
    event_id: str,
    market_type: str = Query("h2h", regex="^(h2h|spreads|totals)$", description="Market type"),
    bookmaker: Optional[str] = Query(None, description="Specific bookmaker, shows all if not specified"),
    hours: int = Query(72, ge=1, le=168, description="History time range (hours) 1-168")
):
    """
    Get event odds history
    For frontend line charts
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get basic event info first
        info_query = """
        SELECT TOP 1 home_team, away_team
        FROM dbo.AFL_2025_odds
        WHERE event_id = ?
        """
        cursor.execute(info_query, (event_id,))
        info_row = cursor.fetchone()
        
        if not info_row:
            raise HTTPException(status_code=404, detail="Event not found")
        
        home_team, away_team = info_row
        
        # Query history data
        base_query = """
        SELECT 
            snapshot_at,
            bookmaker_key,
            home_h2h_price,
            away_h2h_price,
            home_spread_price,
            home_spread_point,
            away_spread_price,
            away_spread_point,
            over_total_price,
            over_total_point,
            under_total_price,
            under_total_point
        FROM dbo.AFL_2025_odds
        WHERE event_id = ?
            AND snapshot_at >= DATEADD(hour, ?, GETDATE())
            {bookmaker_filter}
        ORDER BY snapshot_at ASC, bookmaker_key
        """
        
        bookmaker_filter = f"AND bookmaker_key = '{bookmaker}'" if bookmaker else ""
        query = base_query.format(bookmaker_filter=bookmaker_filter)
        
        cursor.execute(query, (event_id, -hours))
        rows = cursor.fetchall()
        
        if not rows:
            return OddsHistory(
                event_id=event_id,
                home_team=home_team,
                away_team=away_team,
                market_type=market_type,
                bookmaker=bookmaker,
                history=[]
            )
        
        # Organize history data
        history_points = []
        
        for row in rows:
            point = OddsHistoryPoint(
                timestamp=row[0],
                bookmaker=row[1],
                market_type=market_type,
                values={}
            )
            
            if market_type == "h2h":
                point.values = {
                    "home": float(row[2]) if row[2] else None,
                    "away": float(row[3]) if row[3] else None
                }
            elif market_type == "spreads":
                point.values = {
                    "home_price": float(row[4]) if row[4] else None,
                    "home_point": float(row[5]) if row[5] else None,
                    "away_price": float(row[6]) if row[6] else None,
                    "away_point": float(row[7]) if row[7] else None
                }
            elif market_type == "totals":
                point.values = {
                    "over_price": float(row[8]) if row[8] else None,
                    "over_point": float(row[9]) if row[9] else None,
                    "under_price": float(row[10]) if row[10] else None,
                    "under_point": float(row[11]) if row[11] else None
                }
            
            history_points.append(point)
        
        return OddsHistory(
            event_id=event_id,
            home_team=home_team,
            away_team=away_team,
            market_type=market_type,
            bookmaker=bookmaker,
            history=history_points
        )
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@app.get("/api/bookmakers")
async def get_all_bookmakers():
    """
    Get all bookmakers list
    Can be used for frontend filters
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        query = """
        SELECT DISTINCT 
            bookmaker_key,
            bookmaker_title
        FROM dbo.AFL_2025_odds
        WHERE bookmaker_title IS NOT NULL
        ORDER BY bookmaker_key
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        bookmakers = [
            {
                "key": row[0],
                "title": row[1]
            }
            for row in rows
        ]
        
        return {"bookmakers": bookmakers, "total": len(bookmakers)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)