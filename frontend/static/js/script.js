// script.js (robust frontend for your Flask proxy + backend)
// Drop-in replacement: overwrite frontend/static/js/script.js
//
// Behavior:
// 1) POST /run-simulation (FormData) -> triggers backend run via Flask proxy
// 2) GET  /get-results to fetch actual "jobs" and "metrics"
// 3) Normalize whatever the backend returns into timeline SLICES
// 4) Draw bar chart (avg waiting, avg turnaround, throughput)
// 5) Draw CPU utilization line chart (computed client-side from slices if not provided)
// 6) Draw Gantt timeline and jobs table
//
// Notes:
// - Expects responses from /get-results like: { metrics: {...}, jobs: [ ... ] }
// - Accepts slice records with fields: job_id/id, start_time/start/end_time/end, arrival_time (ISO)
// - If backend returns aggregated job records instead of slices, front-end will convert each job to a single slice.

document.addEventListener("DOMContentLoaded", () => {
  const simForm = document.getElementById("simForm");
  const runBtn = document.getElementById("runBtn");

  const metricsPanel = document.getElementById("metricsPanel");
  const chartsPanel = document.getElementById("chartsPanel");
  const jobsPanel = document.getElementById("jobsPanel");

  const metric_algo = document.getElementById("metric_algo");
  const metric_avg_wait = document.getElementById("metric_avg_wait");
  const metric_avg_turn = document.getElementById("metric_avg_turn");
  const metric_throughput = document.getElementById("metric_throughput");
  const metric_cpu = document.getElementById("metric_cpu");

  const barCtx = document.getElementById("barChart");
  const lineCtx = document.getElementById("lineChart");

  let barChart = null;
  let lineChart = null;

  simForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    runBtn.disabled = true;
    const originalText = runBtn.textContent;
    runBtn.textContent = "Running...";

    try {
      // 1) Trigger the simulation via your Flask frontend proxy which posts to backend
      const respRun = await fetch("/run-simulation", {
        method: "POST",
        body: new FormData(simForm) // your frontend app.py expects form-encoded values
      });

      if (!respRun.ok) {
        const txt = await respRun.text();
        throw new Error(`Run failed: ${respRun.status} ${txt}`);
      }

      // 2) After run finishes, fetch actual results
      //    (your /run-simulation currently returns only metrics; /get-results returns jobs + metrics)
      const respResults = await fetch("/get-results", { method: "GET" });
      if (!respResults.ok) {
        const txt = await respResults.text();
        throw new Error(`Get results failed: ${respResults.status} ${txt}`);
      }

      const payload = await respResults.json();
      // payload expected: { metrics: {...}, jobs: [...] }
      const algorithm = (new FormData(simForm)).get("algorithm") || "FIFO";

      showResults(payload, algorithm);
    } catch (err) {
      console.error(err);
      alert("Error running simulation: " + err.message);
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = originalText;
    }
  });

  // ---------------------------
  // normalize backend returned jobs/results into TIMELINE SLICES
  // ---------------------------
  function normalizeToSlices(payload) {
    // payload: { metrics: {...}, jobs: [...] }
    const rawJobs = payload.jobs || [];
    // Two common cases:
    //  - jobs are slices already: each item has start_time & end_time
    //  - jobs are full job summaries: each item has start_time & end_time (single block) -> convert to single slice
    // We want: array of { job_id, arrival_time (Date or null), start (Date), end (Date), meta... }

    const slices = [];

    rawJobs.forEach((r) => {
      // Determine id field
      const jobId = r.job_id ?? r.id ?? r.job ?? r.jobId ?? r._id ?? r.name ?? null;

      // helper to parse timestamp-like values into Date. Accepts ISO strings or numbers.
      const parseTS = (v) => {
        if (v === null || v === undefined) return null;
        if (typeof v === "number") return new Date(v); // assume millis
        if (typeof v === "string") {
          // Accept both '2025-..Z' and '2025-..' forms
          const ds = v.trim();
          const tryIso = new Date(ds);
          if (!isNaN(tryIso.getTime())) return tryIso;
          // fallback: try to parse milliseconds number in string
          const num = Number(ds);
          if (!isNaN(num)) return new Date(num);
        }
        return null;
      };

      // map possible field names:
      const startRaw = r.start_time ?? r.start ?? r.s ?? r.start_time_iso ?? r.startTime;
      const endRaw = r.end_time ?? r.end ?? r.e ?? r.end_time_iso ?? r.endTime;
      const arrivalRaw = r.arrival_time ?? r.arrival ?? r.arrivalTime ?? r.arrival_time_iso;

      const startDate = parseTS(startRaw);
      const endDate = parseTS(endRaw);
      const arrivalDate = parseTS(arrivalRaw);

      if (startDate && endDate) {
        slices.push({
          job_id: jobId,
          arrival_time: arrivalDate,
          start: startDate,
          end: endDate,
          meta: r
        });
      } else {
        // If missing start/end but there is execution_time + arrival_time, convert to single-slice
        const exec = r.execution_time ?? r.execution ?? r.burst_time ?? r.exec_time ?? null;
        if (arrivalDate && exec) {
          const s = arrivalDate;
          const e = new Date(s.getTime() + Number(exec) * 1000);
          slices.push({
            job_id: jobId,
            arrival_time: arrivalDate,
            start: s,
            end: e,
            meta: r
          });
        } else {
          // try to salvage: if object has start and end as Date objects (unlikely), accept them:
          if (r.start_time instanceof Date && r.end_time instanceof Date) {
            slices.push({
              job_id: jobId,
              arrival_time: r.arrival_time instanceof Date ? r.arrival_time : null,
              start: r.start_time,
              end: r.end_time,
              meta: r
            });
          }
        }
      }
    });

    return slices;
  }

  // ---------------------------
  // compute CPU utilization time-series (single-core utilization percent)
  // method: create time buckets over [minStart, maxEnd], compute busy fraction per bucket
  // returns { xs: [labels], ys: [percent values 0-100] }
  // ---------------------------
  function computeCpuSeries(slices, buckets = 50) {
    if (!slices || slices.length === 0) return { xs: [""], ys: [0] };

    const starts = slices.map(s => s.start.getTime());
    const ends = slices.map(s => s.end.getTime());
    const minT = Math.min(...starts);
    const maxT = Math.max(...ends);
    const span = maxT - minT;
    if (span <= 0) return { xs: [""], ys: [0] };

    const bucketMs = Math.max(1, Math.floor(span / buckets));
    const xs = [];
    const ys = [];

    for (let i = 0; i < buckets; i++) {
      const bStart = minT + i * bucketMs;
      const bEnd = (i === buckets - 1) ? maxT : (bStart + bucketMs);
      // compute busy milliseconds inside this bucket
      let busy = 0;
      slices.forEach(s => {
        const s0 = s.start.getTime();
        const s1 = s.end.getTime();
        const ovStart = Math.max(bStart, s0);
        const ovEnd = Math.min(bEnd, s1);
        if (ovEnd > ovStart) busy += (ovEnd - ovStart);
      });
      const util = (busy / (bEnd - bStart)) * 100;
      const midLabel = new Date(Math.floor((bStart + bEnd) / 2)).toISOString();
      xs.push(midLabel);
      ys.push(Math.min(100, Math.max(0, util)));
    }
    return { xs, ys };
  }

  // ---------------------------
  // show results (metrics + slices)
  // payload may contain only metrics (run endpoint); this function expects result payload from /get-results
  // ---------------------------
  function showResults(payload, algorithm) {
    const metrics = payload.metrics || {};
    const rawJobs = payload.jobs || [];

    // normalize to slices
    const slices = normalizeToSlices(payload);

    // If backend returned no slices, but jobs collection exists separately, try to map
    // (we already handled common shapes in normalizeToSlices)

    // show metric tiles
    metricsPanel.style.display = "grid";
    chartsPanel.style.display = "block";
    jobsPanel.style.display = "block";

    metric_algo.textContent = algorithm || (metrics.algorithm || "—");
    metric_avg_wait.textContent = metrics.avg_waiting_time ?? "—";
    metric_avg_turn.textContent = metrics.avg_turnaround_time ?? "—";
    metric_throughput.textContent = metrics.throughput ?? "—";

    // compute CPU series either from metrics.cpu_time_series OR from slices
    let cpuSeries = null;
    if (metrics.cpu_time_series && Array.isArray(metrics.cpu_time_series) && metrics.cpu_time_series.length > 0) {
      // try to adapt backend time series (accept {timestamp,value} or [value,...])
      const xs = [];
      const ys = [];
      metrics.cpu_time_series.forEach(pt => {
        if (typeof pt === "object" && (pt.timestamp || pt.t)) {
          xs.push(pt.timestamp || pt.t);
          ys.push(pt.value ?? pt.cpu ?? pt.y ?? 0);
        } else if (typeof pt === "number") {
          xs.push("");
          ys.push(pt);
        }
      });
      cpuSeries = { xs, ys };
    } else {
      cpuSeries = computeCpuSeries(slices, 60);
    }

    metric_cpu.textContent = (cpuSeries && cpuSeries.ys && cpuSeries.ys.length) ? `${Math.round(cpuSeries.ys.reduce((a,b)=>a+b,0)/cpuSeries.ys.length)}%` : "—";

    // BAR chart for avg waiting / turnaround / throughput
    const barLabels = ["Avg waiting", "Avg turnaround", "Throughput"];
    const barValues = [
      metrics.avg_waiting_time || 0,
      metrics.avg_turnaround_time || 0,
      metrics.throughput || 0
    ];
    if (barChart) barChart.destroy();
    barChart = new Chart(barCtx.getContext("2d"), {
      type: "bar",
      data: {
        labels: barLabels,
        datasets: [{
          label: (algorithm || metrics.algorithm || "metrics"),
          data: barValues,
          backgroundColor: ["rgba(3,102,214,0.85)", "rgba(14,165,164,0.85)", "rgba(249,115,22,0.85)"]
        }]
      },
      options: { responsive: true, scales: { y: { beginAtZero: true } } }
    });

    // LINE chart for CPU utilization
    if (lineChart) lineChart.destroy();
    const cpuLabels = cpuSeries.xs;
    const cpuValues = cpuSeries.ys;
    lineChart = new Chart(lineCtx.getContext("2d"), {
      type: "line",
      data: {
        labels: cpuLabels,
        datasets: [{
          label: "CPU utilization %",
          data: cpuValues,
          fill: true,
          tension: 0.2,
        }]
      },
      options: {
        responsive: true,
        scales: { y: { beginAtZero: true, max: 100 } },
        interaction: { mode: 'index', intersect: false }
      }
    });

    // Jobs table (show sample records)
    renderJobsTable(rawJobs.slice(0, 200));

    // Gantt timeline using slices
    renderGantt(slices);
  }

  // ---------------------------
  // Render jobs table (simple)
  // ---------------------------
  function renderJobsTable(jobs) {
    const cont = document.getElementById("jobsTableContainer");
    cont.innerHTML = "";
    if (!jobs || jobs.length === 0) {
      cont.textContent = "No jobs returned.";
      return;
    }
    const table = document.createElement("table");
    table.className = "jobs-table";
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");

    const keys = Object.keys(jobs[0]);
    keys.forEach(k => {
      const th = document.createElement("th");
      th.textContent = k;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    jobs.forEach(j => {
      const tr = document.createElement("tr");
      keys.forEach(k => {
        const td = document.createElement("td");
        let v = j[k];
        if (v === null || v === undefined) v = "";
        td.textContent = String(v);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    cont.appendChild(table);
  }

  // ---------------------------
  // Render Gantt timeline
  // slices: array of { job_id, arrival_time, start (Date), end (Date) }
  // ---------------------------
  function renderGantt(slices) {
    const container = document.getElementById("ganttContainer");
    container.innerHTML = "";
    if (!slices || slices.length === 0) {
      container.textContent = "No results available.";
      return;
    }

    // ensure Date objects
    const norm = slices.map(s => ({
      job_id: s.job_id ?? s.id ?? s.meta?.job_id ?? s.meta?.id ?? "job",
      start: (s.start instanceof Date) ? s.start : new Date(s.start),
      end: (s.end instanceof Date) ? s.end : new Date(s.end),
      arrival: s.arrival_time instanceof Date ? s.arrival_time : (s.arrival_time ? new Date(s.arrival_time) : null)
    }));

    const minStart = Math.min(...norm.map(n => n.start.getTime()));
    const maxEnd = Math.max(...norm.map(n => n.end.getTime()));
    const span = Math.max(1, maxEnd - minStart);

    // group by job for ordering (optional)
    // We'll show slices in chronological order
    norm.sort((a,b) => a.start - b.start);

    const colors = ["bar-blue", "bar-green", "bar-orange", "bar-purple", "bar-teal"];

    norm.forEach((s, i) => {
      const row = document.createElement("div");
      row.className = "gantt-row";

      const label = document.createElement("div");
      label.className = "gantt-label";
      label.textContent = s.job_id;

      const track = document.createElement("div");
      track.className = "gantt-track";

      const bar = document.createElement("div");
      bar.className = "gantt-bar " + colors[i % colors.length];

      const leftPercent = ((s.start.getTime() - minStart) / span) * 100;
      const widthPercent = ((s.end.getTime() - s.start.getTime()) / span) * 100;

      bar.style.left = leftPercent + "%";
      bar.style.width = Math.max(0.5, widthPercent) + "%";
      bar.title = `${s.job_id}: ${s.start.toISOString()} → ${s.end.toISOString()}`;
      bar.textContent = String(s.job_id);

      track.appendChild(bar);
      row.appendChild(label);
      row.appendChild(track);
      container.appendChild(row);
    });
  }
});
