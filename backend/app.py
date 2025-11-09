"""
Flask backend with MongoDB persistence.
APIs:
 - POST /run-simulation  { "algorithm": "FIFO"|"RoundRobin"|"Priority", "num_jobs": 10000 }
 - GET  /get-results
"""

from flask import Flask, request, jsonify
from pathlib import Path
from utils_hdfs import save_to_hdfs
import pandas as pd
from datetime import datetime
import dask.dataframe as dd
import os

from data_generator import generate_jobs_csv
from schedulers import fifo_scheduler, round_robin_scheduler, priority_scheduler
from db import insert_jobs, insert_results, get_results

app = Flask(__name__)

#  Use an internal path inside container
DATA_PATH = Path("/app/data/jobs_10k.csv")
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

ALGORITHMS = {
    "FIFO": fifo_scheduler,
    "RoundRobin": round_robin_scheduler,
    "Priority": priority_scheduler,
}


@app.route("/run-simulation", methods=["POST"])
def run_simulation():
    body = request.get_json(force=True)
    algo = body.get("algorithm", "FIFO")
    num_jobs = int(body.get("num_jobs", 10000))

    # 1️⃣ Generate jobs CSV (overwrite existing)
    generate_jobs_csv(DATA_PATH, n=num_jobs)

    # 2️⃣ Load jobs and insert into MongoDB
    df = pd.read_csv(DATA_PATH, parse_dates=["arrival_time"])
    jobs_for_db = df.copy()
    jobs_for_db["arrival_time"] = jobs_for_db["arrival_time"].astype(str)
    insert_jobs(jobs_for_db.to_dict(orient="records"), collection="jobs")

    # Convert arrival_time back for scheduler use
    df["arrival_time"] = pd.to_datetime(df["arrival_time"])
    jobs = df.to_dict(orient="records")

    # 3️⃣ Select and run scheduler
    if algo not in ALGORITHMS:
        return jsonify({"error": f"Unknown algorithm: {algo}"}), 400

    scheduled = ALGORITHMS[algo](jobs)
    out_df = pd.DataFrame(scheduled)

    # 4️⃣ Ensure datetime columns are correct
    for col in ["start_time", "end_time", "arrival_time"]:
        if col in out_df.columns:
            out_df[col] = pd.to_datetime(out_df[col], errors="coerce")

    # 5️⃣ Compute metrics (Dask)
    ddf = dd.from_pandas(out_df, npartitions=4)
    avg_wait = ddf["waiting_time"].mean().compute()
    avg_turn = ddf["turnaround_time"].mean().compute()

    start = out_df["arrival_time"].min()
    end = out_df["end_time"].max()
    total_seconds = (
        (end - start).total_seconds()
        if pd.notnull(start) and pd.notnull(end)
        else None
    )
    throughput = (
        len(out_df) / total_seconds if total_seconds and total_seconds > 0 else None
    )

    metrics = {
        "algorithm": algo,
        "avg_waiting_time": float(round(avg_wait, 4)),
        "avg_turnaround_time": float(round(avg_turn, 4)),
        "throughput": float(round(throughput, 6)) if throughput else None,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # 6️⃣ Convert datetime columns for Mongo insertion
    out_db = out_df.copy()
    for col in ["start_time", "end_time", "arrival_time"]:
        if col in out_db.columns:
            out_db[col] = out_db[col].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    insert_results(out_db.to_dict(orient="records"), metrics)

    # 7️⃣ Save simulation results to HDFS
    results_csv = "/app/data/simulation_results.csv"
    out_df.to_csv(results_csv, index=False)
    try:
        save_to_hdfs(results_csv, f"/simulations/{algo}_results.csv")
    except Exception as e:
        print(f"HDFS save error: {e}")


    return jsonify({"message": "Simulation complete", "metrics": metrics})


@app.route("/get-results", methods=["GET"])
def get_results_api():
    results, metrics = get_results()
    if not results:
        return jsonify({"error": "No results found"}), 404
    return jsonify({"metrics": metrics, "jobs": results[:100]})


if __name__ == "__main__":
    # ✅ Run in container on port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
