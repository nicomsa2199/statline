CREATE OR REPLACE VIEW v_team_summary AS
WITH team_game_pairs AS (
    SELECT
        g1.game_id,
        g1.team_id,
        t1.team_name,
        g1.team_score AS points_for,
        g2.team_score AS points_against,
        g1.result
    FROM games g1
    LEFT JOIN games g2
        ON g1.game_id = g2.game_id
       AND g1.team_id <> g2.team_id
    JOIN teams t1
        ON g1.team_id = t1.team_id
)
SELECT
    team_id,
    team_name,
    COUNT(*) AS games_played,
    AVG(points_for) AS avg_points_for,
    AVG(points_against) AS avg_points_against,
    SUM(CASE WHEN result = 'W' THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) AS losses
FROM team_game_pairs
GROUP BY team_id, team_name;

CREATE OR REPLACE VIEW v_recent_player_games AS
SELECT
    p.full_name,
    p.player_id,
    pg.game_id,
    g.game_date,
    pg.points,
    pg.rebounds,
    pg.assists,
    pg.steals,
    pg.blocks,
    pg.turnovers,
    pg.minutes,
    pg.plus_minus
FROM player_game_stats pg
JOIN players p ON pg.player_id = p.player_id
JOIN games g ON pg.game_id = g.game_id;