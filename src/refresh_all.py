import time
from nba_api.stats.static import teams as nba_teams
from src.ingest_players import load_teams_and_players
from src.ingest_games import load_team_games_and_player_logs
from src.metrics import rebuild_aggregates_and_efficiency
from src.predictions import rebuild_player_predictions


if __name__ == "__main__":
    load_teams_and_players()

    all_teams = nba_teams.get_teams()
    failed_teams = []

    for team in all_teams:
        abbrev = team["abbreviation"]
        print(f"Loading {abbrev}...")

        try:
            load_team_games_and_player_logs(
                team_abbreviation=abbrev,
                season="2025-26",
            )
            time.sleep(2)
        except Exception as e:
            print(f"Failed loading {abbrev}: {e}")
            failed_teams.append(abbrev)
            time.sleep(5)

    rebuild_aggregates_and_efficiency(season_label="2025-26")
    rebuild_player_predictions(season_label="2025-26")

    print("Full NBA refresh complete.")
    if failed_teams:
        print(f"Teams that failed: {failed_teams}")