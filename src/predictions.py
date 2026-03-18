import pandas as pd
from sqlalchemy import text

from src.db import engine


def _safe_round(value, digits=2):
    if pd.isna(value):
        return None
    return round(float(value), digits)


def apply_context_adjustments(
    pred_points: float,
    pred_rebounds: float,
    pred_assists: float,
    opp_avg_points_allowed: float | None,
    recent_team_total: float | None,
):
    league_avg_points_allowed = 112.0
    league_avg_total = 225.0

    opp_factor = 1.0
    if opp_avg_points_allowed is not None and not pd.isna(opp_avg_points_allowed):
        opp_factor = float(opp_avg_points_allowed) / league_avg_points_allowed

    pace_factor = 1.0
    if recent_team_total is not None and not pd.isna(recent_team_total):
        pace_factor = float(recent_team_total) / league_avg_total

    pred_points = pred_points * opp_factor * pace_factor
    pred_rebounds = pred_rebounds * (0.98 + 0.04 * pace_factor)
    pred_assists = pred_assists * opp_factor * (0.98 + 0.04 * pace_factor)

    return pred_points, pred_rebounds, pred_assists


def rebuild_player_predictions(season_label: str = "2025-26") -> None:
    season_q = """
    SELECT season_id
    FROM seasons
    WHERE season_label = :season_label
    """

    stats_q = """
    SELECT
        pg.player_id,
        pg.game_id,
        g.game_date,
        g.team_id,
        g.opponent_team_id,
        g.home_or_away,
        pg.points,
        pg.rebounds,
        pg.assists,
        pg.minutes,
        pg.fg_attempts,
        pg.ft_attempts,
        pg.turnovers
    FROM player_game_stats pg
    JOIN games g
        ON pg.game_id = g.game_id
    WHERE g.season_id = :season_id
    ORDER BY pg.player_id, g.game_date
    """

    games_q = """
    SELECT
        game_id,
        game_date,
        team_id,
        opponent_team_id,
        team_score,
        opponent_score,
        home_or_away,
        result
    FROM games
    WHERE season_id = :season_id
    ORDER BY game_date
    """

    injury_q = """
    SELECT
        player_id,
        status,
        usage_boost,
        minutes_multiplier
    FROM player_injuries
    """

    with engine.begin() as conn:
        season_row = conn.execute(
            text(season_q),
            {"season_label": season_label},
        ).fetchone()

        if not season_row:
            raise ValueError(f"Season {season_label} not found.")

        season_id = int(season_row[0])

        stats_df = pd.read_sql(
            text(stats_q),
            conn,
            params={"season_id": season_id},
        )

        games_df = pd.read_sql(
            text(games_q),
            conn,
            params={"season_id": season_id},
        )

        try:
            injuries_df = pd.read_sql(text(injury_q), conn)
        except Exception:
            injuries_df = pd.DataFrame(columns=["player_id", "status", "usage_boost", "minutes_multiplier"])

    if stats_df.empty or games_df.empty:
        print("No stats or games found for predictions.")
        return

    stats_df["game_date"] = pd.to_datetime(stats_df["game_date"])
    games_df["game_date"] = pd.to_datetime(games_df["game_date"])

    numeric_cols = [
        "points",
        "rebounds",
        "assists",
        "minutes",
        "fg_attempts",
        "ft_attempts",
        "turnovers",
        "team_score",
        "opponent_score",
    ]

    for col in numeric_cols:
        if col in stats_df.columns:
            stats_df[col] = pd.to_numeric(stats_df[col], errors="coerce")
        if col in games_df.columns:
            games_df[col] = pd.to_numeric(games_df[col], errors="coerce")

    stats_df = stats_df.sort_values(["player_id", "game_date"]).reset_index(drop=True)
    games_df = games_df.sort_values(["team_id", "game_date"]).reset_index(drop=True)

    # Team-level pace proxy
    games_df["game_total_points"] = (
        games_df["team_score"].fillna(0) + games_df["opponent_score"].fillna(0)
    )

    # Team context built from prior games only
    team_context = (
        games_df.groupby("team_id", group_keys=False)
        .apply(
            lambda df: df.assign(
                team_avg_points_for=df["team_score"].shift(1).expanding().mean(),
                team_avg_points_against=df["opponent_score"].shift(1).expanding().mean(),
                recent_team_total=df["game_total_points"].shift(1).rolling(5, min_periods=1).mean(),
            )
        )
        .reset_index(drop=True)
    )

    team_context = team_context[
        [
            "game_id",
            "team_id",
            "opponent_team_id",
            "team_avg_points_for",
            "team_avg_points_against",
            "recent_team_total",
        ]
    ]

    # Opponent defense proxy
    opp_def_proxy = team_context[
        ["game_id", "team_id", "team_avg_points_against"]
    ].rename(
        columns={
            "team_id": "opponent_team_id",
            "team_avg_points_against": "opp_avg_points_allowed",
        }
    )

    stats_df = stats_df.merge(
        team_context[["game_id", "team_id", "recent_team_total"]],
        on=["game_id", "team_id"],
        how="left",
    )

    stats_df = stats_df.merge(
        opp_def_proxy,
        on=["game_id", "opponent_team_id"],
        how="left",
    )

    # Home / away
    stats_df["is_home"] = (stats_df["home_or_away"] == "Home").astype(int)

    # Rest days
    stats_df["rest_days"] = (
        stats_df.groupby("player_id")["game_date"]
        .diff()
        .dt.days
        .fillna(3)
    )

    def add_player_features(df: pd.DataFrame) -> pd.DataFrame:
        df = df.sort_values("game_date").copy()

        for stat in ["points", "rebounds", "assists", "minutes"]:
            df[f"{stat}_last_3"] = df[stat].shift(1).rolling(3, min_periods=1).mean()
            df[f"{stat}_last_5"] = df[stat].shift(1).rolling(5, min_periods=1).mean()
            df[f"{stat}_last_10"] = df[stat].shift(1).rolling(10, min_periods=1).mean()
            df[f"{stat}_season_avg"] = df[stat].shift(1).expanding().mean()

        # Usage proxy
        df["usage_proxy_last_5"] = (
            df["fg_attempts"].shift(1).rolling(5, min_periods=1).mean().fillna(0)
            + 0.44 * df["ft_attempts"].shift(1).rolling(5, min_periods=1).mean().fillna(0)
            + df["turnovers"].shift(1).rolling(5, min_periods=1).mean().fillna(0)
        )

        # Points per minute
        df["ppm_last_5"] = df["points_last_5"] / df["minutes_last_5"].replace(0, pd.NA)
        df["ppm_last_10"] = df["points_last_10"] / df["minutes_last_10"].replace(0, pd.NA)

        # Momentum
        df["points_momentum"] = df["points"].shift(1) - df["points_last_5"]
        df["rebounds_momentum"] = df["rebounds"].shift(1) - df["rebounds_last_5"]
        df["assists_momentum"] = df["assists"].shift(1) - df["assists_last_5"]

        return df

    features_df = (
        stats_df.groupby("player_id", group_keys=False)
        .apply(add_player_features)
        .reset_index(drop=True)
    )

    # Latest pregame snapshot per player
    latest_df = (
        features_df.sort_values(["player_id", "game_date"])
        .groupby("player_id", as_index=False)
        .tail(1)
        .copy()
    )

    if latest_df.empty:
        print("No feature rows available for predictions.")
        return

    # Merge injuries if available
    if not injuries_df.empty:
        latest_df = latest_df.merge(injuries_df, on="player_id", how="left")
    else:
        latest_df["status"] = None
        latest_df["usage_boost"] = 1.0
        latest_df["minutes_multiplier"] = 1.0

    league_avg_points_allowed = features_df["opp_avg_points_allowed"].dropna().mean()
    league_avg_total = features_df["recent_team_total"].dropna().mean()

    if pd.isna(league_avg_points_allowed):
        league_avg_points_allowed = 112.0
    if pd.isna(league_avg_total):
        league_avg_total = 225.0

    prediction_rows = []

    for _, row in latest_df.iterrows():
        recent_minutes = row["minutes_last_5"] if pd.notna(row["minutes_last_5"]) else row["minutes_season_avg"]
        if pd.isna(recent_minutes):
            recent_minutes = 28.0

        ppm = row["ppm_last_5"]
        if pd.isna(ppm):
            ppm = row["ppm_last_10"]
        if pd.isna(ppm):
            season_minutes = row["minutes_season_avg"]
            season_points = row["points_season_avg"]
            ppm = (
                season_points / season_minutes
                if pd.notna(season_minutes) and season_minutes not in [0, None]
                else 0.75
            )

        # Weighted core predictions
        pred_points = (
            (0.45 * row["points_last_5"] if pd.notna(row["points_last_5"]) else 0)
            + (0.25 * row["points_last_10"] if pd.notna(row["points_last_10"]) else 0)
            + (0.20 * row["points_season_avg"] if pd.notna(row["points_season_avg"]) else 0)
            + (0.10 * (ppm * recent_minutes) if pd.notna(ppm) and pd.notna(recent_minutes) else 0)
        )

        pred_rebounds = (
            (0.50 * row["rebounds_last_5"] if pd.notna(row["rebounds_last_5"]) else 0)
            + (0.30 * row["rebounds_last_10"] if pd.notna(row["rebounds_last_10"]) else 0)
            + (0.20 * row["rebounds_season_avg"] if pd.notna(row["rebounds_season_avg"]) else 0)
        )

        pred_assists = (
            (0.50 * row["assists_last_5"] if pd.notna(row["assists_last_5"]) else 0)
            + (0.30 * row["assists_last_10"] if pd.notna(row["assists_last_10"]) else 0)
            + (0.20 * row["assists_season_avg"] if pd.notna(row["assists_season_avg"]) else 0)
        )

        # Context adjustments
        pred_points, pred_rebounds, pred_assists = apply_context_adjustments(
            pred_points,
            pred_rebounds,
            pred_assists,
            row["opp_avg_points_allowed"],
            row["recent_team_total"],
        )

        # Home / away adjustment
        if row["is_home"] == 1:
            pred_points += 0.75
            pred_assists += 0.25
        else:
            pred_points -= 0.25

        # Rest adjustment
        if pd.notna(row["rest_days"]):
            if row["rest_days"] == 0:
                pred_points -= 1.0
                pred_rebounds -= 0.2
                pred_assists -= 0.2
            elif row["rest_days"] >= 2:
                pred_points += 0.5
                pred_assists += 0.15

        # Usage proxy boost
        if pd.notna(row["usage_proxy_last_5"]):
            usage_boost_extra = min(float(row["usage_proxy_last_5"]) * 0.08, 2.5)
            pred_points += usage_boost_extra

        # Injury adjustments
        status = row["status"] if "status" in row and pd.notna(row["status"]) else "ACTIVE"
        usage_boost = float(row["usage_boost"]) if "usage_boost" in row and pd.notna(row["usage_boost"]) else 1.0
        minutes_multiplier = (
            float(row["minutes_multiplier"])
            if "minutes_multiplier" in row and pd.notna(row["minutes_multiplier"])
            else 1.0
        )

        if status == "OUT":
            pred_points = 0
            pred_rebounds = 0
            pred_assists = 0
        elif status == "QUESTIONABLE":
            pred_points *= 0.85
            pred_rebounds *= 0.90
            pred_assists *= 0.90
        else:
            pred_points *= usage_boost * minutes_multiplier
            pred_rebounds *= minutes_multiplier
            pred_assists *= usage_boost * minutes_multiplier

        prediction_rows.append(
            {
                "player_id": int(row["player_id"]),
                "season_id": season_id,
                "pred_points": _safe_round(max(pred_points, 0)),
                "pred_rebounds": _safe_round(max(pred_rebounds, 0)),
                "pred_assists": _safe_round(max(pred_assists, 0)),
                "trend_points": _safe_round(row["points_last_5"]),
                "trend_rebounds": _safe_round(row["rebounds_last_5"]),
                "trend_assists": _safe_round(row["assists_last_5"]),
                "model_type": "weighted_context_injury_v3",
            }
        )

    predictions_df = pd.DataFrame(prediction_rows)

    upsert_sql = """
    INSERT INTO player_predictions (
        player_id,
        season_id,
        pred_points,
        pred_rebounds,
        pred_assists,
        trend_points,
        trend_rebounds,
        trend_assists,
        model_type
    )
    VALUES (
        :player_id,
        :season_id,
        :pred_points,
        :pred_rebounds,
        :pred_assists,
        :trend_points,
        :trend_rebounds,
        :trend_assists,
        :model_type
    )
    ON CONFLICT (player_id, season_id)
    DO UPDATE SET
        pred_points = EXCLUDED.pred_points,
        pred_rebounds = EXCLUDED.pred_rebounds,
        pred_assists = EXCLUDED.pred_assists,
        trend_points = EXCLUDED.trend_points,
        trend_rebounds = EXCLUDED.trend_rebounds,
        trend_assists = EXCLUDED.trend_assists,
        model_type = EXCLUDED.model_type,
        last_updated = CURRENT_TIMESTAMP
    """

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM player_predictions WHERE season_id = :season_id"),
            {"season_id": season_id},
        )
        conn.execute(text(upsert_sql), predictions_df.to_dict(orient="records"))

    print(f"Rebuilt player predictions for {len(predictions_df)} players.")