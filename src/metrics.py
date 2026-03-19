import pandas as pd
from sqlalchemy import text

from src.db import engine


def rebuild_aggregates_and_efficiency(season_label: str = "2025-26") -> None:
    season_q = """
    SELECT season_id
    FROM seasons
    WHERE season_label = :season_label
    """

    stats_q = """
    SELECT
        pg.player_id,
        g.season_id,
        pg.points,
        pg.rebounds,
        pg.assists,
        pg.minutes,
        pg.fg_made,
        pg.fg_attempts,
        pg.three_made,
        pg.three_attempts,
        pg.ft_made,
        pg.ft_attempts,
        pg.steals,
        pg.blocks,
        pg.turnovers
    FROM player_game_stats pg
    JOIN games g
        ON pg.game_id = g.game_id
    WHERE g.season_id = :season_id
    """

    with engine.begin() as conn:
        season_row = conn.execute(
            text(season_q),
            {"season_label": season_label},
        ).fetchone()

        if not season_row:
            raise ValueError(f"Season {season_label} not found.")

        season_id = int(season_row[0])

        df = pd.read_sql(
            text(stats_q),
            conn,
            params={"season_id": season_id},
        )

    if df.empty:
        print("No player game stats found for aggregate rebuild.")
        return

    numeric_cols = [
        "points",
        "rebounds",
        "assists",
        "minutes",
        "fg_made",
        "fg_attempts",
        "three_made",
        "three_attempts",
        "ft_made",
        "ft_attempts",
        "steals",
        "blocks",
        "turnovers",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    agg = (
        df.groupby(["player_id", "season_id"], as_index=False)
        .agg(
            games_played=("player_id", "size"),
            avg_points=("points", "mean"),
            avg_rebounds=("rebounds", "mean"),
            avg_assists=("assists", "mean"),
            total_minutes=("minutes", "sum"),
            total_fg_made=("fg_made", "sum"),
            total_fg_attempts=("fg_attempts", "sum"),
            total_three_made=("three_made", "sum"),
            total_three_attempts=("three_attempts", "sum"),
            total_ft_made=("ft_made", "sum"),
            total_ft_attempts=("ft_attempts", "sum"),
            total_steals=("steals", "sum"),
            total_blocks=("blocks", "sum"),
            total_turnovers=("turnovers", "sum"),
        )
        .copy()
    )

    # Per-36 stats
    agg["per36_points"] = agg.apply(
        lambda r: (r["avg_points"] * r["games_played"] * 36 / r["total_minutes"])
        if r["total_minutes"] > 0
        else 0,
        axis=1,
    )
    agg["per36_rebounds"] = agg.apply(
        lambda r: (r["avg_rebounds"] * r["games_played"] * 36 / r["total_minutes"])
        if r["total_minutes"] > 0
        else 0,
        axis=1,
    )
    agg["per36_assists"] = agg.apply(
        lambda r: (r["avg_assists"] * r["games_played"] * 36 / r["total_minutes"])
        if r["total_minutes"] > 0
        else 0,
        axis=1,
    )

    # Shooting percentages
    agg["fg_pct"] = agg.apply(
        lambda r: (r["total_fg_made"] / r["total_fg_attempts"] * 100)
        if r["total_fg_attempts"] > 0
        else 0,
        axis=1,
    )
    agg["three_pct"] = agg.apply(
        lambda r: (r["total_three_made"] / r["total_three_attempts"] * 100)
        if r["total_three_attempts"] > 0
        else 0,
        axis=1,
    )
    agg["ft_pct"] = agg.apply(
        lambda r: (r["total_ft_made"] / r["total_ft_attempts"] * 100)
        if r["total_ft_attempts"] > 0
        else 0,
        axis=1,
    )

    # Keep only final aggregated_stats columns
    agg = agg[
        [
            "player_id",
            "season_id",
            "games_played",
            "avg_points",
            "avg_rebounds",
            "avg_assists",
            "per36_points",
            "per36_rebounds",
            "per36_assists",
            "fg_pct",
            "three_pct",
            "ft_pct",
        ]
    ].copy()

    # Round values for cleaner storage
    round_cols = [
        "avg_points",
        "avg_rebounds",
        "avg_assists",
        "per36_points",
        "per36_rebounds",
        "per36_assists",
        "fg_pct",
        "three_pct",
        "ft_pct",
    ]
    agg[round_cols] = agg[round_cols].round(2)

    # Simple player efficiency model
    eff = (
        df.groupby(["player_id", "season_id"], as_index=False)
        .agg(
            games_played=("player_id", "size"),
            points=("points", "sum"),
            rebounds=("rebounds", "sum"),
            assists=("assists", "sum"),
            steals=("steals", "sum"),
            blocks=("blocks", "sum"),
            turnovers=("turnovers", "sum"),
            fg_made=("fg_made", "sum"),
            fg_attempts=("fg_attempts", "sum"),
            ft_made=("ft_made", "sum"),
            ft_attempts=("ft_attempts", "sum"),
        )
        .copy()
    )

    eff["efficiency_score"] = (
        eff["points"]
        + eff["rebounds"]
        + eff["assists"]
        + eff["steals"]
        + eff["blocks"]
        - (eff["fg_attempts"] - eff["fg_made"])
        - (eff["ft_attempts"] - eff["ft_made"])
        - eff["turnovers"]
    ) / eff["games_played"].replace(0, pd.NA)

    eff["efficiency_score"] = eff["efficiency_score"].fillna(0).round(2)

    eff = eff[
        [
            "player_id",
            "season_id",
            "efficiency_score",
        ]
    ].copy()

    with engine.begin() as conn:
        # Clear old season rows first so refresh can rerun safely
        conn.execute(
            text("DELETE FROM aggregated_stats WHERE season_id = :season_id"),
            {"season_id": season_id},
        )
        conn.execute(
            text("DELETE FROM player_efficiency WHERE season_id = :season_id"),
            {"season_id": season_id},
        )

        agg.to_sql("aggregated_stats", conn, if_exists="append", index=False)
        eff.to_sql("player_efficiency", conn, if_exists="append", index=False)

    print(f"Rebuilt aggregated_stats for {len(agg)} players.")
    print(f"Rebuilt player_efficiency for {len(eff)} players.")