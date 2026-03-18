from sqlalchemy import text
import pandas as pd

from src.db import engine


def recommendation_from_edge(edge: float) -> str:
    if edge >= 5:
        return "Strong Over"
    if edge >= 2:
        return "Lean Over"
    if edge <= -5:
        return "Strong Under"
    if edge <= -2:
        return "Lean Under"
    return "No Edge"


def model_side_from_edge(edge: float) -> str:
    if edge > 0:
        return "OVER"
    if edge < 0:
        return "UNDER"
    return "NONE"


def outcome_side(actual: float, line_value: float) -> str:
    if actual > line_value:
        return "OVER"
    if actual < line_value:
        return "UNDER"
    return "PUSH"


def evaluate_props_for_date(prop_date: str | None = None) -> None:
    if prop_date:
        date_filter = "WHERE dpl.prop_date = :prop_date"
        params = {"prop_date": prop_date}
    else:
        date_filter = ""
        params = {}

    q = f"""
    SELECT
        dpl.prop_id,
        dpl.player_id,
        dpl.stat_type,
        dpl.line_value,
        dpl.prop_date,
        CASE
            WHEN dpl.stat_type = 'POINTS' THEN pp.pred_points
            WHEN dpl.stat_type = 'REBOUNDS' THEN pp.pred_rebounds
            WHEN dpl.stat_type = 'ASSISTS' THEN pp.pred_assists
            WHEN dpl.stat_type = 'PRA' THEN (pp.pred_points + pp.pred_rebounds + pp.pred_assists)
        END AS projection,
        CASE
            WHEN dpl.stat_type = 'POINTS' THEN pg.points
            WHEN dpl.stat_type = 'REBOUNDS' THEN pg.rebounds
            WHEN dpl.stat_type = 'ASSISTS' THEN pg.assists
            WHEN dpl.stat_type = 'PRA' THEN (pg.points + pg.rebounds + pg.assists)
        END AS actual_value
    FROM daily_prop_lines dpl
    JOIN player_predictions pp
        ON dpl.player_id = pp.player_id
    JOIN player_game_stats pg
        ON dpl.player_id = pg.player_id
    JOIN games g
        ON pg.game_id = g.game_id
    {date_filter}
      AND g.game_date::date = dpl.prop_date
    """

    if not prop_date:
        q = q.replace("WHERE", "WHERE 1=1", 1)

    with engine.begin() as conn:
        df = pd.read_sql(text(q), conn, params=params)

    if df.empty:
        print("No props found to evaluate.")
        return

    df["projection"] = pd.to_numeric(df["projection"], errors="coerce")
    df["actual_value"] = pd.to_numeric(df["actual_value"], errors="coerce")
    df["line_value"] = pd.to_numeric(df["line_value"], errors="coerce")

    df = df.dropna(subset=["projection", "actual_value", "line_value"]).copy()
    if df.empty:
        print("No valid evaluated props after cleaning.")
        return

    df["edge"] = df["projection"] - df["line_value"]
    df["recommendation"] = df["edge"].apply(recommendation_from_edge)
    df["model_side"] = df["edge"].apply(model_side_from_edge)
    df["outcome_side"] = df.apply(lambda r: outcome_side(r["actual_value"], r["line_value"]), axis=1)

    df["is_correct"] = df.apply(
        lambda r: True if r["model_side"] in ["OVER", "UNDER"] and r["model_side"] == r["outcome_side"] else False,
        axis=1,
    )

    rows = df[
        [
            "prop_id",
            "player_id",
            "stat_type",
            "line_value",
            "projection",
            "actual_value",
            "recommendation",
            "edge",
            "outcome_side",
            "model_side",
            "is_correct",
            "prop_date",
        ]
    ].to_dict(orient="records")

    upsert_sql = """
    INSERT INTO prop_results (
        prop_id,
        player_id,
        stat_type,
        line_value,
        projection,
        actual_value,
        recommendation,
        edge,
        outcome_side,
        model_side,
        is_correct,
        prop_date
    )
    VALUES (
        :prop_id,
        :player_id,
        :stat_type,
        :line_value,
        :projection,
        :actual_value,
        :recommendation,
        :edge,
        :outcome_side,
        :model_side,
        :is_correct,
        :prop_date
    )
    ON CONFLICT (prop_id)
    DO UPDATE SET
        projection = EXCLUDED.projection,
        actual_value = EXCLUDED.actual_value,
        recommendation = EXCLUDED.recommendation,
        edge = EXCLUDED.edge,
        outcome_side = EXCLUDED.outcome_side,
        model_side = EXCLUDED.model_side,
        is_correct = EXCLUDED.is_correct,
        evaluated_at = CURRENT_TIMESTAMP
    """

    with engine.begin() as conn:
        conn.execute(text(upsert_sql), rows)

    print(f"Evaluated {len(rows)} props.")


if __name__ == "__main__":
    evaluate_props_for_date()