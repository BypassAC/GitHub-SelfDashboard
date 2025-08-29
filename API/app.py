import dash
from dash import html, dcc, Input, Output, State
import plotly.express as px
import pandas as pd
import requests
import os
from dotenv import load_dotenv
from collections import Counter
from datetime import datetime
import time


load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


USER_COLORS = ["#00FF7F", "#1E90FF", "#FF6347"]

app = dash.Dash(__name__, title="GitHub SelfDashboard")

CACHE = {}
CACHE_TTL = 300


def get_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

def fetch_user_data(username):
    now = time.time()
    if username in CACHE and now - CACHE[username]["timestamp"] < CACHE_TTL:
        return CACHE[username]
    headers = get_headers()
    try:
        user_resp = requests.get(f"https://api.github.com/users/{username}", headers=headers, timeout=10)
        if user_resp.status_code != 200:
            return None
        user_data = user_resp.json()
    except:
        return None
    try:
        repos_resp = requests.get(f"https://api.github.com/users/{username}/repos?per_page=100", headers=headers, timeout=10)
        repos = repos_resp.json() if repos_resp.status_code == 200 else []
    except:
        repos = []
    try:
        events_resp = requests.get(f"https://api.github.com/users/{username}/events/public?per_page=100", headers=headers, timeout=10)
        events = events_resp.json() if events_resp.status_code == 200 else []
    except:
        events = []
    CACHE[username] = {"timestamp": now, "user": user_data, "repos": repos, "events": events}
    return CACHE[username]

