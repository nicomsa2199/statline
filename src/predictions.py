import pandas as pd
from sqlalchemy import text

from src.db import engine


def _safe_round(value, digits=2):
    if pd.isna(value):
        return None
    return round(float(value), digits)


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(float(value), max_value))


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
        raw_opp_ratio = float(opp_avg_points_allowed) / league_avg_points_allowed
        opp_factor = 1.0 + (raw_opp_ratio - 1.0) * 0.35
        opp_factor = _clamp(opp_factor, 0.94, 1.06)

    pace_factor = 1.0
    if recent_team_total is not None and not pd.isna(recent_team_total):
        raw_pace_ratio = float(recent_team_total) / league_avg_total
        pace_factor = 1.0 + (raw_pace_ratio - 1.0) * 0.35
        pace_factor = _clamp(pace_factor, 0.95, 1.05)

    pred_points = pred_points * opp_factor * pace_factor
    pred_rebounds = pred_rebounds * (0.99 + 0.02 * pace_factor)
    pred_assists = pred_assists * (0.99 + 0.02 * pace_factor) * (0.995 + 0.015 * opp_factor)

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
    FROM (
        SELECT DISTINCT ON (pg.player_id, pg.game_id)
            pg.player_id,
            pg.game_id,
            pg.points,
            pg.rebounds,
            pg.assists,
            pg.minutes,
            pg.fg_attempts,
            pg.ft_attempts,
            pg.turnovers
        FROM player_game_stats pg
        ORDER BY pg.player_id, pg.game_id
    ) pg
    JOIN games g
        ON pg.game_id = g.game_id
    WHERE g.season_id = :season_id
    ORDER BY pg.player_id, g.game_date
    """

    games_q = """
    SELECT DISTINCT ON (game_id, team_id)
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
    ORDER BY game_id, team_id, game_date
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
            injuries_df = pd.DataFrame(
                columns=["player_id", "status", "usage_boost", "minutes_multiplier"]
            )

    if stats_df.empty or games_df.empty:
        print("No stats or games found for predictions.")
        return

    stats_df = stats_df.drop_duplicates(subset=["player_id", "game_id"]).copy()
    games_df = games_df.drop_duplicates(subset=["game_id", "team_id"]).copy()

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

    games_df["game_total_points"] = (
        games_df["team_score"].fillna(0) + games_df["opponent_score"].fillna(0)
    )

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

    stats_df["is_home"] = (stats_df["home_or_away"] == "Home").astype(int)

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

        df["minutes_last_5"] = df["minutes_last_5"].clip(lower=20)

        df["usage_proxy_last_5"] = (
            df["fg_attempts"].shift(1).rolling(5, min_periods=1).mean().fillna(0)
            + 0.44 * df["ft_attempts"].shift(1).rolling(5, min_periods=1).mean().fillna(0)
            + df["turnovers"].shift(1).rolling(5, min_periods=1).mean().fillna(0)
        )

        df["ppm_last_5"] = df["points_last_5"] / df["minutes_last_5"].replace(0, pd.NA)
        df["ppm_last_10"] = df["points_last_10"] / df["minutes_last_10"].replace(0, pd.NA)

        df["points_momentum"] = df["points"].shift(1) - df["points_last_5"]
        df["rebounds_momentum"] = df["rebounds"].shift(1) - df["rebounds_last_5"]
        df["assists_momentum"] = df["assists"].shift(1) - df["assists_last_5"]

        return df

    features_df = (
        stats_df.groupby("player_id", group_keys=False)
        .apply(add_player_features)
        .reset_index(drop=True)
    )

    latest_df = (
        features_df.sort_values(["player_id", "game_date"])
        .groupby("player_id", as_index=False)
        .tail(1)
        .copy()
    )

    if latest_df.empty:
        print("No feature rows available for predictions.")
        return

    if not injuries_df.empty:
        latest_df = latest_df.merge(injuries_df, on="player_id", how="left")
    else:
        latest_df["status"] = None
        latest_df["usage_boost"] = 1.0
        latest_df["minutes_multiplier"] = 1.0

    prediction_rows = []

    for _, row in latest_df.iterrows():
        minutes_last_5 = row["minutes_last_5"] if pd.notna(row["minutes_last_5"]) else None
        minutes_season_avg = row["minutes_season_avg"] if pd.notna(row["minutes_season_avg"]) else None

        if minutes_last_5 is not None and minutes_season_avg is not None:
            recent_minutes = max(float(minutes_last_5), float(minutes_season_avg) * 0.85)
        elif minutes_last_5 is not None:
            recent_minutes = float(minutes_last_5)
        elif minutes_season_avg is not None:
            recent_minutes = float(minutes_season_avg)
        else:
            recent_minutes = 28.0

        recent_minutes = _clamp(recent_minutes, 12.0, 40.0)

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

        ppm = _clamp(ppm, 0.25, 1.45)

        # raw point model
        raw_pred_points = (
            (0.30 * row["points_last_5"] if pd.notna(row["points_last_5"]) else 0)
            + (0.20 * row["points_last_10"] if pd.notna(row["points_last_10"]) else 0)
            + (0.30 * row["points_season_avg"] if pd.notna(row["points_season_avg"]) else 0)
            + (0.20 * (ppm * recent_minutes) if pd.notna(ppm) and pd.notna(recent_minutes) else 0)
        )

        # baseline anchor for points
        if pd.notna(row["points_season_avg"]):
            pred_points = 0.65 * raw_pred_points + 0.35 * float(row["points_season_avg"])
        else:
            pred_points = raw_pred_points

        # rebounds and assists: slightly more stable blend
        raw_pred_rebounds = (
            (0.40 * row["rebounds_last_5"] if pd.notna(row["rebounds_last_5"]) else 0)
            + (0.25 * row["rebounds_last_10"] if pd.notna(row["rebounds_last_10"]) else 0)
            + (0.25 * row["rebounds_season_avg"] if pd.notna(row["rebounds_season_avg"]) else 0)
            + (0.10 * row["rebounds_last_3"] if pd.notna(row["rebounds_last_3"]) else 0)
        )
        if pd.notna(row["rebounds_season_avg"]):
            pred_rebounds = 0.75 * raw_pred_rebounds + 0.25 * float(row["rebounds_season_avg"])
        else:
            pred_rebounds = raw_pred_rebounds

        raw_pred_assists = (
            (0.40 * row["assists_last_5"] if pd.notna(row["assists_last_5"]) else 0)
            + (0.25 * row["assists_last_10"] if pd.notna(row["assists_last_10"]) else 0)
            + (0.25 * row["assists_season_avg"] if pd.notna(row["assists_season_avg"]) else 0)
            + (0.10 * row["assists_last_3"] if pd.notna(row["assists_last_3"]) else 0)
        )
        if pd.notna(row["assists_season_avg"]):
            pred_assists = 0.75 * raw_pred_assists + 0.25 * float(row["assists_season_avg"])
        else:
            pred_assists = raw_pred_assists

        pred_points, pred_rebounds, pred_assists = apply_context_adjustments(
            pred_points,
            pred_rebounds,
            pred_assists,
            row["opp_avg_points_allowed"],
            row["recent_team_total"],
        )

        if row["is_home"] == 1:
            pred_points += 0.50
            pred_assists += 0.15
        else:
            pred_points -= 0.15

        if pd.notna(row["rest_days"]):
            if row["rest_days"] == 0:
                pred_points -= 0.75
                pred_rebounds -= 0.15
                pred_assists -= 0.15
            elif row["rest_days"] >= 2:
                pred_points += 0.25
                pred_assists += 0.10

        if pd.notna(row["usage_proxy_last_5"]):
            usage_boost_extra = min(float(row["usage_proxy_last_5"]) * 0.03, 1.0)
            pred_points += usage_boost_extra

        status = row["status"] if "status" in row and pd.notna(row["status"]) else "ACTIVE"
        usage_boost = float(row["usage_boost"]) if "usage_boost" in row and pd.notna(row["usage_boost"]) else 1.0
        minutes_multiplier = (
            float(row["minutes_multiplier"])
            if "minutes_multiplier" in row and pd.notna(row["minutes_multiplier"])
            else 1.0
        )

        usage_boost = _clamp(usage_boost, 0.85, 1.12)
        minutes_multiplier = _clamp(minutes_multiplier, 0.80, 1.10)

        if status == "OUT":
            pred_points = 0
            pred_rebounds = 0
            pred_assists = 0
        elif status == "QUESTIONABLE":
            pred_points *= 0.88
            pred_rebounds *= 0.92
            pred_assists *= 0.92
        else:
            pred_points *= usage_boost * minutes_multiplier
            pred_rebounds *= minutes_multiplier
            pred_assists *= usage_boost * minutes_multiplier

        # season floor
        if pd.notna(row["points_season_avg"]):
            pred_points = max(pred_points, float(row["points_season_avg"]) * 0.80)
        if pd.notna(row["rebounds_season_avg"]):
            pred_rebounds = max(pred_rebounds, float(row["rebounds_season_avg"]) * 0.70)
        if pd.notna(row["assists_season_avg"]):
            pred_assists = max(pred_assists, float(row["assists_season_avg"]) * 0.70)

        # recent trend floor
        trend_points = row["points_last_5"] if pd.notna(row["points_last_5"]) else row["points_season_avg"]
        trend_rebounds = row["rebounds_last_5"] if pd.notna(row["rebounds_last_5"]) else row["rebounds_season_avg"]
        trend_assists = row["assists_last_5"] if pd.notna(row["assists_last_5"]) else row["assists_season_avg"]

        if pd.notna(trend_points):
            pred_points = max(pred_points, float(trend_points) * 0.72)
        if pd.notna(trend_rebounds):
            pred_rebounds = max(pred_rebounds, float(trend_rebounds) * 0.65)
        if pd.notna(trend_assists):
            pred_assists = max(pred_assists, float(trend_assists) * 0.65)

        pred_points = _clamp(pred_points, 0, 45)
        pred_rebounds = _clamp(pred_rebounds, 0, 22)
        pred_assists = _clamp(pred_assists, 0, 16)

        prediction_rows.append(
            {
                "player_id": int(row["player_id"]),
                "season_id": season_id,
                "pred_points": _safe_round(pred_points),
                "pred_rebounds": _safe_round(pred_rebounds),
                "pred_assists": _safe_round(pred_assists),
                "trend_points": _safe_round(row["points_last_5"]),
                "trend_rebounds": _safe_round(row["rebounds_last_5"]),
                "trend_assists": _safe_round(row["assists_last_5"]),
                "model_type": "weighted_context_injury_v7_anchor",
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


if __name__ == "__main__":
    rebuild_player_predictions()