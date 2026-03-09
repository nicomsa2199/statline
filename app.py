import base64
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from src.db import engine

st.set_page_config(
    page_title="StatLine",
    layout="wide",
    initial_sidebar_state="collapsed",
)

LOGO_PATH = "assets/statline_logo.png"


def get_base64_image(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return base64.b64encode(file_path.read_bytes()).decode()


def inject_css():
    logo_b64 = get_base64_image(LOGO_PATH)

    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top, rgba(255, 59, 59, 0.10) 0%, rgba(10, 15, 28, 0.98) 25%, rgba(4, 7, 14, 1) 60%, rgba(2, 4, 9, 1) 100%);
            color: #f5f7fb;
        }

        [data-testid="stAppViewContainer"] {
            background: transparent;
        }

        [data-testid="stHeader"] {
            background: rgba(0,0,0,0);
        }

        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 3rem;
            max-width: 1250px;
        }

        .hero {
            position: relative;
            overflow: hidden;
            border-radius: 30px;
            padding: 1.5rem 2.2rem 2rem 2.2rem;
            background:
                linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01)),
                radial-gradient(circle at left center, rgba(255,59,59,0.22), rgba(255,59,59,0.03) 38%, transparent 55%);
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: 0 0 40px rgba(255,59,59,0.12);
            margin-bottom: 1.2rem;
            width: 100%;
        }

        .hero::after {
            content: "";
            position: absolute;
            inset: auto -5% 12% -5%;
            height: 3px;
            background: linear-gradient(90deg, transparent, #ff3b3b 18%, #ff6b6b 50%, #ff3b3b 82%, transparent);
            box-shadow: 0 0 18px rgba(255,59,59,0.9);
        }

        .hero-logo-wrap {
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 0.8rem;
        }

        .hero-logo {
            width: min(100%, 1300px);
            max-height: 300px;
            object-fit: contain;
            display: block;
        }

        .hero-title {
            font-size: 2.4rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: #ffffff;
            margin: 0;
            text-align: center;
        }

        .hero-subtitle {
            color: #e5e7eb;
            font-size: 1.05rem;
            margin-top: 0.4rem;
            text-align: center;
        }

        .hero-subtitle-secondary {
            color: #9ca7b8;
            font-size: 0.95rem;
            letter-spacing: 0.03em;
            margin-top: 0.15rem;
            text-align: center;
        }

        .section-title {
            font-size: 1.55rem;
            font-weight: 750;
            color: #ffffff;
            margin: 0.25rem 0 1rem 0;
        }

        .subtle-label {
            color: #9ca7b8;
            text-transform: uppercase;
            letter-spacing: 0.10em;
            font-size: 0.82rem;
            margin-bottom: 0.4rem;
        }

        .metric-card {
            background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.025));
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 22px;
            padding: 1rem 0.95rem;
            min-height: 112px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.28);
        }

        .metric-value {
            color: #ffffff;
            font-size: 1.95rem;
            font-weight: 800;
            line-height: 1.1;
            margin-top: 0.3rem;
        }

        .metric-name {
            color: #b7bfcb;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.82rem;
        }

        .panel {
            background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 24px;
            padding: 1.1rem;
            box-shadow: 0 12px 30px rgba(0,0,0,0.22);
            margin-bottom: 1rem;
        }

        .projection-card {
            background: linear-gradient(135deg, rgba(255,59,59,0.16), rgba(255,255,255,0.03));
            border: 1px solid rgba(255,59,59,0.28);
            border-radius: 20px;
            padding: 1rem;
            box-shadow: 0 0 24px rgba(255,59,59,0.10);
        }

        .recent-game-card {
            background: rgba(255,255,255,0.035);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 18px;
            padding: 1rem;
            margin-bottom: 0.75rem;
        }

        .recent-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
        }

        .recent-main {
            color: #ffffff;
            font-size: 1rem;
            font-weight: 700;
        }

        .recent-sub {
            color: #aeb7c4;
            font-size: 0.85rem;
            margin-top: 0.25rem;
        }

        .recent-stat {
            color: #ff6b6b;
            font-weight: 700;
            font-size: 1rem;
        }

        .footer-note {
            color: #8f98a8;
            font-size: 0.88rem;
            margin-top: 0.6rem;
        }

        .stRadio label, .stSelectbox label {
            color: #d8dde6 !important;
            font-weight: 600 !important;
        }

        div[data-baseweb="select"] > div {
            background-color: rgba(255,255,255,0.06) !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
            border-radius: 14px !important;
            color: white !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if logo_b64:
        st.markdown(
            f"""
            <div class="hero">
                <div class="hero-logo-wrap">
                    <img class="hero-logo" src="data:image/png;base64,{logo_b64}" />
                </div>
                <h1 class="hero-title">StatLine</h1>
                <div class="hero-subtitle">
                    The Pulse of the Game
                </div>
                <div class="hero-subtitle-secondary">
                    Player Performance • Team Trends • League Intelligence
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="hero">
                <h1 class="hero-title">StatLine</h1>
                <div class="hero-subtitle">
                    The Pulse of the Game
                </div>
                <div class="hero-subtitle-secondary">
                    Player Performance • Team Trends • League Intelligence
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def safe_metric(value, digits=1):
    if pd.isna(value):
        return "0.0"
    return f"{float(value):.{digits}f}"


@st.cache_data(ttl=3600)
def load_players():
    q = """
    SELECT DISTINCT p.player_id, p.full_name, t.team_abbreviation
    FROM players p
    JOIN player_game_stats pg ON p.player_id = pg.player_id
    LEFT JOIN teams t ON p.team_id = t.team_id
    ORDER BY p.full_name
    """
    return pd.read_sql(text(q), engine)


@st.cache_data(ttl=3600)
def load_teams():
    q = """
    SELECT DISTINCT t.team_id, t.team_name, t.team_abbreviation
    FROM teams t
    JOIN games g ON t.team_id = g.team_id
    ORDER BY t.team_name
    """
    return pd.read_sql(text(q), engine)


@st.cache_data(ttl=3600)
def load_player_stats(player_id):
    q = """
    SELECT
        g.game_date,
        pg.points,
        pg.rebounds,
        pg.assists,
        pg.steals,
        pg.blocks,
        pg.turnovers,
        pg.fg_made,
        pg.fg_attempts,
        pg.three_made,
        pg.three_attempts,
        pg.ft_made,
        pg.ft_attempts
    FROM player_game_stats pg
    JOIN games g ON pg.game_id = g.game_id
    WHERE pg.player_id = :player_id
    ORDER BY g.game_date
    """
    return pd.read_sql(text(q), engine, params={"player_id": player_id})


@st.cache_data(ttl=3600)
def load_efficiency_leaders():
    q = """
    SELECT
        p.full_name,
        t.team_abbreviation,
        e.efficiency_score
    FROM player_efficiency e
    JOIN players p ON e.player_id = p.player_id
    LEFT JOIN teams t ON p.team_id = t.team_id
    ORDER BY e.efficiency_score DESC
    LIMIT 20
    """
    return pd.read_sql(text(q), engine)


@st.cache_data(ttl=3600)
def load_scoring_leaders():
    q = """
    SELECT
        p.full_name,
        t.team_abbreviation,
        ROUND(AVG(pg.points)::numeric, 1) AS ppg
    FROM player_game_stats pg
    JOIN players p ON pg.player_id = p.player_id
    LEFT JOIN teams t ON p.team_id = t.team_id
    GROUP BY p.full_name, t.team_abbreviation
    ORDER BY ppg DESC
    LIMIT 20
    """
    return pd.read_sql(text(q), engine)


@st.cache_data(ttl=3600)
def load_team_summary():
    q = """
    SELECT team_name, games_played, avg_points_for, avg_points_against, wins, losses
    FROM v_team_summary
    ORDER BY wins DESC, avg_points_for DESC
    """
    return pd.read_sql(text(q), engine)


@st.cache_data(ttl=3600)
def load_team_games(team_id):
    q = """
    SELECT
        g.game_date,
        g.matchup,
        g.team_score,
        g.opponent_score,
        g.result
    FROM games g
    WHERE g.team_id = :team_id
    ORDER BY g.game_date
    """
    return pd.read_sql(text(q), engine, params={"team_id": team_id})


@st.cache_data(ttl=3600)
def load_team_player_leaders(team_id):
    q = """
    SELECT
        p.full_name,
        ROUND(AVG(pg.points)::numeric, 1) AS ppg,
        ROUND(AVG(pg.rebounds)::numeric, 1) AS rpg,
        ROUND(AVG(pg.assists)::numeric, 1) AS apg
    FROM player_game_stats pg
    JOIN players p ON pg.player_id = p.player_id
    WHERE p.team_id = :team_id
    GROUP BY p.full_name
    ORDER BY ppg DESC
    LIMIT 10
    """
    return pd.read_sql(text(q), engine, params={"team_id": team_id})


@st.cache_data(ttl=3600)
def load_player_prediction(player_id):
    q = """
    SELECT
        pred_points,
        pred_rebounds,
        pred_assists,
        trend_points,
        trend_rebounds,
        trend_assists
    FROM player_predictions
    WHERE player_id = :player_id
    """
    try:
        return pd.read_sql(text(q), engine, params={"player_id": player_id})
    except Exception:
        return pd.DataFrame()


inject_css()

view = st.radio(
    "View",
    ["Player Analytics", "Team Analytics", "League Leaders"],
    horizontal=True,
)

if view == "Player Analytics":
    players = load_players()

    if players.empty:
        st.error("No player data found.")
        st.stop()

    player_display = players["full_name"] + " • " + players["team_abbreviation"].fillna("")
    selected = st.selectbox("Select Player", player_display.tolist())

    selected_name = selected.split(" • ")[0]
    player_id = int(players.loc[players["full_name"] == selected_name, "player_id"].iloc[0])

    stats = load_player_stats(player_id)
    prediction = load_player_prediction(player_id)

    if stats.empty:
        st.warning("No game log data is available for this player.")
        st.stop()

    latest = stats.iloc[-1]

    fg_pct = (stats["fg_made"].sum() / stats["fg_attempts"].sum() * 100) if stats["fg_attempts"].sum() > 0 else 0
    three_pct = (stats["three_made"].sum() / stats["three_attempts"].sum() * 100) if stats["three_attempts"].sum() > 0 else 0
    ft_pct = (stats["ft_made"].sum() / stats["ft_attempts"].sum() * 100) if stats["ft_attempts"].sum() > 0 else 0

    st.markdown('<div class="section-title">Latest Game Snapshot</div>', unsafe_allow_html=True)

    cols = st.columns(6)
    cards = [
        (cols[0], latest["points"], "PTS"),
        (cols[1], latest["rebounds"], "REB"),
        (cols[2], latest["assists"], "AST"),
        (cols[3], latest["steals"], "STL"),
        (cols[4], latest["blocks"], "BLK"),
        (cols[5], latest["turnovers"], "TO"),
    ]

    for col, value, label in cards:
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-value">{safe_metric(value, 0)}</div>
                    <div class="metric-name">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    left, right = st.columns([1.3, 0.9])

    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Points Trend</div>', unsafe_allow_html=True)

        plot_df = stats.copy()
        plot_df["rolling_5"] = plot_df["points"].rolling(5).mean()

        fig = px.line(
            plot_df,
            x="game_date",
            y=["points", "rolling_5"],
            markers=True,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#f3f4f6",
            legend_title_text="",
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis_title="",
            yaxis_title="",
        )
        fig.update_traces(line=dict(width=3))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Recent Games</div>', unsafe_allow_html=True)

        recent_games = stats.sort_values("game_date", ascending=False).head(5)
        for _, row in recent_games.iterrows():
            st.markdown(
                f"""
                <div class="recent-game-card">
                    <div class="recent-row">
                        <div>
                            <div class="recent-main">{row['game_date']}</div>
                            <div class="recent-sub">
                                {int(row['points'])} PTS • {int(row['rebounds'])} REB • {int(row['assists'])} AST
                            </div>
                        </div>
                        <div class="recent-stat">{int(row['steals'])} STL / {int(row['blocks'])} BLK</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">Season Averages & Shooting</div>', unsafe_allow_html=True)
    row1 = st.columns(6)
    metrics = [
        (row1[0], stats["points"].mean(), "Season PPG"),
        (row1[1], stats["rebounds"].mean(), "Season RPG"),
        (row1[2], stats["assists"].mean(), "Season APG"),
        (row1[3], stats["steals"].mean(), "Season SPG"),
        (row1[4], stats["blocks"].mean(), "Season BPG"),
        (row1[5], stats["turnovers"].mean(), "Season TO"),
    ]

    for col, value, label in metrics:
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-value">{safe_metric(value, 1)}</div>
                    <div class="metric-name">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("")
    row2 = st.columns(3)
    shoot = [
        (row2[0], fg_pct, "FG%"),
        (row2[1], three_pct, "3P%"),
        (row2[2], ft_pct, "FT%"),
    ]

    for col, value, label in shoot:
        with col:
            st.markdown(
                f"""
                <div class="projection-card">
                    <div class="subtle-label">{label}</div>
                    <div class="metric-value">{safe_metric(value, 1)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if not prediction.empty:
        st.markdown('<div class="section-title">Next Game Projection</div>', unsafe_allow_html=True)
        pred = prediction.iloc[0]
        p1, p2, p3 = st.columns(3)
        proj = [
            (p1, pred["pred_points"], "Projected Points"),
            (p2, pred["pred_rebounds"], "Projected Rebounds"),
            (p3, pred["pred_assists"], "Projected Assists"),
        ]

        for col, value, label in proj:
            with col:
                st.markdown(
                    f"""
                    <div class="projection-card">
                        <div class="subtle-label">{label}</div>
                        <div class="metric-value">{safe_metric(value, 1)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

elif view == "Team Analytics":
    teams = load_teams()

    if teams.empty:
        st.error("No team data found.")
        st.stop()

    team_display = teams["team_name"] + " • " + teams["team_abbreviation"].fillna("")
    selected_team = st.selectbox("Select Team", team_display.tolist())

    selected_team_name = selected_team.split(" • ")[0]
    team_id = int(teams.loc[teams["team_name"] == selected_team_name, "team_id"].iloc[0])

    team_games = load_team_games(team_id)
    team_leaders = load_team_player_leaders(team_id)

    if team_games.empty:
        st.warning("No game data found for this team.")
        st.stop()

    wins = int((team_games["result"] == "W").sum())
    losses = int((team_games["result"] == "L").sum())
    avg_for = team_games["team_score"].mean()
    avg_against = team_games["opponent_score"].mean()

    st.markdown('<div class="section-title">Team Snapshot</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    cards = [
        (cols[0], wins, "Wins"),
        (cols[1], losses, "Losses"),
        (cols[2], avg_for, "Avg Points For"),
        (cols[3], avg_against, "Avg Points Against"),
    ]

    for col, value, label in cards:
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-value">{safe_metric(value, 1 if isinstance(value, float) else 0)}</div>
                    <div class="metric-name">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    left, right = st.columns([1.2, 1])

    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Team Scoring Trend</div>', unsafe_allow_html=True)

        team_plot = team_games.copy()
        team_plot["rolling_5"] = team_plot["team_score"].rolling(5).mean()

        fig = px.line(
            team_plot,
            x="game_date",
            y=["team_score", "rolling_5"],
            markers=True,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#f3f4f6",
            legend_title_text="",
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis_title="",
            yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Top Team Players</div>', unsafe_allow_html=True)
        st.dataframe(team_leaders, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">Recent Team Results</div>', unsafe_allow_html=True)
    recent_team_games = team_games.sort_values("game_date", ascending=False).head(8)

    for _, row in recent_team_games.iterrows():
        team_score = "-" if pd.isna(row["team_score"]) else str(int(row["team_score"]))
        opp_score = "-" if pd.isna(row["opponent_score"]) else str(int(row["opponent_score"]))
        result = row["result"] if pd.notna(row["result"]) else "-"

        st.markdown(
            f"""
            <div class="recent-game-card">
                <div class="recent-row">
                    <div>
                        <div class="recent-main">{row['game_date']} • {row['matchup']}</div>
                        <div class="recent-sub">
                            {team_score} - {opp_score}
                        </div>
                    </div>
                    <div class="recent-stat">{result}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

else:
    leaders = load_efficiency_leaders()
    scoring = load_scoring_leaders()
    team_summary = load_team_summary()

    st.markdown('<div class="section-title">League Leaders</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Efficiency Leaders</div>', unsafe_allow_html=True)
        st.dataframe(leaders, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Scoring Leaders</div>', unsafe_allow_html=True)
        st.dataframe(scoring, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Team Rankings</div>', unsafe_allow_html=True)
    st.dataframe(team_summary, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    '<div class="footer-note">StatLine • The Pulse of the Game</div>',
    unsafe_allow_html=True,
)