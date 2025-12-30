"""
Flask + D3 visualization for a scheduling solution.

Usage:
    python src/visaulize_solution.py --input sample_solution.json --port 5000
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from flask import Flask, Response, jsonify, render_template_string


def load_solution(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def create_app(solution: Dict[str, Any]) -> Flask:
    app = Flask(__name__)

    @app.get("/data")
    def data() -> Response:
        return jsonify(solution)

    @app.get("/")
    def index() -> str:
        return render_template_string(
            HTML_TEMPLATE,
            status=solution.get("status", "n/a"),
            objective_value=solution.get("objective_value"),
        )

    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize scheduling solution with D3.")
    parser.add_argument("--input", "-i", type=Path, required=True, help="Path to solution JSON file.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind. Default: 5000")
    parser.add_argument("--debug", action="store_true", help="Run Flask debug mode.")
    return parser.parse_args()


HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Scheduling Solution</title>
  <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 0; background: #f7f7f7; }
    header { padding: 12px 16px; background: #0f172a; color: #e2e8f0; }
    main { padding: 16px; max-width: 1200px; margin: 0 auto; }
    #controls { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
    select, button { padding: 6px 10px; font-size: 14px; }
    #meta { color: #cbd5e1; font-size: 14px; }
    #chart { border: 1px solid #e2e8f0; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .axis line, .axis path { stroke: #cbd5e1; }
    .grid line { stroke: #e2e8f0; }
    .slot { stroke: #0f172a; stroke-width: 0.5px; fill-opacity: 0.75; }
    .legend { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; font-size: 12px; color: #334155; }
    .legend-item { display: flex; align-items: center; gap: 4px; }
    .legend-swatch { width: 12px; height: 12px; border: 1px solid #cbd5e1; }
    .tooltip { position: absolute; pointer-events: none; background: #0f172a; color: #e2e8f0;
               padding: 6px 8px; border-radius: 4px; font-size: 12px; opacity: 0; }
    #unscheduled { margin-top: 16px; background: white; padding: 12px; border: 1px solid #e2e8f0;
                   box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    #unscheduled h4 { margin: 0 0 8px 0; }
    #unscheduled ul { margin: 0; padding-left: 18px; color: #475569; }
  </style>
</head>
<body>
  <header>
    <h2 style="margin:0;">Scheduling Solution</h2>
    <div id="meta">
      Status: {{ status }} |
      Objective: {{ objective_value if objective_value is not none else "n/a" }}
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
    <div id="unscheduled">
      <h4>Unscheduled Patients</h4>
      <ul id="unscheduledList"></ul>
    </div>
  </main>
  <div class="tooltip" id="tooltip"></div>

  <script>
    const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
    const chartWidth = 1100;
    const chartHeight = 600;
    const margin = { top: 30, right: 20, bottom: 40, left: 70 };
    const doctorPadding = 6;

    const tooltip = d3.select("#tooltip");
    const chart = d3.select("#chart")
      .append("svg")
      .attr("width", chartWidth)
      .attr("height", chartHeight);

    const plotArea = chart.append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const innerWidth = chartWidth - margin.left - margin.right;
    const innerHeight = chartHeight - margin.top - margin.bottom;

    fetch("/data")
      .then(resp => resp.json())
      .then(draw);

    function timeToMinutes(str) {
      const [h, m] = str.split(":").map(Number);
      return h * 60 + m;
    }

    function draw(data) {
      const scheduledRaw = data.scheduled || [];
      const unscheduled = data.unscheduled || [];

      const dayIndex = (day) => {
        const idx = days.indexOf(day);
        return idx === -1 ? Number.MAX_SAFE_INTEGER : idx;
      };

      const slots = scheduledRaw.map(item => ({
        day: item.day || "(unknown)",
        doctorId: item.doctor_id,
        patientId: item.patient_id,
        start: timeToMinutes(item.start),
        end: timeToMinutes(item.end),
        duration: item.duration_minutes
      }));

      const doctors = Array.from(new Set(slots.map(s => s.doctorId)));
      const domainDoctors = doctors.length > 0 ? doctors : ["(none)"];
      const daysInData = Array.from(new Set(slots.map(s => s.day)))
        .sort((a, b) => dayIndex(a) - dayIndex(b));
      const domainDays = daysInData.length > 0 ? daysInData : ["(none)"];

      const xScale = d3.scaleBand().domain(domainDays).range([0, innerWidth]).paddingInner(0.12);
      const doctorBand = d3.scaleBand().domain(domainDoctors).range([0, xScale.bandwidth()]).paddingInner(0.1);

      const startMin = d3.min(slots, d => d.start) ?? 8 * 60;
      const endMax = d3.max(slots, d => d.end) ?? 18 * 60;
      const yScale = d3.scaleLinear().domain([startMin, endMax]).range([0, innerHeight]);

      const hours = d3.range(Math.floor(startMin / 60), Math.ceil(endMax / 60) + 1);

      // Grid and axes
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
        .data(domainDays)
        .join("line")
        .attr("class", "day-sep")
        .attr("x1", d => xScale(d) + xScale.bandwidth())
        .attr("x2", d => xScale(d) + xScale.bandwidth())
        .attr("y1", 0)
        .attr("y2", innerHeight);

      const color = d3.scaleOrdinal(d3.schemeTableau10).domain(domainDoctors);

      // Controls
      const select = d3.select("#doctorSelect");
      select.selectAll("option")
        .data([{ id: "ALL", label: "All doctors" }, ...doctors.map(d => ({ id: d, label: d }))])
        .join("option")
        .attr("value", d => d.id)
        .text(d => d.label);

      select.on("change", () => renderSlots(select.property("value")));

      const summary = d3.select("#summary");
      const slotLayer = plotArea.append("g").attr("class", "slots");

      function renderSlots(selectedId) {
        const filtered = selectedId === "ALL" ? slots : slots.filter(s => s.doctorId === selectedId);
        summary.text(`Scheduled: ${filtered.length} | Total scheduled: ${slots.length} | Unscheduled: ${unscheduled.length} | Doctors: ${doctors.length} | Days: ${daysInData.length || 0}`);

        const rects = slotLayer.selectAll("rect").data(filtered, d => `${d.patientId}-${d.doctorId}-${d.start}-${d.end}`);

        rects.enter()
          .append("rect")
          .attr("class", "slot")
          .attr("rx", 3)
          .attr("ry", 3)
          .attr("x", d => (xScale(d.day) ?? 0) + (doctorBand(d.doctorId) ?? 0) + doctorPadding / 2)
          .attr("width", () => Math.max(10, doctorBand.bandwidth() - doctorPadding))
          .attr("y", d => yScale(d.start))
          .attr("height", d => Math.max(3, yScale(d.end) - yScale(d.start)))
          .attr("fill", d => color(d.doctorId))
          .on("mousemove", (event, d) => {
            tooltip
              .style("opacity", 0.95)
              .style("left", `${event.pageX + 10}px`)
              .style("top", `${event.pageY + 10}px`)
              .html(`<strong>${d.patientId}</strong><br/>Doctor: ${d.doctorId}<br/>${d.day}<br/>${minutesToStr(d.start)} - ${minutesToStr(d.end)}<br/>Duration: ${d.duration} min`);
          })
          .on("mouseleave", () => tooltip.style("opacity", 0));

        rects
          .attr("x", d => (xScale(d.day) ?? 0) + (doctorBand(d.doctorId) ?? 0) + doctorPadding / 2)
          .attr("width", () => Math.max(10, doctorBand.bandwidth() - doctorPadding))
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
        .html(d => `<span class="legend-swatch" style="background:${color(d)}"></span>${d}`);

      // Unscheduled list
      const unscheduledList = d3.select("#unscheduledList");
      if (unscheduled.length === 0) {
        unscheduledList.html("<li>None</li>");
      } else {
        unscheduledList.selectAll("li")
          .data(unscheduled)
          .join("li")
          .text(d => d);
      }

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

    solution = load_solution(args.input)
    app = create_app(solution)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
