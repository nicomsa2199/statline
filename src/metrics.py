import pandas as pd
from sqlalchemy import text
from src.db import engine

def rebuild_aggregates_and_efficiency(season_label: str = "2024-25") -> None:
    query = """
    SELECT pg.*, g.season_id
    FROM player_game_stats pg
    JOIN games g ON pg.game_id = g.game_id
    JOIN seasons s ON g.season_id = s.season_id
    WHERE s.season_label = :season_label
    """
    df = pd.read_sql(text(query), engine, params={"season_label": season_label})

    if df.empty:
        print("No stats found.")
        return

    agg = df.groupby("player_id", as_index=False).agg(
        games_played=("game_id", "nunique"),
        avg_points=("points", "mean"),
        avg_rebounds=("rebounds", "mean"),
        avg_assists=("assists", "mean"),
        fg_made=("fg_made", "sum"),
        fg_attempts=("fg_attempts", "sum"),
        three_made=("three_made", "sum"),
        three_attempts=("three_attempts", "sum"),
        ft_made=("ft_made", "sum"),
        ft_attempts=("ft_attempts", "sum")
    )

    agg["per36_points"] = 0
    agg["per36_rebounds"] = 0
    agg["per36_assists"] = 0
    agg["fg_pct"] = (agg["fg_made"] / agg["fg_attempts"] * 100).fillna(0)
    agg["three_pct"] = (agg["three_made"] / agg["three_attempts"] * 100).fillna(0)
    agg["ft_pct"] = (agg["ft_made"] / agg["ft_attempts"] * 100).fillna(0)

    season_id = pd.read_sql(
        text("SELECT season_id FROM seasons WHERE season_label = :season_label"),
        engine,
        params={"season_label": season_label}
    ).iloc[0, 0]

    agg["season_id"] = season_id
    agg = agg[[
        "player_id", "season_id", "games_played", "avg_points", "avg_rebounds",
        "avg_assists", "per36_points", "per36_rebounds", "per36_assists",
        "fg_pct", "three_pct", "ft_pct"
    ]]

    eff = df.groupby("player_id", as_index=False).agg(
        points=("points", "mean"),
        rebounds=("rebounds", "mean"),
        assists=("assists", "mean"),
        steals=("steals", "mean"),
        blocks=("blocks", "mean"),
        turnovers=("turnovers", "mean"),
        plus_minus=("plus_minus", "mean"),
        games=("game_id", "nunique")
    )

    eff["offensive_contrib"] = eff["points"] * 0.35 + eff["assists"] * 0.25
    eff["defensive_contrib"] = eff["rebounds"] * 0.12 + eff["steals"] * 0.15 + eff["blocks"] * 0.13
    eff["durability_contrib"] = eff["games"] * 0.05
    eff["impact_contrib"] = eff["plus_minus"].fillna(0).clip(lower=0) * 0.10
    eff["role_adjustment"] = 0.25
    eff["efficiency_score"] = (
        eff["offensive_contrib"] +
        eff["defensive_contrib"] +
        eff["durability_contrib"] +
        eff["impact_contrib"] +
        eff["role_adjustment"] -
        eff["turnovers"] * 0.08
    ).clip(lower=0, upper=5)

    eff["season_id"] = season_id
    eff = eff[[
        "player_id", "season_id", "efficiency_score", "offensive_contrib",
        "defensive_contrib", "durability_contrib", "impact_contrib", "role_adjustment"
    ]]

    with engine.begin() as conn:
        agg.to_sql("aggregated_stats", conn, if_exists="append", index=False)
        eff.to_sql("player_efficiency", conn, if_exists="append", index=False)

    print("Aggregated stats and efficiency loaded.")