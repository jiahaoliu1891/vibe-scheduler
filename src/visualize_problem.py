"""
Flask + D3 visualization for doctor availability test cases.

Usage:
    python src/visualize_problem.py --input sample_case.json --port 9000
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from flask import Flask, Response, jsonify, render_template_string


def load_case(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def create_app(test_case: Dict[str, Any]) -> Flask:
    app = Flask(__name__)

    @app.get("/data")
    def data() -> Response:
        return jsonify(test_case)

    @app.get("/")
    def index() -> str:
        return render_template_string(
            HTML_TEMPLATE,
            meta=test_case.get("meta", {}),
        )

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize scheduling test case with D3.")
    parser.add_argument("--input", "-i", type=Path, required=True, help="Path to test case JSON file.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=9000, help="Port to bind. Default: 9000")
    parser.add_argument("--debug", action="store_true", help="Run Flask debug mode.")
    return parser.parse_args()


HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Doctor Availability</title>
  <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 0; background: #f7f7f7; }
    header { padding: 12px 16px; background: #0f172a; color: #e2e8f0; }
    main { padding: 16px; }
    #controls { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
    select, button { padding: 6px 10px; font-size: 14px; }
    #meta { color: #475569; font-size: 14px; }
    #chart { border: 1px solid #e2e8f0; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .axis line, .axis path { stroke: #cbd5e1; }
    .grid line { stroke: #e2e8f0; }
    .slot { stroke: #0f172a; stroke-width: 0.5px; fill-opacity: 0.7; }
    .legend { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; font-size: 12px; color: #334155; }
    .legend-item { display: flex; align-items: center; gap: 4px; }
    .legend-swatch { width: 12px; height: 12px; border: 1px solid #cbd5e1; }
    .tooltip { position: absolute; pointer-events: none; background: #0f172a; color: #e2e8f0;
               padding: 6px 8px; border-radius: 4px; font-size: 12px; opacity: 0; }
  </style>
</head>
<body>
  <header>
    <h2 style="margin:0;">Doctor Availability</h2>
    <div id="meta">
      Seed: {{ meta.get("seed", "n/a") }} |
      Generated at: {{ meta.get("generated_at", "n/a") }} |
      Time zone: {{ meta.get("time_zone", "n/a") }}
    </div>
  </header>
  <main>
    <div id="controls">
      <label for="doctorSelect">Doctor:</label>
      <select id="doctorSelect"></select>
      <span id="summary"></span>
    </div>
    <div id="chart"></div>
    <div class="legend" id="legend"></div>
  </main>
  <div class="tooltip" id="tooltip"></div>

  <script>
    const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    const chartWidth = 1100;
    const chartHeight = 600;
    const margin = { top: 30, right: 20, bottom: 40, left: 70 };
    const dayPadding = 6;

    const tooltip = d3.select("#tooltip");
    const chart = d3.select("#chart")
      .append("svg")
      .attr("width", chartWidth)
      .attr("height", chartHeight);

    const plotArea = chart.append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const innerWidth = chartWidth - margin.left - margin.right;
    const innerHeight = chartHeight - margin.top - margin.bottom;
    const xScale = d3.scaleBand().domain(days).range([0, innerWidth]).paddingInner(0.12);

    fetch("/data")
      .then(resp => resp.json())
      .then(draw);

    function timeToMinutes(str) {
      const [h, m] = str.split(":").map(Number);
      return h * 60 + m;
    }

    function draw(data) {
      const doctors = data.doctors || [];
      const slots = doctors.flatMap(doc => (doc.availability || []).map(s => ({
        doctorId: doc.id,
        day: s.day,
        start: timeToMinutes(s.start),
        end: timeToMinutes(s.end),
      })));

      const startMin = d3.min(slots, d => d.start) ?? 8 * 60;
      const endMax = d3.max(slots, d => d.end) ?? 18 * 60;
      const yScale = d3.scaleLinear().domain([startMin, endMax]).range([0, innerHeight]);

      const hours = d3.range(Math.floor(startMin / 60), Math.ceil(endMax / 60) + 1);

      // Axes and grid
      plotArea.append("g")
        .attr("class", "grid")
        .selectAll("line")
        .data(hours)
        .join("line")
        .attr("x1", 0)
        .attr("x2", innerWidth)
        .attr("y1", d => yScale(d * 60))
        .attr("y2", d => yScale(d * 60));

      plotArea.append("g")
        .attr("class", "axis")
        .call(d3.axisLeft(yScale).tickValues(hours.map(h => h * 60)).tickFormat(d => `${String(Math.floor(d / 60)).padStart(2, "0")}:00`));

      plotArea.append("g")
        .attr("class", "axis")
        .attr("transform", `translate(0, ${innerHeight})`)
        .call(d3.axisBottom(xScale));

      // Day separators
      plotArea.append("g")
        .attr("class", "grid")
        .selectAll("line.day-sep")
        .data(days)
        .join("line")
        .attr("class", "day-sep")
        .attr("x1", d => xScale(d) + xScale.bandwidth())
        .attr("x2", d => xScale(d) + xScale.bandwidth())
        .attr("y1", 0)
        .attr("y2", innerHeight);

      const color = d3.scaleOrdinal(d3.schemeTableau10).domain(doctors.map(d => d.id));

      // Controls
      const select = d3.select("#doctorSelect");
      select.selectAll("option")
        .data([{ id: "ALL", label: "All doctors" }, ...doctors.map(d => ({ id: d.id, label: d.id }))])
        .join("option")
        .attr("value", d => d.id)
        .text(d => d.label);

      select.on("change", () => renderSlots(select.property("value")));

      const summary = d3.select("#summary");

      const slotLayer = plotArea.append("g").attr("class", "slots");

      function renderSlots(selectedId) {
        const filtered = selectedId === "ALL" ? slots : slots.filter(s => s.doctorId === selectedId);
        summary.text(`Slots: ${filtered.length} | Doctors: ${selectedId === "ALL" ? doctors.length : 1}`);

        const rects = slotLayer.selectAll("rect").data(filtered, d => `${d.doctorId}-${d.day}-${d.start}-${d.end}`);

        rects.enter()
          .append("rect")
          .attr("class", "slot")
          .attr("rx", 3)
          .attr("ry", 3)
          .attr("x", d => xScale(d.day) + dayPadding / 2)
          .attr("width", xScale.bandwidth() - dayPadding)
          .attr("y", d => yScale(d.start))
          .attr("height", d => Math.max(3, yScale(d.end) - yScale(d.start)))
          .attr("fill", d => color(d.doctorId))
          .on("mousemove", (event, d) => {
            tooltip
              .style("opacity", 0.95)
              .style("left", `${event.pageX + 10}px`)
              .style("top", `${event.pageY + 10}px`)
              .html(`<strong>${d.doctorId}</strong><br/>${d.day}<br/>${minutesToStr(d.start)} - ${minutesToStr(d.end)}`);
          })
          .on("mouseleave", () => tooltip.style("opacity", 0));

        rects
          .attr("x", d => xScale(d.day) + dayPadding / 2)
          .attr("width", xScale.bandwidth() - dayPadding)
          .attr("y", d => yScale(d.start))
          .attr("height", d => Math.max(3, yScale(d.end) - yScale(d.start)))
          .attr("fill", d => color(d.doctorId));

        rects.exit().remove();
      }

      function minutesToStr(total) {
        const h = Math.floor(total / 60);
        const m = total % 60;
        return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
      }

      // Legend
      const legend = d3.select("#legend");
      legend.selectAll(".legend-item")
        .data(doctors)
        .join("div")
        .attr("class", "legend-item")
        .html(d => `<span class="legend-swatch" style="background:${color(d.id)}"></span>${d.id}`);

      renderSlots("ALL");
    }
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    test_case = load_case(args.input)
    app = create_app(test_case)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()

