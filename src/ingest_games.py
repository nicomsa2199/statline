import time
from typing import Callable

import pandas as pd
from sqlalchemy import text
from nba_api.stats.static import teams as nba_teams
from nba_api.stats.endpoints import (
    leaguegamefinder,
    commonteamroster,
    playergamelog,
)

from src.db import engine


def ensure_season(season_label: str) -> int:
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO seasons (season_label)
                VALUES (:season_label)
                ON CONFLICT (season_label) DO NOTHING
            """),
            {"season_label": season_label},
        )

        row = conn.execute(
            text("""
                SELECT season_id
                FROM seasons
                WHERE season_label = :season_label
            """),
            {"season_label": season_label},
        ).fetchone()

    return int(row[0])


def get_team_id(team_abbreviation: str) -> int:
    for team in nba_teams.get_teams():
        if team["abbreviation"] == team_abbreviation:
            return int(team["id"])
    raise ValueError(f"Team {team_abbreviation} not found")


def _safe_api_fetch(fetch_fn: Callable[[], pd.DataFrame], retries: int = 3, delay: int = 2) -> pd.DataFrame:
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            return fetch_fn()
        except Exception as e:
            last_error = e
            print(f"API call failed (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(delay)
    raise last_error


def _to_python_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    clean_df = df.copy()
    clean_df = clean_df.where(pd.notnull(clean_df), None)

    records = []
    for row in clean_df.to_dict(orient="records"):
        fixed = {}
        for k, v in row.items():
            if hasattr(v, "item"):
                fixed[k] = v.item()
            else:
                fixed[k] = v
        records.append(fixed)
    return records


def _upsert_games(final_games: pd.DataFrame) -> None:
    if final_games.empty:
        return

    final_games = final_games.copy()
    final_games["game_id"] = final_games["game_id"].astype(str)
    final_games["team_id"] = final_games["team_id"].astype(int)

    final_games = final_games.drop_duplicates(subset=["game_id", "team_id"], keep="first")

    records = _to_python_records(final_games)

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO games (
                    game_id,
                    season_id,
                    game_date,
                    team_id,
                    opponent_team_id,
                    matchup,
                    home_or_away,
                    team_score,
                    opponent_score,
                    result
                )
                VALUES (
                    :game_id,
                    :season_id,
                    :game_date,
                    :team_id,
                    :opponent_team_id,
                    :matchup,
                    :home_or_away,
                    :team_score,
                    :opponent_score,
                    :result
                )
                ON CONFLICT (game_id, team_id) DO UPDATE
                SET
                    season_id = EXCLUDED.season_id,
                    game_date = EXCLUDED.game_date,
                    opponent_team_id = EXCLUDED.opponent_team_id,
                    matchup = EXCLUDED.matchup,
                    home_or_away = EXCLUDED.home_or_away,
                    team_score = EXCLUDED.team_score,
                    result = EXCLUDED.result,
                    opponent_score = COALESCE(EXCLUDED.opponent_score, games.opponent_score),
                    last_updated = CURRENT_TIMESTAMP
            """),
            records,
        )

        # Once both team rows exist for a game, backfill opponent_score from the opposite row
        conn.execute(
            text("""
                UPDATE games g
                SET opponent_score = opp.team_score,
                    last_updated = CURRENT_TIMESTAMP
                FROM games opp
                WHERE g.game_id = opp.game_id
                  AND g.team_id <> opp.team_id
                  AND (
                      g.opponent_score IS NULL
                      OR g.opponent_score <> opp.team_score
                  )
            """)
        )


