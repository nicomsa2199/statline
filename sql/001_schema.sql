CREATE TABLE IF NOT EXISTS seasons (
    season_id SERIAL PRIMARY KEY,
    season_label VARCHAR(20) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL,
    team_abbreviation VARCHAR(10),
    city VARCHAR(100),
    conference VARCHAR(20),
    division VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    jersey_name VARCHAR(100),
    height VARCHAR(20),
    weight INTEGER,
    birthdate DATE,
    team_id INTEGER REFERENCES teams(team_id),
    position VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS games (
    game_id VARCHAR(30) PRIMARY KEY,
    season_id INTEGER REFERENCES seasons(season_id),
    game_date DATE NOT NULL,
    team_id INTEGER REFERENCES teams(team_id),
    opponent_team_id INTEGER REFERENCES teams(team_id),
    matchup VARCHAR(50),
    home_or_away VARCHAR(10),
    team_score INTEGER,
    opponent_score INTEGER,
    result VARCHAR(5),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS player_game_stats (
    stat_id BIGSERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id),
    game_id VARCHAR(30) REFERENCES games(game_id),
    minutes DECIMAL(5,2),
    points INTEGER,
    rebounds INTEGER,
    assists INTEGER,
    steals INTEGER,
    blocks INTEGER,
    turnovers INTEGER,
    fg_attempts INTEGER,
    fg_made INTEGER,
    three_attempts INTEGER,
    three_made INTEGER,
    ft_attempts INTEGER,
    ft_made INTEGER,
    plus_minus INTEGER,
    UNIQUE(player_id, game_id)
);

CREATE TABLE IF NOT EXISTS injuries (
    injury_id BIGSERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id),
    season_id INTEGER REFERENCES seasons(season_id),
    injury_type VARCHAR(100),
    injury_description TEXT,
    injury_start_date DATE,
    injury_end_date DATE,
    status VARCHAR(50),
    minutes_restriction INTEGER
);

CREATE TABLE IF NOT EXISTS aggregated_stats (
    player_id INTEGER PRIMARY KEY REFERENCES players(player_id),
    season_id INTEGER REFERENCES seasons(season_id),
    games_played INTEGER,
    avg_points DECIMAL(8,2),
    avg_rebounds DECIMAL(8,2),
    avg_assists DECIMAL(8,2),
    per36_points DECIMAL(8,2),
    per36_rebounds DECIMAL(8,2),
    per36_assists DECIMAL(8,2),
    fg_pct DECIMAL(8,2),
    three_pct DECIMAL(8,2),
    ft_pct DECIMAL(8,2),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS player_efficiency (
    efficiency_id BIGSERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id),
    season_id INTEGER REFERENCES seasons(season_id),
    efficiency_score DECIMAL(8,2),
    offensive_contrib DECIMAL(8,2),
    defensive_contrib DECIMAL(8,2),
    durability_contrib DECIMAL(8,2),
    impact_contrib DECIMAL(8,2),
    role_adjustment DECIMAL(8,2),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season_id)
);

CREATE TABLE IF NOT EXISTS player_predictions (
    prediction_id BIGSERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(player_id),
    season_id INTEGER REFERENCES seasons(season_id),
    pred_points DECIMAL(8,2),
    pred_rebounds DECIMAL(8,2),
    pred_assists DECIMAL(8,2),
    trend_points DECIMAL(8,2),
    trend_rebounds DECIMAL(8,2),
    trend_assists DECIMAL(8,2),
    model_type VARCHAR(50),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season_id)
);