import os
from datetime import datetime

import pandas as pd
import requests
from sqlalchemy import text
from dotenv import load_dotenv

from src.db import engine

# 🔑 load .env
load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY")

SPORT = "basketball_nba"
REGIONS = "us"
BOOKMAKERS = "fanduel,draftkings"

MARKET_MAP = {
    "player_points": "POINTS",
    "player_rebounds": "REBOUNDS",
    "player_assists": "ASSISTS",
    "player_points_rebounds_assists": "PRA",
}

EVENTS_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
EVENT_ODDS_URL = f"https://api.the-odds-api.com/v4/sports/{SPORT}/events/{{event_id}}/odds"


def _require_api_key():
    if not ODDS_API_KEY:
        raise ValueError("❌ ODDS_API_KEY not loaded. Check your .env")


def normalize_name(name):
    return " ".join(str(name).strip().lower().split())


# ======================
# FETCH EVENTS
# ======================
def fetch_today_events():
    _require_api_key()

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGIONS,
        "bookmakers": BOOKMAKERS,
        "markets": "h2h",
        "oddsFormat": "american",
    }

    resp = requests.get(EVENTS_URL, params=params, timeout=30)

    print("EVENTS STATUS:", resp.status_code)
    print("EVENTS PREVIEW:", resp.text[:300])

    resp.raise_for_status()
    events = resp.json()

    print(f"Events returned: {len(events)}")

    return events


# ======================
# FETCH EVENT PROPS
# ======================
def fetch_event_props(event_id):
    _require_api_key()

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGIONS,
        "bookmakers": BOOKMAKERS,
        "markets": ",".join(MARKET_MAP.keys()),
        "oddsFormat": "american",
    }

    url = EVENT_ODDS_URL.format(event_id=event_id)
    resp = requests.get(url, params=params, timeout=30)

    print(f"\nEVENT {event_id} STATUS:", resp.status_code)
    print(f"EVENT {event_id} PREVIEW:", resp.text[:200])

    resp.raise_for_status()
    return resp.json()


# ======================
# EXTRACT PROPS
# ======================
def extract_prop_rows(event_payload, prop_date):
    rows = []

    bookmakers = event_payload.get("bookmakers", [])
    print("Bookmakers found:", len(bookmakers))

    for book in bookmakers:
        sportsbook = book.get("title", "Unknown")

        for market in book.get("markets", []):
            if market.get("key") not in MARKET_MAP:
                continue

            stat_type = MARKET_MAP[market["key"]]

            for outcome in market.get("outcomes", []):
                side = outcome.get("name")
                player_name = outcome.get("description") or outcome.get("participant")
                line_value = outcome.get("point")

                if side not in ("Over", "Under"):
                    continue
                if not player_name or line_value is None:
                    continue

                rows.append(
                    {
                        "player_name": player_name,
                        "stat_type": stat_type,
                        "line_value": float(line_value),
                        "sportsbook": sportsbook,
                        "prop_date": prop_date,
                    }
                )

    print("Rows extracted:", len(rows))
    return rows


# ======================
# LOAD PLAYERS
# ======================
def load_players_lookup():
    q = "SELECT player_id, full_name FROM players"
    with engine.begin() as conn:
        df = pd.read_sql(text(q), conn)

    df["norm_name"] = df["full_name"].map(normalize_name)
    return df


def load_name_map():
    try:
        with engine.begin() as conn:
            df = pd.read_sql(text("SELECT api_name, player_id FROM player_name_map"), conn)
        return df
    except:
        return pd.DataFrame()


# ======================
# UPSERT
# ======================
def upsert_daily_props(rows):
    if not rows:
        print("❌ No props collected")
        return 0

    df = pd.DataFrame(rows)
    df["norm_name"] = df["player_name"].map(normalize_name)

    players = load_players_lookup()
    name_map = load_name_map()

    merged = df.merge(players[["player_id", "norm_name"]], on="norm_name", how="left")

    print("Matched players:", merged["player_id"].notna().sum())

    if not name_map.empty:
        fallback = df.merge(name_map, left_on="player_name", right_on="api_name", how="left")
        merged["player_id"] = merged["player_id"].fillna(fallback["player_id"])

    merged = merged.dropna(subset=["player_id"])
    print("Final matched:", len(merged))

    if merged.empty:
        print("❌ No matches after mapping")
        return 0

    merged["player_id"] = merged["player_id"].astype(int)

    rows_to_write = merged[
        ["player_id", "stat_type", "line_value", "sportsbook", "prop_date"]
    ].to_dict(orient="records")

    print("Writing rows:", len(rows_to_write))

    sql = """
    INSERT INTO daily_prop_lines (
        player_id, stat_type, line_value, sportsbook, prop_date
    )
    VALUES (
        :player_id, :stat_type, :line_value, :sportsbook, :prop_date
    )
    ON CONFLICT (player_id, stat_type, sportsbook, prop_date)
    DO UPDATE SET
        line_value = EXCLUDED.line_value,
        created_at = CURRENT_TIMESTAMP
    """

    with engine.begin() as conn:
        conn.execute(text(sql), rows_to_write)

    return len(rows_to_write)


# ======================
# MAIN
# ======================
def load_daily_props_from_odds_api():
    events = fetch_today_events()

    if not events:
        print("❌ No events found")
        return

    all_rows = []

    for event in events:
        event_id = event["id"]
        commence = event.get("commence_time")

        if not commence:
            continue

        try:
            prop_date = datetime.fromisoformat(commence.replace("Z", "+00:00")).date().isoformat()

            payload = fetch_event_props(event_id)
            rows = extract_prop_rows(payload, prop_date)

            print(f"Event {event_id} -> {len(rows)} props")

            all_rows.extend(rows)

        except Exception as e:
            print("❌ Failed event:", e)

    print("\nTOTAL ROWS:", len(all_rows))

    inserted = upsert_daily_props(all_rows)

    print(f"\n✅ FINAL INSERTED: {inserted}")


if __name__ == "__main__":
    load_daily_props_from_odds_api()