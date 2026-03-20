# StatLine

StatLine is an NBA analytics platform designed to analyze player performance, team trends, matchup dynamics, and betting market evaluation.

The goal of this project was to simulate the type of analytics tools used internally at sportsbooks, combining data ingestion, database modeling, analytics, and visualization into a single application.

This project explores the intersection of sports analytics, data engineering, and product development. The goal was to create a platform that reflects the types of tools analysts may use internally within sports analytics and sportsbook environments.

Link: 
https://statline.streamlit.app/
---

# Features

## Player Analytics
Analyze individual player performance with:

- Game log trends
- Rolling averages
- Season averages
- Shooting percentages
- Performance projections
- Prop bet insights

---

## Team Analytics

Evaluate team performance with:

- Team scoring trends
- Win/loss performance
- Average points for and against
- Top player contributions
  
<img width="1466" height="893" alt="Screenshot 2026-03-20 at 4 11 49 PM" src="https://github.com/user-attachments/assets/dfd1ab83-369a-4431-b553-00e6c4705b50" />

---

## Matchup Comparison

Compare two teams head-to-head using:

- Projected scores
- Win probability estimates
- Team statistics
- Key player comparisons

This simulates pre-game matchup analysis used in sports analytics and betting contexts.
<img width="1477" height="848" alt="Screenshot 2026-03-20 at 4 06 30 PM" src="https://github.com/user-attachments/assets/996182ab-fab9-459c-81a8-937ea61881cf" />


---

## League Leaders

View league leaders across major statistical categories to benchmark player performance across the NBA.

<img width="1466" height="893" alt="Screenshot 2026-03-20 at 4 12 23 PM" src="https://github.com/user-attachments/assets/0a7c7fe9-15ae-41c5-a7f5-dc9341607beb" />


---

# Data Pipeline

StatLine uses an automated data pipeline to collect and analyze NBA data.

**Data Source**

NBA Stats API

**Pipeline**

The database serves as the central analytics layer powering the visualizations and projections used in the application.

Additional Data Sources:
- Odds API (daily sportsbook prop lines)

Pipeline Enhancements:
- Daily prop ingestion and normalization
- Player name mapping and reconciliation
- Automated upserts for daily betting markets
- Integration of predictions with live betting lines

---

# Database Structure

The project uses a relational data model with the following core entities:

- players
- teams
- games
- player_game_stats
- player_predictions

The **player_game_stats** table acts as the primary fact table linking players and games while storing performance metrics such as:

- points
- rebounds
- assists
- steals
- blocks
- shooting statistics

daily_prop_lines
Stores sportsbook betting lines for player props

prop_results (in progress)

Tracks historical outcomes of prop bets for performance evaluation

---

# Analytics & Projections

Player projections are generated using a weighted statistical model that incorporates:

- Rolling averages (last 3, 5, 10 games)
- Season-long performance trends
- Minutes and usage proxies
- Opponent defensive context
- Game pace adjustments
- Home/away splits
- Rest days and fatigue factors
- Injury-based usage and minutes adjustments

These projections are used to estimate expected player performance (ex: points, rebounds, assists) and evaluate betting market inefficiencies.
<img width="1466" height="893" alt="Screenshot 2026-03-20 at 4 07 35 PM" src="https://github.com/user-attachments/assets/3066ccb1-ad13-4713-a592-b4d3823e18f5" />
<img width="1466" height="893" alt="Screenshot 2026-03-20 at 4 07 48 PM" src="https://github.com/user-attachments/assets/4578a7b6-1f38-4aac-9db4-e0ad14a7df73" />



# Daily Prop Engine (NEW)
StatLine includes a Daily Prop Engine that evaluates player prop betting opportunities by combining model projections with live sportsbook lines.

Features:
- Automated ingestion of daily prop lines via Odds API
- Player-level projections for points, rebounds, assists, and PRA
- Edge calculation (Projection - Line)
- Confidence scoring and recommendation system
- Ranked prop board highlighting top opportunities

This simulates how sportsbooks and analytics teams identify value in betting markets.
<img width="1475" height="816" alt="Screenshot 2026-03-20 at 4 02 55 PM" src="https://github.com/user-attachments/assets/92e797a9-38cc-46a1-b164-9e91bf507833" />


---

# Tech Stack

StatLine was built using the following technologies:

- Python
- SQL
- SQLAlchemy
- PostgreSQL / Neon
- Streamlit
- Plotly
- NBA Stats API
- The Odds API

---

# Running the Project Locally

Clone the repository:

```bash
git clone https://github.com/nicomsa2199/statline.git
cd statline

Install dependencies:
pip install -r requirements.txt

Set database connection:
DATABASE_URL=************

Run application:
streamlit run app.py

# What Makes StatLine Different

Unlike typical sports dashboards, StatLine combines:

- Data engineering (ETL pipelines, database modeling)
- Statistical modeling (player projections)
- Product design (interactive dashboards)
- Betting analytics (prop evaluation engine)

The platform bridges the gap between analytics and real-world decision-making, simulating tools used by sportsbooks and professional analysts.

# Roadmap

- Track historical prop performance (win rate, ROI)
- Add probability-based modeling (hit rates instead of raw edges)
- Support multiple sportsbooks and line comparison
- Build automated pick posting system
- Improve model calibration and backtesting
