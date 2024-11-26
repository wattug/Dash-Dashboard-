import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import json
import plotly.express as px
import plotly.colors as colors
import plotly.graph_objs as go

# Load and process GeoJSON data
with open("data.geojson") as f:
    data_complete_geojson = json.load(f)

# Extract data into DataFrame
points = []
for feature in data_complete_geojson["features"]:
    coords = feature["geometry"]["coordinates"]
    props = feature["properties"]
    points.append({
        "lon": coords[0],
        "lat": coords[1],
        "NAMOBJ": props.get("NAMOBJ", "Unknown"),
        "Status": props.get("Status", 0),
        "Update_1": props.get("Update_1"),
        "Update_2": props.get("Update_2"),
        "Update_3": props.get("Update_3"),
        "Update_4": props.get("Update_4"),
        "Update_5": props.get("Update_5")
    })

# Convert to DataFrame and parse date columns
df_points = pd.DataFrame(points)
for i in range(1, 6):
    df_points[f"Update_{i}"] = pd.to_datetime(df_points[f"Update_{i}"], format='%d-%m-%Y', errors='coerce')

# Set up colors for Status
status_range = df_points["Status"].max() - df_points["Status"].min()
viridis_colors = colors.sample_colorscale("Viridis", [i / status_range for i in range(status_range + 1)], colortype="rgb")
status_color_map = {status: viridis_colors[status] for status in range(df_points["Status"].min(), df_points["Status"].max() + 1)}
custom_color_map = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA']

# Define the navigation bar with links to different pages
navbar = dbc.Navbar(
    dbc.Container([
        dbc.NavbarBrand("Exploration Stages Dashboard", className="ms-2 text-white"),
        dbc.Nav(
            [
                dbc.NavItem(dcc.Link("Summary Page", href="/summary", className="nav-link text-white")),
                *[
                    dbc.NavItem(dcc.Link(f"Stage {i} Map", href=f"/stage-{i}", className="nav-link text-white"))
                    for i in range(1, 6)
                ],
            ],
            className="ms-auto",
            navbar=True
        ),
    ]),
    color="dark",
    dark=True,
    className="mb-4"
)

# Initialize Dash app with Bootstrap theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY], suppress_callback_exceptions=True)
server = app.server

# Summary page layout
summary_layout = dbc.Container([
    # Filter checklist
    # Filter checklist
    dbc.Row([
        dbc.Col(
            dbc.Card([
                dbc.CardHeader(
                    "Filter Options", 
                    className="bg-primary text-white text-center"
                ),
                dbc.CardBody([
                    html.Div(
                        dcc.Checklist(
                            id="namobj-checklist", 
                            options=[{"label": nam, "value": nam} for nam in df_points["NAMOBJ"].unique()],
                            value=df_points["NAMOBJ"].unique().tolist(), 
                            inline=False,  # Align items vertically
                            style={"color": "white"}
                        ),
                        style={
                            "height": "120px",  # Make it scrollable if there are many options
                            "overflowY": "scroll",
                            "padding": "10px",  # Add padding around checklist items
                            "backgroundColor": "#2c2f33",  # Match background color for consistency
                            "borderRadius": "5px"
                        }
                    )
                ])
            ]),
            width=6
        )
    ], className="mb-4"),

    # Map overview
    dbc.Row([dbc.Col(dbc.Card([dbc.CardHeader("Map Overview"), dbc.CardBody(dcc.Graph(id="map", style={"height": "500px"}))]), width=12)], className="mb-4"),
    
    # Status count bar chart
    dbc.Row([dbc.Col(dbc.Card([dbc.CardHeader("Status Count per NAMOBJ"), dbc.CardBody(dcc.Graph(id="status-bar-plot"))]), width=12)], className="mb-4"),
    
    # Progress stages
    dbc.Row([dbc.Col(dbc.Card([dbc.CardHeader("Progress Stages"), dbc.CardBody(html.Div(id="progress-plots-container"))]), width=12)], className="mb-4")
], fluid=True)

# Layout for each stage page
def create_stage_layout(stage):
    return dbc.Container([
        dbc.Row([dbc.Col(html.Label(f"Stage {stage} Completion Date")), dbc.Col(dcc.Slider(id=f"date-slider-{stage}", min=0, max=1, value=0, marks={}, tooltip={"placement": "bottom", "always_visible": True}), width=10)], className="my-4"),
        dbc.Row([dbc.Col(dcc.Graph(id=f"progress-map-{stage}", style={"height": "600px"}), width=8), dbc.Col(dcc.Graph(id=f"namobj-bar-{stage}", style={"height": "600px"}), width=4)], className="my-4")
    ], fluid=True)

# Main layout with navigation links
app.layout = dbc.Container([
    navbar,
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content")
])

# Update content based on URL
@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def display_page(pathname):
    if pathname in ["/", "/summary"]:
        return summary_layout
    elif pathname.startswith("/stage-"):
        try:
            stage = int(pathname.split("-")[1])
            return create_stage_layout(stage)
        except (IndexError, ValueError):
            return html.H1("Invalid Page")
    return html.H1("404 - Page Not Found")

