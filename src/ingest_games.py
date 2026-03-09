import time
import pandas as pd
from sqlalchemy import text
from nba_api.stats.static import teams as nba_teams
from nba_api.stats.endpoints import leaguegamefinder, commonteamroster, playergamelog
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

    return row[0]


def get_team_id(team_abbreviation: str) -> int:
    for team in nba_teams.get_teams():
        if team["abbreviation"] == team_abbreviation:
            return team["id"]
    raise ValueError(f"Team {team_abbreviation} not found")


def load_team_games_and_player_logs(
    team_abbreviation: str = "NYK",
    season: str = "2025-26",
) -> None:
    team_id = get_team_id(team_abbreviation)
    season_id = ensure_season(season)

    games = leaguegamefinder.LeagueGameFinder(
        team_id_nullable=team_id,
        season_nullable=season,
    ).get_data_frames()[0]

    time.sleep(1)

    if games.empty:
        print(f"No games found for {team_abbreviation}.")
        return

    games["game_id"] = games["GAME_ID"].astype(str)
    games["game_date"] = pd.to_datetime(games["GAME_DATE"]).dt.date
    games["team_id"] = games["TEAM_ID"]
    games["matchup"] = games["MATCHUP"]
    games["home_or_away"] = games["MATCHUP"].apply(
        lambda x: "Away" if "@" in x else "Home"
    )
    games["team_score"] = games["PTS"]
    games["result"] = games["WL"]

    opp_abbrev = games["MATCHUP"].str.split().str[-1]
    team_map = {t["abbreviation"]: t["id"] for t in nba_teams.get_teams()}
    games["opponent_team_id"] = opp_abbrev.map(team_map)
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
    ].drop_duplicates()

    # Append only new games instead of deleting everything
    with engine.begin() as conn:
        existing_game_ids = pd.read_sql(
            text("SELECT game_id FROM games"),
            conn,
        )["game_id"].astype(str).tolist()

        final_games["game_id"] = final_games["game_id"].astype(str)
        new_games = final_games[~final_games["game_id"].isin(existing_game_ids)]

        if not new_games.empty:
            new_games.to_sql("games", conn, if_exists="append", index=False)

    roster = commonteamroster.CommonTeamRoster(
        team_id=team_id,
        season=season,
    ).get_data_frames()[0]

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

    # Make sure roster players exist in players table
    with engine.begin() as conn:
        existing_ids = pd.read_sql(
            text("SELECT player_id FROM players"),
            conn,
        )["player_id"].tolist()

        missing_players = roster_players[
            ~roster_players["player_id"].isin(existing_ids)
        ]

        if not missing_players.empty:
            missing_players.to_sql("players", conn, if_exists="append", index=False)

        for _, row in roster_players.iterrows():
            conn.execute(
                text("""
                    UPDATE players
                    SET team_id = :team_id,
                        position = :position
                    WHERE player_id = :player_id
                """),
                {
                    "team_id": int(row["team_id"]),
                    "position": row["position"] if pd.notna(row["position"]) else None,
                    "player_id": int(row["player_id"]),
                },
            )

    stat_rows = []

    for player_id in roster["PLAYER_ID"].tolist():
        try:
            logs = playergamelog.PlayerGameLog(
                player_id=int(player_id),
                season=season,
            ).get_data_frames()[0]

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

        with engine.begin() as conn:
            valid_player_ids = pd.read_sql(
                text("SELECT player_id FROM players"),
                conn,
            )["player_id"].tolist()

            valid_game_ids = pd.read_sql(
                text("SELECT game_id FROM games"),
                conn,
            )["game_id"].astype(str).tolist()

            existing_pairs = pd.read_sql(
                text("SELECT player_id, game_id FROM player_game_stats"),
                conn,
            )

            if not existing_pairs.empty:
                existing_pairs["game_id"] = existing_pairs["game_id"].astype(str)

            stats_df["game_id"] = stats_df["game_id"].astype(str)

            stats_df = stats_df[
                stats_df["player_id"].isin(valid_player_ids)
                & stats_df["game_id"].isin(valid_game_ids)
            ].drop_duplicates(subset=["player_id", "game_id"])

            if not existing_pairs.empty:
                stats_df = stats_df.merge(
                    existing_pairs.assign(_exists=1),
                    on=["player_id", "game_id"],
                    how="left",
                )
                stats_df = stats_df[stats_df["_exists"].isna()].drop(columns=["_exists"])

            if not stats_df.empty:
                stats_df.to_sql(
                    "player_game_stats",
                    conn,
                    if_exists="append",
                    index=False,
                )

    print(f"{team_abbreviation} games and player logs loaded.")