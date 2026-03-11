import base64
import math
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from src.db import engine


def get_player_headshot(player_id: int) -> str:
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"


def get_team_logo(team_abbrev: str) -> str:
    return f"https://a.espncdn.com/i/teamlogos/nba/500/{team_abbrev.lower()}.png"


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

        .leaderboard-list {
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
        }

        .leader-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 18px;
            padding: 0.85rem 1rem;
        }

        .leader-left {
            display: flex;
            align-items: center;
            gap: 0.9rem;
            min-width: 0;
        }

        .leader-rank {
            font-size: 1.1rem;
            font-weight: 800;
            color: #ff6b6b;
            width: 28px;
            flex-shrink: 0;
        }

        .leader-headshot {
            width: 52px;
            height: 52px;
            object-fit: cover;
            border-radius: 50%;
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.04);
            flex-shrink: 0;
        }

        .leader-logo {
            width: 28px;
            height: 28px;
            object-fit: contain;
            flex-shrink: 0;
        }

        .leader-name-wrap {
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
            min-width: 0;
        }

        .leader-name {
            color: #ffffff;
            font-weight: 700;
            font-size: 1rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .leader-team {
            color: #9ca7b8;
            font-size: 0.82rem;
            letter-spacing: 0.04em;
        }

        .leader-stat {
            color: #ffffff;
            font-size: 1.5rem;
            font-weight: 800;
            flex-shrink: 0;
        }

        .team-rank-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            margin-bottom: 0.75rem;
        }

        .team-rank-left {
            display: flex;
            align-items: center;
            gap: 0.9rem;
            min-width: 0;
        }

        .team-rank-logo {
            width: 42px;
            height: 42px;
            object-fit: contain;
            flex-shrink: 0;
        }

        .team-rank-name-wrap {
            display: flex;
            flex-direction: column;
            gap: 0.12rem;
        }

        .team-rank-name {
            color: #ffffff;
            font-weight: 700;
            font-size: 1rem;
        }

        .team-rank-sub {
            color: #9ca7b8;
            font-size: 0.82rem;
        }

        .team-rank-right {
            display: flex;
            gap: 1.2rem;
            align-items: center;
            flex-wrap: wrap;
            justify-content: flex-end;
        }

        .team-rank-stat {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            min-width: 58px;
        }

        .team-rank-stat-value {
            color: #ffffff;
            font-size: 1.05rem;
            font-weight: 800;
            line-height: 1.1;
        }

        .team-rank-stat-label {
            color: #9ca7b8;
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
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


def filter_by_window(df: pd.DataFrame, mode: str = "Season") -> pd.DataFrame:
    if df.empty:
        return df
    df = df.sort_values("game_date")
    if mode == "Last 5":
        return df.tail(5)
    if mode == "Last 10":
        return df.tail(10)
    return df


def get_recent_record(team_games_df: pd.DataFrame, n: int = 10) -> tuple[int, int]:
    recent = team_games_df.sort_values("game_date", ascending=False).head(n)
    wins = int((recent["result"] == "W").sum())
    losses = int((recent["result"] == "L").sum())
    return wins, losses


def projected_team_score(avg_for, opp_avg_against) -> float:
    if pd.isna(avg_for) or pd.isna(opp_avg_against):
        return 0.0
    return round((float(avg_for) + float(opp_avg_against)) / 2, 1)


def win_probability_from_net(net_diff: float) -> float:
    return 1 / (1 + math.exp(-net_diff / 4))


def prop_call(edge: float) -> str:
    if edge >= 2:
        return "Strong Over"
    if edge >= 0.75:
        return "Lean Over"
    if edge <= -2:
        return "Strong Under"
    if edge <= -0.75:
        return "Lean Under"
    return "No Edge"


def render_leaderboard(df: pd.DataFrame, stat_col: str, title: str):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown('<div class="leaderboard-list">', unsafe_allow_html=True)

    for rank, (_, row) in enumerate(df.head(10).iterrows(), start=1):
        team_abbrev = row["team_abbreviation"] if pd.notna(row["team_abbreviation"]) else ""
        headshot_html = ""
        logo_html = ""

        if "player_id" in row and pd.notna(row["player_id"]):
            headshot_html = f'<img class="leader-headshot" src="{get_player_headshot(int(row["player_id"]))}" />'

        if team_abbrev:
            logo_html = f'<img class="leader-logo" src="{get_team_logo(team_abbrev)}" />'

        stat_value = row[stat_col]

        st.markdown(
            f"""
            <div class="leader-row">
                <div class="leader-left">
                    <div class="leader-rank">#{rank}</div>
                    {headshot_html}
                    <div class="leader-name-wrap">
                        <div class="leader-name">{row['full_name']}</div>
                        <div class="leader-team">{team_abbrev}</div>
                    </div>
                    {logo_html}
                </div>
                <div class="leader-stat">{stat_value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_team_player_cards(df: pd.DataFrame, title: str):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown('<div class="leaderboard-list">', unsafe_allow_html=True)

    for _, row in df.iterrows():
        ppg = safe_metric(row["ppg"], 1) if "ppg" in row else "0.0"
        rpg = safe_metric(row["rpg"], 1) if "rpg" in row else "0.0"
        apg = safe_metric(row["apg"], 1) if "apg" in row else "0.0"

        headshot_html = ""
        if "player_id" in row and pd.notna(row["player_id"]):
            headshot_html = f'<img class="leader-headshot" src="{get_player_headshot(int(row["player_id"]))}" />'

        st.markdown(
            f"""
            <div class="leader-row">
                <div class="leader-left">
                    {headshot_html}
                    <div class="leader-name-wrap">
                        <div class="leader-name">{row['full_name']}</div>
                        <div class="leader-team">Top rotation contributor</div>
                    </div>
                </div>
                <div class="leader-stat" style="font-size:1rem;">
                    {ppg} PPG • {rpg} RPG • {apg} APG
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_team_rankings(df: pd.DataFrame, teams_df: pd.DataFrame, title: str = "Team Rankings"):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)

    merged = df.merge(
        teams_df[["team_name", "team_abbreviation"]],
        on="team_name",
        how="left",
    )

    for rank, (_, row) in enumerate(merged.head(10).iterrows(), start=1):
        team_abbrev = row["team_abbreviation"] if pd.notna(row["team_abbreviation"]) else ""
        logo_html = f'<img class="team-rank-logo" src="{get_team_logo(team_abbrev)}" />' if team_abbrev else ""

        st.markdown(
            f"""
            <div class="team-rank-row">
                <div class="team-rank-left">
                    <div class="leader-rank">#{rank}</div>
                    {logo_html}
                    <div class="team-rank-name-wrap">
                        <div class="team-rank-name">{row['team_name']}</div>
                        <div class="team-rank-sub">{team_abbrev} • {int(row['games_played'])} games</div>
                    </div>
                </div>
                <div class="team-rank-right">
                    <div class="team-rank-stat">
                        <div class="team-rank-stat-value">{int(row['wins'])}</div>
                        <div class="team-rank-stat-label">Wins</div>
                    </div>
                    <div class="team-rank-stat">
                        <div class="team-rank-stat-value">{int(row['losses'])}</div>
                        <div class="team-rank-stat-label">Losses</div>
                    </div>
                    <div class="team-rank-stat">
                        <div class="team-rank-stat-value">{safe_metric(row['avg_points_for'], 1)}</div>
                        <div class="team-rank-stat-label">PPG</div>
                    </div>
                    <div class="team-rank-stat">
                        <div class="team-rank-stat-value">{safe_metric(row['avg_points_against'], 1)}</div>
                        <div class="team-rank-stat-label">Opp PPG</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


@st.cache_data(ttl=300)
def load_last_updated():
    q = """
    SELECT MAX(last_updated) AS last_updated
    FROM games
    """
    return pd.read_sql(text(q), engine)


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
    SELECT DISTINCT
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
    return pd.read_sql(text(q), engine, params={"player_id": player_id}).drop_duplicates()


@st.cache_data(ttl=3600)
def load_efficiency_leaders():
    q = """
    SELECT
        p.player_id,
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
        p.player_id,
        p.full_name,
        t.team_abbreviation,
        ROUND(AVG(pg.points)::numeric, 1) AS ppg
    FROM player_game_stats pg
    JOIN players p ON pg.player_id = p.player_id
    LEFT JOIN teams t ON p.team_id = t.team_id
    GROUP BY p.player_id, p.full_name, t.team_abbreviation
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
def load_team_summary_with_abbrev():
    q = """
    SELECT t.team_id,
           t.team_name,
           t.team_abbreviation,
           v.games_played,
           v.avg_points_for,
           v.avg_points_against,
           v.wins,
           v.losses
    FROM v_team_summary v
    JOIN teams t ON v.team_name = t.team_name
    ORDER BY t.team_name
    """
    return pd.read_sql(text(q), engine)


@st.cache_data(ttl=3600)
def load_team_games(team_id):
    q = """
    SELECT DISTINCT
        g.game_date,
        g.matchup,
        g.team_score,
        g.opponent_score,
        g.result
    FROM games g
    WHERE g.team_id = :team_id
    ORDER BY g.game_date
    """
    return pd.read_sql(text(q), engine, params={"team_id": team_id}).drop_duplicates()


@st.cache_data(ttl=3600)
def load_team_player_leaders(team_id):
    q = """
    SELECT
        p.player_id,
        p.full_name,
        ROUND(AVG(pg.points)::numeric, 1) AS ppg,
        ROUND(AVG(pg.rebounds)::numeric, 1) AS rpg,
        ROUND(AVG(pg.assists)::numeric, 1) AS apg
    FROM player_game_stats pg
    JOIN players p ON pg.player_id = p.player_id
    WHERE p.team_id = :team_id
    GROUP BY p.player_id, p.full_name
    ORDER BY ppg DESC
    LIMIT 10
    """
    return pd.read_sql(text(q), engine, params={"team_id": team_id})


@st.cache_data(ttl=3600)
def load_team_recent_players(team_id):
    q = """
    SELECT
        p.player_id,
        p.full_name,
        ROUND(AVG(pg.points)::numeric, 1) AS ppg,
        ROUND(AVG(pg.rebounds)::numeric, 1) AS rpg,
        ROUND(AVG(pg.assists)::numeric, 1) AS apg
    FROM player_game_stats pg
    JOIN players p ON pg.player_id = p.player_id
    WHERE p.team_id = :team_id
    GROUP BY p.player_id, p.full_name
    ORDER BY ppg DESC
    LIMIT 5
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

last_updated_df = load_last_updated()
if not last_updated_df.empty and pd.notna(last_updated_df.loc[0, "last_updated"]):
    st.caption(f"Last data refresh: {last_updated_df.loc[0, 'last_updated']}")

view = st.radio(
    "View",
    ["Player Analytics", "Team Analytics", "League Leaders", "Matchup Comparison"],
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
    selected_row = players.loc[players["full_name"] == selected_name].iloc[0]

    player_id = int(selected_row["player_id"])
    team_abbrev = selected_row["team_abbreviation"] if pd.notna(selected_row["team_abbreviation"]) else ""

    stats = load_player_stats(player_id)
    prediction = load_player_prediction(player_id)

    if stats.empty:
        st.warning("No game log data is available for this player.")
        st.stop()

    player_window = st.radio(
        "Player sample",
        ["Season", "Last 10", "Last 5"],
        horizontal=True,
        key="player_window",
    )

    stats_view = filter_by_window(stats, player_window)

    header_col1, header_col2, header_col3 = st.columns([1.1, 1.1, 5])

    with header_col1:
        st.image(get_player_headshot(player_id), width=150)

    with header_col2:
        if team_abbrev:
            st.image(get_team_logo(team_abbrev), width=90)

    with header_col3:
        st.markdown(
            f'<div class="section-title" style="margin-bottom:0.2rem;">{selected_name}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="hero-subtitle-secondary" style="text-align:left;">{team_abbrev} • {player_window} Analytics Profile</div>',
            unsafe_allow_html=True,
        )

    latest = stats_view.iloc[-1]

    fg_pct = (stats_view["fg_made"].sum() / stats_view["fg_attempts"].sum() * 100) if stats_view["fg_attempts"].sum() > 0 else 0
    three_pct = (stats_view["three_made"].sum() / stats_view["three_attempts"].sum() * 100) if stats_view["three_attempts"].sum() > 0 else 0
    ft_pct = (stats_view["ft_made"].sum() / stats_view["ft_attempts"].sum() * 100) if stats_view["ft_attempts"].sum() > 0 else 0

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

        plot_df = stats_view.copy()
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

    st.markdown('<div class="section-title">Sample Averages & Shooting</div>', unsafe_allow_html=True)
    row1 = st.columns(6)
    metrics = [
        (row1[0], stats_view["points"].mean(), "PPG"),
        (row1[1], stats_view["rebounds"].mean(), "RPG"),
        (row1[2], stats_view["assists"].mean(), "APG"),
        (row1[3], stats_view["steals"].mean(), "SPG"),
        (row1[4], stats_view["blocks"].mean(), "BPG"),
        (row1[5], stats_view["turnovers"].mean(), "TO"),
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

        st.markdown('<div class="section-title">Prop Bet Insights</div>', unsafe_allow_html=True)

        pred_points = float(pred["pred_points"])
        pred_rebounds = float(pred["pred_rebounds"])
        pred_assists = float(pred["pred_assists"])
        pred_pra = pred_points + pred_rebounds + pred_assists

        line_col1, line_col2, line_col3, line_col4 = st.columns(4)
        with line_col1:
            points_line = st.number_input("Points Line", value=22.5, step=0.5, key="points_line")
        with line_col2:
            rebounds_line = st.number_input("Rebounds Line", value=8.5, step=0.5, key="rebounds_line")
        with line_col3:
            assists_line = st.number_input("Assists Line", value=5.5, step=0.5, key="assists_line")
        with line_col4:
            pra_line = st.number_input("PRA Line", value=36.5, step=0.5, key="pra_line")

        props = [
            ("Points", pred_points, points_line),
            ("Rebounds", pred_rebounds, rebounds_line),
            ("Assists", pred_assists, assists_line),
            ("PRA", pred_pra, pra_line),
        ]

        prop_cols = st.columns(4)

        for col, (name, projection, line) in zip(prop_cols, props):
            edge = projection - line
            call = prop_call(edge)

            with col:
                st.markdown(
                    f"""
                    <div class="projection-card">
                        <div class="subtle-label">{name} Insight</div>
                        <div class="metric-value">{call}</div>
                        <div class="footer-note">
                            Projection: {projection:.1f}<br>
                            Line: {line:.1f}<br>
                            Edge: {edge:+.1f}
                        </div>
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
    selected_team_row = teams.loc[teams["team_name"] == selected_team_name].iloc[0]

    team_id = int(selected_team_row["team_id"])
    team_abbrev = selected_team_row["team_abbreviation"] if pd.notna(selected_team_row["team_abbreviation"]) else ""

    team_games = load_team_games(team_id)
    team_leaders = load_team_player_leaders(team_id)

    if team_games.empty:
        st.warning("No game data found for this team.")
        st.stop()

    team_window = st.radio(
        "Team sample",
        ["Season", "Last 10", "Last 5"],
        horizontal=True,
        key="team_window",
    )

    team_games_view = filter_by_window(team_games, team_window)

    team_header_col1, team_header_col2 = st.columns([1.1, 6])

    with team_header_col1:
        if team_abbrev:
            st.image(get_team_logo(team_abbrev), width=110)

    with team_header_col2:
        st.markdown(
            f'<div class="section-title" style="margin-bottom:0.2rem;">{selected_team_name}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="hero-subtitle-secondary" style="text-align:left;">{team_abbrev} • {team_window} Team Analytics</div>',
            unsafe_allow_html=True,
        )

    wins = int((team_games["result"] == "W").sum())
    losses = int((team_games["result"] == "L").sum())
    sample_avg_for = team_games_view["team_score"].mean()
    sample_avg_against = team_games_view["opponent_score"].mean()

    st.markdown('<div class="section-title">Team Snapshot</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    cards = [
        (cols[0], wins, "Season Wins"),
        (cols[1], losses, "Season Losses"),
        (cols[2], sample_avg_for, f"{team_window} Avg For"),
        (cols[3], sample_avg_against, f"{team_window} Avg Against"),
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

        team_plot = team_games_view.copy()
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
        render_team_player_cards(team_leaders, "Top Team Players")
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

elif view == "League Leaders":
    leaders = load_efficiency_leaders()
    scoring = load_scoring_leaders()
    team_summary = load_team_summary()
    teams = load_teams()

    st.markdown('<div class="section-title">League Leaders</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        render_leaderboard(leaders, "efficiency_score", "Efficiency Leaders")
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        render_leaderboard(scoring, "ppg", "Scoring Leaders")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    render_team_rankings(team_summary, teams, "Team Rankings")
    st.markdown("</div>", unsafe_allow_html=True)

elif view == "Matchup Comparison":
    teams = load_teams()
    team_summary_df = load_team_summary_with_abbrev()

    if teams.empty or team_summary_df.empty:
        st.error("No team data found.")
        st.stop()

    team_display = teams["team_name"] + " • " + teams["team_abbreviation"].fillna("")

    col_a, col_b = st.columns(2)
    with col_a:
        selected_team_a = st.selectbox("Select Team A", team_display.tolist(), key="matchup_team_a")
    with col_b:
        selected_team_b = st.selectbox("Select Team B", team_display.tolist(), index=1, key="matchup_team_b")

    team_a_name = selected_team_a.split(" • ")[0]
    team_b_name = selected_team_b.split(" • ")[0]

    row_a = teams.loc[teams["team_name"] == team_a_name].iloc[0]
    row_b = teams.loc[teams["team_name"] == team_b_name].iloc[0]

    team_a_id = int(row_a["team_id"])
    team_b_id = int(row_b["team_id"])
    team_a_abbrev = row_a["team_abbreviation"]
    team_b_abbrev = row_b["team_abbreviation"]

    summary_a = team_summary_df.loc[team_summary_df["team_id"] == team_a_id].iloc[0]
    summary_b = team_summary_df.loc[team_summary_df["team_id"] == team_b_id].iloc[0]

    games_a = load_team_games(team_a_id)
    games_b = load_team_games(team_b_id)

    a_last10_w, a_last10_l = get_recent_record(games_a, 10)
    b_last10_w, b_last10_l = get_recent_record(games_b, 10)

    a_net = float(summary_a["avg_points_for"] - summary_a["avg_points_against"])
    b_net = float(summary_b["avg_points_for"] - summary_b["avg_points_against"])

    proj_a = projected_team_score(summary_a["avg_points_for"], summary_b["avg_points_against"])
    proj_b = projected_team_score(summary_b["avg_points_for"], summary_a["avg_points_against"])

    a_win_prob = win_probability_from_net(a_net - b_net)
    b_win_prob = 1 - a_win_prob

    header1, header2, header3 = st.columns([2, 1, 2])

    with header1:
        st.image(get_team_logo(team_a_abbrev), width=110)
        st.markdown(f'<div class="section-title">{team_a_name}</div>', unsafe_allow_html=True)

    with header2:
        st.markdown('<div class="section-title" style="text-align:center; margin-top:2rem;">VS</div>', unsafe_allow_html=True)

    with header3:
        st.image(get_team_logo(team_b_abbrev), width=110)
        st.markdown(f'<div class="section-title">{team_b_name}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">Projected Matchup</div>', unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    matchup_cards = [
        (m1, proj_a, f"{team_a_abbrev} Projected Score"),
        (m2, proj_b, f"{team_b_abbrev} Projected Score"),
        (m3, a_win_prob * 100, f"{team_a_abbrev} Win %"),
        (m4, b_win_prob * 100, f"{team_b_abbrev} Win %"),
    ]

    for col, value, label in matchup_cards:
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

    st.markdown('<div class="section-title">Team Comparison</div>', unsafe_allow_html=True)

    left, right = st.columns(2)

    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown(f"### {team_a_name}")
        st.write(f"Record: {int(summary_a['wins'])}-{int(summary_a['losses'])}")
        st.write(f"Last 10: {a_last10_w}-{a_last10_l}")
        st.write(f"Avg Points For: {safe_metric(summary_a['avg_points_for'], 1)}")
        st.write(f"Avg Points Against: {safe_metric(summary_a['avg_points_against'], 1)}")
        st.write(f"Net Rating Proxy: {safe_metric(a_net, 1)}")
        render_team_player_cards(load_team_recent_players(team_a_id), f"{team_a_name} Top Players")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown(f"### {team_b_name}")
        st.write(f"Record: {int(summary_b['wins'])}-{int(summary_b['losses'])}")
        st.write(f"Last 10: {b_last10_w}-{b_last10_l}")
        st.write(f"Avg Points For: {safe_metric(summary_b['avg_points_for'], 1)}")
        st.write(f"Avg Points Against: {safe_metric(summary_b['avg_points_against'], 1)}")
        st.write(f"Net Rating Proxy: {safe_metric(b_net, 1)}")
        render_team_player_cards(load_team_recent_players(team_b_id), f"{team_b_name} Top Players")
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    '<div class="footer-note">StatLine • The Pulse of the Game</div>',
    unsafe_allow_html=True,
)