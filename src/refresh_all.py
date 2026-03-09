from src.ingest_players import load_teams_and_players
from src.ingest_games import load_team_games_and_player_logs
from src.metrics import rebuild_aggregates_and_efficiency

if __name__ == "__main__":
    load_teams_and_players()
    load_team_games_and_player_logs(team_abbreviation="NYK", season="2024-25")
    rebuild_aggregates_and_efficiency(season_label="2024-25")
    print("Refresh complete.")