def fetch_commit_activity(username, repos):
    headers = get_headers()
    all_commits = []
    for repo in repos:
        repo_name = repo["name"]
        commits_url = f"https://api.github.com/repos/{username}/{repo_name}/commits?per_page=100"
        try:
            resp = requests.get(commits_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                commits = resp.json()
                for commit in commits:
                    try:
                        date_str = commit["commit"]["author"]["date"]
                        date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        all_commits.append(date)
                    except:
                        continue
        except:
            continue
    if all_commits:
        df = pd.DataFrame(all_commits, columns=["Дата"])
        return df.groupby(df["Дата"].dt.date).size().reset_index(name="Коммиты")
    else:
        return pd.DataFrame(columns=["Дата","Коммиты"])

def get_repo_languages(repos):
    headers = get_headers()
    langs = []
    for repo in repos:
        url = repo.get("languages_url")
        if url:
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    langs += list(resp.json().keys())
            except:
                continue
    return Counter(langs)


app.layout = html.Div(style={"backgroundColor": "#0D1117", "color": "#c9d1d9", "font-family": "Consolas, monospace", "padding":"20px"}, children=[

    # Заголовок
    html.Div([
        html.H1("GitHub SelfDashboard", style={"textAlign":"center", "color":"#58a6ff","margin-bottom":"10px"}),
        html.P("Сравнение активности до 3 пользователей GitHub", style={"textAlign":"center", "fontSize":"18px","color":"#8b949e"})
    ], className="header"),

    html.Div([
        dcc.Input(id="username-input", type="text", placeholder="Введите до 3 usernames через запятую...", style={"width":"70%","padding":"10px","border-radius":"5px","border":"1px solid #30363d","backgroundColor":"#161b22","color":"white"}),
        html.Button("Обновить", id="update-btn", style={"margin-left":"10px","padding":"10px 20px","border-radius":"5px","border":"none","backgroundColor":"#238636","color":"white","cursor":"pointer"})
    ], style={"textAlign":"center","margin-bottom":"30px"}),

    dcc.Interval(id="interval-component", interval=60*1000, n_intervals=0),

    html.Div(id="user-cards", style={"display":"flex","justifyContent":"space-around","margin-bottom":"30px","flex-wrap":"wrap"}),

    html.Div(id="commit-charts", style={"display":"flex","justifyContent":"space-around","flex-wrap":"wrap","margin-bottom":"30px"}),

    html.Div(id="languages-charts", style={"display":"flex","justifyContent":"space-around","flex-wrap":"wrap","margin-bottom":"30px"}),

    html.Div(id="events-charts", style={"display":"flex","justifyContent":"space-around","flex-wrap":"wrap","margin-bottom":"30px"})
])


@app.callback(
    Output("user-cards", "children"),
    Output("commit-charts", "children"),
    Output("languages-charts", "children"),
    Output("events-charts", "children"),
    Input("update-btn", "n_clicks"),
    Input("interval-component", "n_intervals"),
    State("username-input", "value")
)
def update_dashboard(n_clicks, n_intervals, username_input):
    if not username_input:
        return [],[],[],[]
    usernames = [u.strip() for u in username_input.split(",")][:3]
    cards=[]
    commit_graphs=[]
    lang_graphs=[]
    event_graphs=[]
    for idx, username in enumerate(usernames):
        data = fetch_user_data(username)
        color = USER_COLORS[idx]
        card_style = {"backgroundColor":"#161b22","padding":"15px","border-radius":"10px","margin":"5px","width":"280px","box-shadow":"0 0 10px rgba(0,0,0,0.5)"}
        if not data:
            cards.append(html.Div([html.H3(username, style={"color":color}),html.P("Ошибка или лимит API")], style=card_style))
            continue
        user_data = data["user"]
        repos = data["repos"]
        events = data["events"]
        # Карточки
        cards.append(html.Div([
            html.H3(username, style={"color":color}),
            html.P(f"Репозитории: {user_data.get('public_repos',0)}"),
            html.P(f"Подписчики / Подписки: {user_data.get('followers',0)} / {user_data.get('following',0)}"),
            html.P(f"Публичные события: {len(events)}")
        ], style=card_style))
        # Коммиты
        commits_df = fetch_commit_activity(username, repos)
        if not commits_df.empty:
            fig_commits = px.line(commits_df, x="Дата", y="Коммиты")
            fig_commits.update_traces(line_color=color)
        else:
            fig_commits = px.line(title=f"{username} — Активность коммитов")
        fig_commits.update_layout(paper_bgcolor="#0D1117", plot_bgcolor="#0D1117", font_color="#c9d1d9", margin=dict(t=40,b=20,l=20,r=20))
        commit_graphs.append(dcc.Graph(figure=fig_commits, style={"width":"400px","height":"300px","margin":"10px"}))
        # Языки
        langs_counter = get_repo_languages(repos)
        if langs_counter:
            df_langs = pd.DataFrame(langs_counter.items(), columns=["Язык","Количество"])
            fig_langs = px.bar(df_langs, x="Язык", y="Количество")
            fig_langs.update_traces(marker_color=color)
        else:
            fig_langs = px.bar(title=f"{username} — Языки")
        fig_langs.update_layout(paper_bgcolor="#0D1117", plot_bgcolor="#0D1117", font_color="#c9d1d9", margin=dict(t=40,b=20,l=20,r=20))
        lang_graphs.append(dcc.Graph(figure=fig_langs, style={"width":"400px","height":"300px","margin":"10px"}))
        # События
        if events:
            event_types = [e.get("type","Unknown") for e in events]
            counter = Counter(event_types)
            df_events = pd.DataFrame(counter.items(), columns=["Событие","Количество"])
            fig_events = px.pie(df_events, names="Событие", values="Количество")
            fig_events.update_traces(marker_colors=[color]*len(df_events))
        else:
            fig_events = px.pie(title=f"{username} — События")
        fig_events.update_layout(paper_bgcolor="#0D1117", plot_bgcolor="#0D1117", font_color="#c9d1d9", margin=dict(t=40,b=20,l=20,r=20))
        event_graphs.append(dcc.Graph(figure=fig_events, style={"width":"400px","height":"300px","margin":"10px"}))
    return cards, commit_graphs, lang_graphs, event_graphs

if __name__=="__main__":
    app.run(debug=True)
