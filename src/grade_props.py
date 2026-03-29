from sqlalchemy import text
from src.db import engine


def grade_saved_props() -> None:
    update_sql = """
    WITH actual_stats AS (
        SELECT
            pr.result_id,
            CASE
                WHEN pr.stat_type = 'POINTS' THEN pg.points::numeric
                WHEN pr.stat_type = 'REBOUNDS' THEN pg.rebounds::numeric
                WHEN pr.stat_type = 'ASSISTS' THEN pg.assists::numeric
                WHEN pr.stat_type = 'PRA' THEN (pg.points + pg.rebounds + pg.assists)::numeric
            END AS actual_value
        FROM prop_results pr
        JOIN player_game_stats pg
            ON pr.player_id = pg.player_id
        JOIN games g
            ON pg.game_id = g.game_id
        WHERE pr.prop_date = DATE(g.game_date)
          AND pr.actual_value IS NULL
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
        evaluated_at = CURRENT_TIMESTAMP
    FROM actual_stats a
    WHERE pr.result_id = a.result_id
    """

    summary_sql = """
    SELECT
        COUNT(*) AS total_graded_picks,
        COALESCE(SUM(correct_pick), 0) AS correct_picks,
        ROUND(
            100.0 * COALESCE(SUM(correct_pick), 0) / NULLIF(COUNT(*), 0),
            2
        ) AS win_percentage
    FROM prop_results
    WHERE correct_pick IS NOT NULL
    """

    with engine.begin() as conn:
        conn.execute(text(update_sql))
        summary = conn.execute(text(summary_sql)).mappings().one()

    print("Finished grading saved props.")
    print(f"Total graded picks: {summary['total_graded_picks']}")
    print(f"Correct picks: {summary['correct_picks']}")
    print(f"Win %: {summary['win_percentage']}")


if __name__ == "__main__":
    grade_saved_props()