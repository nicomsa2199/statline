import os
from datetime import datetime

import pandas as pd
import requests
from sqlalchemy import text

from src.db import engine

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


def _require_api_key() -> None:
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY is not set.")


def normalize_name(name: str) -> str:
    return " ".join(str(name).strip().lower().split())


def fetch_today_events() -> list[dict]:
    _require_api_key()

    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGIONS,
        "bookmakers": BOOKMAKERS,
        "markets": "h2h",
        "oddsFormat": "american",
    }

    resp = requests.get(EVENTS_URL, params=params, timeout=30)
    resp.raise_for_status()
    events = resp.json()

    print(f"Events returned from Odds API: {len(events)}")
    for event in events[:10]:
        print(
            "Event:",
            event.get("home_team"),
            "vs",
            event.get("away_team"),
            "| commence_time:",
            event.get("commence_time"),
        )

    return events


def fetch_event_props(event_id: str) -> dict:
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
    resp.raise_for_status()
    return resp.json()


def extract_prop_rows(event_payload: dict, prop_date: str) -> list[dict]:
    rows = []

    bookmakers = event_payload.get("bookmakers", [])
    print(f"Bookmakers in event payload: {len(bookmakers)}")

    for book in bookmakers:
        sportsbook = book.get("title", "Unknown")
        markets = book.get("markets", [])
        print(f"  {sportsbook} markets: {[m.get('key') for m in markets]}")

        for market in markets:
            market_key = market.get("key")
            if market_key not in MARKET_MAP:
                continue

            stat_type = MARKET_MAP[market_key]

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

    print(f"Raw extracted rows for event date {prop_date}: {len(rows)}")

    if not rows:
        return []

    df = pd.DataFrame(rows)

    df = df.drop_duplicates(
        subset=["player_name", "stat_type", "sportsbook", "prop_date", "line_value"]
    )

    df = (
        df.sort_values(
            ["player_name", "stat_type", "sportsbook", "prop_date", "line_value"],
            ascending=[True, True, True, True, True],
        )
        .drop_duplicates(
            subset=["player_name", "stat_type", "sportsbook", "prop_date"],
            keep="first",
        )
    )

    return df.to_dict(orient="records")


def load_players_lookup() -> pd.DataFrame:
    q = """
    SELECT player_id, full_name
    FROM players
    """
    with engine.begin() as conn:
        players_df = pd.read_sql(text(q), conn)

    players_df["norm_name"] = players_df["full_name"].map(normalize_name)
    return players_df


def load_name_map() -> pd.DataFrame:
    q = """
    SELECT api_name, player_id
    FROM player_name_map
    """
    try:
        with engine.begin() as conn:
            name_map_df = pd.read_sql(text(q), conn)
        return name_map_df
    except Exception:
        return pd.DataFrame(columns=["api_name", "player_id"])


def upsert_daily_props(rows: list[dict]) -> int:
    if not rows:
        print("No raw prop rows collected before matching.")
        return 0

    props_df = pd.DataFrame(rows)
    print(f"Raw prop rows before matching: {len(props_df)}")
    props_df["norm_name"] = props_df["player_name"].map(normalize_name)

    players_df = load_players_lookup()
    name_map_df = load_name_map()

    merged = props_df.merge(
        players_df[["player_id", "norm_name"]],
        on="norm_name",
        how="left",
    )

    direct_matched = merged["player_id"].notna().sum()
    print(f"Direct matched rows: {direct_matched}")

    if not name_map_df.empty:
        fallback = props_df.merge(
            name_map_df,
            left_on="player_name",
            right_on="api_name",
            how="left",
        )
        merged["player_id"] = merged["player_id"].fillna(fallback["player_id"])

    final_matched = merged["player_id"].notna().sum()
    print(f"Final matched rows after name_map fallback: {final_matched}")

    missing = merged[merged["player_id"].isna()]
    if not missing.empty:
        print("Unmatched player names from Odds API:")
        print(sorted(missing["player_name"].drop_duplicates().tolist())[:100])

    merged = merged.dropna(subset=["player_id"]).copy()
    if merged.empty:
        print("No prop lines matched players in your database.")
        return 0

    merged["player_id"] = merged["player_id"].astype(int)

    rows_to_write = merged[
        ["player_id", "stat_type", "line_value", "sportsbook", "prop_date"]
    ].to_dict(orient="records")

    print(f"Rows to write to daily_prop_lines: {len(rows_to_write)}")

    upsert_sql = """
    INSERT INTO daily_prop_lines (
        player_id,
        stat_type,
        line_value,
        sportsbook,
        prop_date
    )
    VALUES (
        :player_id,
        :stat_type,
        :line_value,
        :sportsbook,
        :prop_date
    )
    ON CONFLICT (player_id, stat_type, sportsbook, prop_date)
    DO UPDATE SET
        line_value = EXCLUDED.line_value,
        created_at = CURRENT_TIMESTAMP
    """

    with engine.begin() as conn:
        conn.execute(text(upsert_sql), rows_to_write)

    return len(rows_to_write)


def load_daily_props_from_odds_api() -> None:
    events = fetch_today_events()
    if not events:
        print("No NBA events found.")
        return

    all_rows = []

    for event in events:
        event_id = event["id"]
        commence = event.get("commence_time")

        if not commence:
            continue

        try:
            event_dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
            prop_date = event_dt.date().isoformat()

            payload = fetch_event_props(event_id)
            event_rows = extract_prop_rows(payload, prop_date)

            print(f"Event {event_id} -> extracted {len(event_rows)} props")
            all_rows.extend(event_rows)

        except Exception as e:
            print(f"Failed to fetch props for event {event_id}: {e}")

    print(f"Total rows collected before insert: {len(all_rows)}")

    inserted = upsert_daily_props(all_rows)
    print(f"Loaded {inserted} daily prop lines from Odds API.")


if __name__ == "__main__":
    load_daily_props_from_odds_api()