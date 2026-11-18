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
