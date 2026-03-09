import numpy as np
import pandas as pd
from sqlalchemy import text
from sklearn.linear_model import LinearRegression
from src.db import engine


def _weighted_projection(series: pd.Series) -> float:
    if series.empty:
        return 0.0

    season_avg = series.mean()
    last10_avg = series.tail(10).mean() if len(series) >= 10 else series.mean()
    last5_avg = series.tail(5).mean() if len(series) >= 5 else series.mean()

    pred = 0.5 * last5_avg + 0.3 * last10_avg + 0.2 * season_avg
    return float(pred)


def _trend_projection(series: pd.Series) -> float:
    if series.empty:
        return 0.0

    recent = series.tail(10).reset_index(drop=True)

    if len(recent) < 2:
        return float(recent.iloc[-1])

    X = np.arange(len(recent)).reshape(-1, 1)
    y = recent.values

    model = LinearRegression()
    model.fit(X, y)

    next_idx = np.array([[len(recent)]])
    pred = model.predict(next_idx)[0]
    return float(pred)


def rebuild_player_predictions(season_label: str = "2025-26") -> None:
    q = """
    SELECT
        pg.player_id,
        g.game_date,
        pg.points,
        pg.rebounds,
        pg.assists
    FROM player_game_stats pg
    JOIN games g
        ON pg.game_id = g.game_id
    JOIN seasons s
        ON g.season_id = s.season_id
    WHERE s.season_label = :season_label
    ORDER BY pg.player_id, g.game_date
    """

    df = pd.read_sql(text(q), engine, params={"season_label": season_label})

    if df.empty:
        print("No data found for predictions.")
        return

    season_id = int(
    pd.read_sql(
        text("SELECT season_id FROM seasons WHERE season_label = :season_label"),
        engine,
        params={"season_label": season_label},
    ).iloc[0, 0]
)

    prediction_rows = []

    for player_id, grp in df.groupby("player_id"):
        grp = grp.sort_values("game_date")

        points_series = grp["points"]
        rebounds_series = grp["rebounds"]
        assists_series = grp["assists"]

        pred_points = _weighted_projection(points_series)
        pred_rebounds = _weighted_projection(rebounds_series)
        pred_assists = _weighted_projection(assists_series)

        trend_points = _trend_projection(points_series)
        trend_rebounds = _trend_projection(rebounds_series)
        trend_assists = _trend_projection(assists_series)

        prediction_rows.append(
            {
                "player_id": int(player_id),
                "season_id": int(season_id),
                "pred_points": round(pred_points, 2),
                "pred_rebounds": round(pred_rebounds, 2),
                "pred_assists": round(pred_assists, 2),
                "trend_points": round(trend_points, 2),
                "trend_rebounds": round(trend_rebounds, 2),
                "trend_assists": round(trend_assists, 2),
                "model_type": "weighted_avg_plus_trend",
            }
        )

    pred_df = pd.DataFrame(prediction_rows)

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM player_predictions WHERE season_id = :season_id"),
            {"season_id": int(season_id)},
        )
        pred_df.to_sql("player_predictions", conn, if_exists="append", index=False)

    print("Player predictions loaded.")