# Summary page callback
@app.callback(
    [Output("map", "figure"), Output("status-bar-plot", "figure"), Output("progress-plots-container", "children")],
    [Input("namobj-checklist", "value")]
)
def update_dashboard(selected_namobj):
    filtered_df = df_points[df_points["NAMOBJ"].isin(selected_namobj)].copy()
    center_lat, center_lon = (-7.9, 110.4) if filtered_df.empty else (filtered_df["lat"].mean(), filtered_df["lon"].mean())

    map_fig = go.Figure(data=[
        go.Scattermapbox(
            lat=filtered_df["lat"], lon=filtered_df["lon"], mode="markers",
            marker={"size": 8, "color": filtered_df["Status"].map(status_color_map), "opacity": 0.6},
            text=filtered_df["NAMOBJ"] + " - Status: " + filtered_df["Status"].astype(str),
            hoverinfo="text"
        )
    ], layout=go.Layout(
        mapbox={"style": "open-street-map", "center": {"lat": center_lat, "lon": center_lon}, "zoom": 12},
        margin={"r": 0, "t": 0, "l": 0, "b": 0}, paper_bgcolor="#2c2f33", font={"color": "white"}
    ))

    bar_df = filtered_df.groupby(["NAMOBJ", "Status"]).size().reset_index(name="Count")
    bar_fig = px.bar(bar_df, x="NAMOBJ", y="Count", color="Status", color_continuous_scale="Viridis", labels={"Count": "Status Count", "NAMOBJ": "NAMOBJ"}, title="Status Count per NAMOBJ")
    bar_fig.update_layout(paper_bgcolor="#2c2f33", plot_bgcolor="#2c2f33", font=dict(color="white"))

    progress_plots = []
    for stage in range(1, 6):
        stage_df = filtered_df[filtered_df[f"Update_{stage}"].notna()]
        if not stage_df.empty:
            grouped_df = stage_df.groupby(["NAMOBJ", f"Update_{stage}"]).size().reset_index(name="count").sort_values(by=f"Update_{stage}")
            fig = px.bar(grouped_df, x=f"Update_{stage}", y="count", color="NAMOBJ", title=f"Progress Stage {stage} Completion Dates", labels={f"Update_{stage}": "Date", "count": "Number of Points"}, color_discrete_sequence=custom_color_map)
            fig.update_layout(xaxis=dict(type='category'), paper_bgcolor="#2c2f33", plot_bgcolor="#2c2f33", font=dict(color="white"))
            progress_plots.append(dcc.Graph(figure=fig))

    return map_fig, bar_fig, progress_plots

# Callback for each stage map and bar chart

for stage in range(1, 6):
    @app.callback(
        [Output(f"date-slider-{stage}", "min"), Output(f"date-slider-{stage}", "max"),
         Output(f"date-slider-{stage}", "marks"), Output(f"progress-map-{stage}", "figure"),
         Output(f"namobj-bar-{stage}", "figure")],
        [Input(f"date-slider-{stage}", "value")]
    )
    def update_map_and_bar(slider_value, stage=stage):
        stage_col = f"Update_{stage}"
        stage_df = df_points[df_points[stage_col].notna()]

        if stage_df.empty:
            return 0, 1, {}, {}, {}

        # Get unique dates and create slider range
        unique_dates = sorted(stage_df[stage_col].dropna().unique())
        date_marks = {i: date.strftime('%d-%m-%Y') for i, date in enumerate(unique_dates)}
        slider_index = int(slider_value)
        date_selected = unique_dates[slider_index] if slider_index < len(unique_dates) else unique_dates[-1]

        # Filter points up to selected date
        filtered_df = stage_df[stage_df[stage_col] <= date_selected]
        
        # Generate color map for NAMOBJ values
        unique_namobjs = filtered_df["NAMOBJ"].unique()
        color_map = {namobj: color for namobj, color in zip(unique_namobjs, px.colors.qualitative.Plotly)}

        # Create map traces
        map_traces = [
            go.Scattermapbox(
                lat=filtered_df[filtered_df["NAMOBJ"] == namobj]["lat"],
                lon=filtered_df[filtered_df["NAMOBJ"] == namobj]["lon"],
                mode="markers",
                marker={"size": 8, "color": color_map[namobj], "opacity": 0.6},
                name=namobj,
                showlegend=True,
                hoverinfo="text",
                text=filtered_df[filtered_df["NAMOBJ"] == namobj]["NAMOBJ"] + " - Status: " + filtered_df["Status"].astype(str)
            ) for namobj in unique_namobjs
        ]

        map_layout = go.Layout(
            mapbox={
                "style": "open-street-map",
                "center": {"lat": -7.9, "lon": 110.4},
                "zoom": 12
            },
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            paper_bgcolor="#2c2f33",
            font={"color": "white"},
            legend={"title": "NAMOBJ"}
        )
        map_fig = go.Figure(data=map_traces, layout=map_layout)

        # Create bar chart for NAMOBJ counts
        bar_df = filtered_df["NAMOBJ"].value_counts().reset_index()
        bar_df.columns = ["NAMOBJ", "Count"]

        bar_fig = px.bar(
            bar_df, x="NAMOBJ", y="Count",
            color="NAMOBJ",
            color_discrete_map=color_map,
            title="Number of Points per NAMOBJ",
            labels={"NAMOBJ": "NAMOBJ", "Count": "Point Count"}
        )
        bar_fig.update_layout(
            paper_bgcolor="#2c2f33",
            plot_bgcolor="#2c2f33",
            font=dict(color="white")
        )

        return 0, len(unique_dates) - 1, date_marks, map_fig, bar_fig

if __name__ == "__main__":
    app.run_server(debug=True, port=8051)
