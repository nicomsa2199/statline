CREATE OR REPLACE VIEW v_team_summary AS
SELECT
    g.team_id,
    t.team_name,
    COUNT(*) AS games_played,
    AVG(g.team_score) AS avg_points_for,
    AVG(g.opponent_score) AS avg_points_against,
    SUM(CASE WHEN g.result = 'W' THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN g.result = 'L' THEN 1 ELSE 0 END) AS losses
FROM games g
JOIN teams t ON g.team_id = t.team_id
GROUP BY g.team_id, t.team_name;

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