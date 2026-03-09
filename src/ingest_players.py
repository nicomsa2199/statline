import pandas as pd
from sqlalchemy import text
from nba_api.stats.static import teams as nba_teams
from nba_api.stats.static import players as nba_players
from src.db import engine

def load_teams_and_players() -> None:
    teams_df = pd.DataFrame(nba_teams.get_teams())
    teams_df = teams_df.rename(columns={
        "id": "team_id",
        "full_name": "team_name",
        "abbreviation": "team_abbreviation",
        "city": "city"
    })

    teams_df["conference"] = None
    teams_df["division"] = None

    teams_df = teams_df[[
        "team_id", "team_name", "team_abbreviation",
        "city", "conference", "division"
    ]]

    players_df = pd.DataFrame(nba_players.get_active_players())
    players_df = players_df.rename(columns={
        "id": "player_id",
        "full_name": "full_name",
        "first_name": "first_name",
        "last_name": "last_name",
        "is_active": "is_active"
    })

    players_df["jersey_name"] = players_df["last_name"]
    players_df["height"] = None
    players_df["weight"] = None
    players_df["birthdate"] = None
    players_df["team_id"] = None
    players_df["position"] = None

    players_df = players_df[[
        "player_id", "first_name", "last_name", "full_name",
        "jersey_name", "height", "weight", "birthdate",
        "team_id", "position", "is_active"
    ]]

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE player_game_stats, aggregated_stats, player_efficiency, injuries, games, players, teams, seasons RESTART IDENTITY CASCADE"))
        teams_df.to_sql("teams", conn, if_exists="append", index=False)
        players_df.to_sql("players", conn, if_exists="append", index=False)

    print("Teams and players loaded.")