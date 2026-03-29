from sqlalchemy import text
from src.db import engine


def grade_saved_props() -> None:
    update_sql = """
    WITH candidate_games AS (
        SELECT
            pr.result_id,
            pr.player_id,
            pr.stat_type,
            pr.line_value,
            pr.pick_side,
            pr.prop_date,
            g.game_id,
            g.game_date,
            pg.points,
            pg.rebounds,
            pg.assists,
            ROW_NUMBER() OVER (
                PARTITION BY pr.result_id
                ORDER BY DATE(g.game_date) ASC
            ) AS rn
        FROM prop_results pr
        JOIN player_game_stats pg
            ON pr.player_id = pg.player_id
        JOIN games g
            ON pg.game_id = g.game_id
        WHERE DATE(g.game_date) >= pr.prop_date
          AND DATE(g.game_date) <= pr.prop_date + INTERVAL '2 days'
          AND pr.actual_value IS NULL
    ),
    actual_stats AS (
        SELECT
            result_id,
            CASE
                WHEN stat_type = 'POINTS' THEN points::numeric
                WHEN stat_type = 'REBOUNDS' THEN rebounds::numeric
                WHEN stat_type = 'ASSISTS' THEN assists::numeric
                WHEN stat_type = 'PRA' THEN (points + rebounds + assists)::numeric
            END AS actual_value
        FROM candidate_games
        WHERE rn = 1
    )
    UPDATE prop_results pr
    SET
        actual_value = a.actual_value,
        actual_result = CASE
            WHEN a.actual_value > pr.line_value THEN 'OVER'
            WHEN a.actual_value < pr.line_value THEN 'UNDER'
            ELSE 'PUSH'
        END,
        correct_pick = CASE
            WHEN a.actual_value = pr.line_value THEN NULL
            WHEN pr.pick_side = CASE
                WHEN a.actual_value > pr.line_value THEN 'OVER'
                WHEN a.actual_value < pr.line_value THEN 'UNDER'
                ELSE 'PUSH'
            END THEN 1
            ELSE 0
        END,
        outcome_side = CASE
            WHEN a.actual_value > pr.line_value THEN 'OVER'
            WHEN a.actual_value < pr.line_value THEN 'UNDER'
            ELSE 'PUSH'
        END,
        model_side = pr.pick_side,
        is_correct = CASE
            WHEN a.actual_value = pr.line_value THEN NULL
            WHEN pr.pick_side = CASE
                WHEN a.actual_value > pr.line_value THEN 'OVER'
                WHEN a.actual_value < pr.line_value THEN 'UNDER'
                ELSE 'PUSH'
            END THEN TRUE
            ELSE FALSE
        END,
        units = CASE
            WHEN a.actual_value = pr.line_value THEN 0
            WHEN pr.pick_side = CASE
                WHEN a.actual_value > pr.line_value THEN 'OVER'
                WHEN a.actual_value < pr.line_value THEN 'UNDER'
                ELSE 'PUSH'
            END THEN 0.91
            ELSE -1
        END,
        evaluated_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    FROM actual_stats a
    WHERE pr.result_id = a.result_id
    """

    summary_sql = """
    SELECT
        COUNT(*) AS total_saved_picks,
        COUNT(*) FILTER (WHERE actual_value IS NOT NULL) AS total_graded_picks,
        COALESCE(SUM(correct_pick), 0) AS correct_picks,
        ROUND(
            100.0 * COALESCE(SUM(correct_pick), 0)
            / NULLIF(COUNT(*) FILTER (WHERE correct_pick IS NOT NULL), 0),
            2
        ) AS win_percentage,
        ROUND(COALESCE(SUM(units), 0)::numeric, 2) AS total_units
    FROM prop_results
    """

    with engine.begin() as conn:
        result = conn.execute(text(update_sql))
        summary = conn.execute(text(summary_sql)).mappings().one()

    print("Finished grading saved props.")
    print(f"Rows updated: {result.rowcount}")
    print(f"Total saved picks: {summary['total_saved_picks']}")
    print(f"Total graded picks: {summary['total_graded_picks']}")
    print(f"Correct picks: {summary['correct_picks']}")
    print(f"Win %: {summary['win_percentage']}")
    print(f"Total Units: {summary['total_units']}")


if __name__ == "__main__":
    grade_saved_props()