def _upsert_players(roster_players: pd.DataFrame) -> None:
    if roster_players.empty:
        return

    records = _to_python_records(roster_players)

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO players (
                    player_id,
                    first_name,
                    last_name,
                    full_name,
                    jersey_name,
                    height,
                    weight,
                    birthdate,
                    team_id,
                    position,
                    is_active
                )
                VALUES (
                    :player_id,
                    :first_name,
                    :last_name,
                    :full_name,
                    :jersey_name,
                    :height,
                    :weight,
                    :birthdate,
                    :team_id,
                    :position,
                    :is_active
                )
                ON CONFLICT (player_id) DO UPDATE
                SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    full_name = EXCLUDED.full_name,
                    jersey_name = EXCLUDED.jersey_name,
                    team_id = EXCLUDED.team_id,
                    position = EXCLUDED.position,
                    is_active = EXCLUDED.is_active,
                    last_updated = CURRENT_TIMESTAMP
            """),
            records,
        )


def load_team_games_and_player_logs(
    team_abbreviation: str = "NYK",
    season: str = "2025-26",
) -> None:
    team_id = get_team_id(team_abbreviation)
    season_id = ensure_season(season)

    games = _safe_api_fetch(
        lambda: leaguegamefinder.LeagueGameFinder(
            team_id_nullable=team_id,
            season_nullable=season,
            season_type_nullable="Regular Season",
        ).get_data_frames()[0]
    )

    time.sleep(1)

    if games.empty:
        print(f"No games found for {team_abbreviation}.")
        return

    games["game_id"] = games["GAME_ID"].astype(str)
    games["game_date"] = pd.to_datetime(games["GAME_DATE"]).dt.date
    games["team_id"] = games["TEAM_ID"].astype(int)
    games["matchup"] = games["MATCHUP"]
    games["home_or_away"] = games["MATCHUP"].apply(
        lambda x: "Away" if "@" in x else "Home"
    )
    games["team_score"] = games["PTS"]
    games["result"] = games["WL"]

    opp_abbrev = games["MATCHUP"].str.split().str[-1]
    team_map = {t["abbreviation"]: int(t["id"]) for t in nba_teams.get_teams()}
    games["opponent_team_id"] = opp_abbrev.map(team_map)

    # This will get backfilled later via self-join in _upsert_games()
    games["opponent_score"] = None
    games["season_id"] = season_id

    final_games = games[
        [
            "game_id",
            "season_id",
            "game_date",
            "team_id",
            "opponent_team_id",
            "matchup",
            "home_or_away",
            "team_score",
            "opponent_score",
            "result",
        ]
    ].copy()

    final_games["game_id"] = final_games["game_id"].astype(str)
    final_games["team_id"] = final_games["team_id"].astype(int)
    final_games = final_games.drop_duplicates(subset=["game_id", "team_id"], keep="first")

    _upsert_games(final_games)

    roster = _safe_api_fetch(
        lambda: commonteamroster.CommonTeamRoster(
            team_id=team_id,
            season=season,
        ).get_data_frames()[0]
    )

    time.sleep(1)

    roster_players = pd.DataFrame(
        {
            "player_id": roster["PLAYER_ID"].astype(int),
            "first_name": roster["PLAYER"].apply(
                lambda x: str(x).split(" ", 1)[0] if " " in str(x) else str(x)
            ),
            "last_name": roster["PLAYER"].apply(
                lambda x: str(x).split(" ", 1)[1] if " " in str(x) else ""
            ),
            "full_name": roster["PLAYER"].astype(str),
            "jersey_name": roster["PLAYER"].apply(lambda x: str(x).split(" ")[-1]),
            "height": None,
            "weight": None,
            "birthdate": None,
            "team_id": team_id,
            "position": roster["POSITION"] if "POSITION" in roster.columns else None,
            "is_active": True,
        }
    )

    _upsert_players(roster_players)

    stat_rows = []

    for player_id in roster["PLAYER_ID"].tolist():
        try:
            logs = _safe_api_fetch(
                lambda pid=int(player_id): playergamelog.PlayerGameLog(
                    player_id=pid,
                    season=season,
                    season_type_all_star="Regular Season",
                ).get_data_frames()[0]
            )

            time.sleep(1)

            if logs.empty:
                continue

            logs["player_id"] = int(player_id)
            logs["game_id"] = logs["Game_ID"].astype(str)
            logs["minutes"] = None
            logs["points"] = logs["PTS"]
            logs["rebounds"] = logs["REB"]
            logs["assists"] = logs["AST"]
            logs["steals"] = logs["STL"]
            logs["blocks"] = logs["BLK"]
            logs["turnovers"] = logs["TOV"]
            logs["fg_attempts"] = logs["FGA"]
            logs["fg_made"] = logs["FGM"]
            logs["three_attempts"] = logs["FG3A"]
            logs["three_made"] = logs["FG3M"]
            logs["ft_attempts"] = logs["FTA"]
            logs["ft_made"] = logs["FTM"]
            logs["plus_minus"] = logs["PLUS_MINUS"]

            stat_rows.append(
                logs[
                    [
                        "player_id",
                        "game_id",
                        "minutes",
                        "points",
                        "rebounds",
                        "assists",
                        "steals",
                        "blocks",
                        "turnovers",
                        "fg_attempts",
                        "fg_made",
                        "three_attempts",
                        "three_made",
                        "ft_attempts",
                        "ft_made",
                        "plus_minus",
                    ]
                ]
            )

        except Exception as e:
            print(f"Failed for player {player_id}: {e}")

    if stat_rows:
        stats_df = pd.concat(stat_rows, ignore_index=True)
        stats_df["game_id"] = stats_df["game_id"].astype(str)
        stats_df["player_id"] = stats_df["player_id"].astype(int)

        stats_df = stats_df.drop_duplicates(subset=["player_id", "game_id"], keep="first")

        with engine.begin() as conn:
            valid_player_ids = pd.read_sql(
                text("SELECT player_id FROM players"),
                conn,
            )["player_id"].tolist()

            valid_game_ids = pd.read_sql(
                text("SELECT DISTINCT game_id FROM games"),
                conn,
            )["game_id"].astype(str).tolist()

            existing_pairs = pd.read_sql(
                text("SELECT player_id, game_id FROM player_game_stats"),
                conn,
            )

            if not existing_pairs.empty:
                existing_pairs["game_id"] = existing_pairs["game_id"].astype(str)
                existing_pairs["player_id"] = existing_pairs["player_id"].astype(int)

            stats_df = stats_df[
                stats_df["player_id"].isin(valid_player_ids)
                & stats_df["game_id"].isin(valid_game_ids)
            ]

            if not existing_pairs.empty:
                existing_set = set(zip(existing_pairs["player_id"], existing_pairs["game_id"]))
                stats_df = stats_df[
                    ~stats_df.apply(
                        lambda row: (int(row["player_id"]), str(row["game_id"])) in existing_set,
                        axis=1,
                    )
                ]

            if not stats_df.empty:
                stats_df.to_sql(
                    "player_game_stats",
                    conn,
                    if_exists="append",
                    index=False,
                )

    print(f"{team_abbreviation} games and player logs loaded.")