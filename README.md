# StatLine

StatLine is an NBA analytics platform designed to analyze player performance, team trends, matchup dynamics, and betting insights.

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

---

## Matchup Comparison

Compare two teams head-to-head using:

- Projected scores
- Win probability estimates
- Team statistics
- Key player comparisons

This simulates pre-game matchup analysis used in sports analytics and betting contexts.

---

## League Leaders

View league leaders across major statistical categories to benchmark player performance across the NBA.

---

# Data Pipeline

StatLine uses an automated data pipeline to collect and analyze NBA data.

**Data Source**

NBA Stats API

**Pipeline**

The database serves as the central analytics layer powering the visualizations and projections used in the application.

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

---

# Analytics & Projections

Player projections are currently generated using historical performance trends including:

- rolling averages
- recent game performance
- season averages

These projections estimate expected player performance for:

- points
- rebounds
- assists

The system also compares projections against potential betting lines to highlight possible value opportunities.

---

# Tech Stack

StatLine was built using the following technologies:

- Python
- SQL
- PostgreSQL / Neon
- Streamlit
- Plotly
- NBA Stats API

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
