"""CSS for the Lisbon map presentation."""

MAP_LAYOUT_CSS = """
<style>
.st-key-lisbon_map_frame {
    height: 520px;
    box-sizing: border-box;
    overflow: hidden;
    border: 1px solid #d3dbe8;
    border-radius: 16px;
    box-shadow: 0 4px 16px rgba(14, 27, 51, 0.10);
}
.st-key-lisbon_map_frame [data-testid="stDeckGlJsonChart"] {
    border-radius: 15px;
    overflow: hidden;
}
.map-legend-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-top: 10px;
    color: #667085;
    font-size: 0.82rem;
}
.map-legend {
    display: flex;
    align-items: center;
    gap: 14px;
    white-space: nowrap;
}
.map-legend-item {
    display: inline-flex;
    align-items: center;
    gap: 5px;
}
.map-legend-dot {
    width: 9px;
    height: 9px;
    display: inline-block;
    border-radius: 50%;
}
.map-legend-no-reviews {
    background: transparent;
    border: 2px solid #d9960f;
}
.map-count {
    white-space: nowrap;
    text-align: right;
}
</style>
"""

MAP_LEGEND_HTML = """
<div class="map-legend-row">
  <div class="map-legend">
    <span class="map-legend-item"><i class="map-legend-dot" style="background:#2ea043"></i>4+</span>
    <span class="map-legend-item"><i class="map-legend-dot" style="background:#f5a623"></i>3–4</span>
    <span class="map-legend-item"><i class="map-legend-dot" style="background:#dc3545"></i>Under 3</span>
    <span class="map-legend-item"><i class="map-legend-dot map-legend-no-reviews"></i>No reviews</span>
  </div>
  <span class="map-count">Showing {shown} of {total} bars</span>
</div>
"""

VENUE_WEATHER_CSS = """
<style>
.st-key-venue_weather_box {
    background: #f6f8fb;
    border: 1px solid #e6ebf2;
    border-radius: 10px;
    padding: 0.4rem 0.7rem;
    margin: 0.4rem 0 0.6rem;
}
.st-key-venue_weather_box [data-testid="stCaptionContainer"] {
    margin-bottom: 0;
}
</style>
"""


THEME_CSS = """
<style>
/* Red banner across the top with a thin gold and dark line under it, like bottle neck foil. */
.stApp {
  background:
    linear-gradient(to bottom,
      #B80F24 0, #D0142C 210px,
      #D4A646 210px, #D4A646 215px,
      #2A1405 215px, #2A1405 218px,
      #FBF3E4 218px) no-repeat;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stHeader"] * { color: #FFF4DC !important; }
/* Our own beer illustration on the right side of the banner. */
[data-testid="stMain"]::before {
  content: ""; position: absolute; top: 46px; right: 4%; width: 380px; height: 160px; z-index: 0;
  background: url("app/static/beers.svg") no-repeat right top / contain; pointer-events: none;
}
@media (max-width: 900px) { [data-testid="stMain"]::before { display: none; } }
h1, h1 span { color: #FFFFFF !important; text-shadow: 0 2px 0 rgba(90, 10, 20, 0.35); }
h1 { margin-bottom: 1.6rem !important; }
h2, h3 { color: #3A1E08 !important; }
h2::after, h3::after {
  content: ""; display: block; width: 56px; height: 4px; margin-top: 6px;
  background: linear-gradient(90deg, #D4A646, #B87B1E); border-radius: 2px;
}
[data-testid="stSidebar"] { border-right: 1px solid #E3C98F; }
/* Cards: cream with a gold edge. */
[data-testid="stVerticalBlockBorderWrapper"] {
  background: #FFFBF2; border-color: #E3C98F !important;
  box-shadow: 0 4px 14px rgba(90, 42, 6, 0.10);
}
.stButton button[kind="primary"], .stFormSubmitButton button { box-shadow: 0 2px 0 #7E0A19; font-weight: 600; }
.stButton button[kind="secondary"]:hover { border-color: #D4A646; color: #8A4B0C; }
</style>
"""
