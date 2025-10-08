"""
Flask backend with MongoDB persistence.
APIs:
 - POST /run-simulation  { "algorithm": "FIFO"|"RoundRobin"|"Priority", "num_jobs": 10000 }
 - GET  /get-results
"""
from flask import Flask, request, jsonify
from pathlib import Path
import pandas as pd
from datetime import datetime
from data_generator import generate_jobs_csv
from schedulers import fifo_scheduler, round_robin_scheduler, priority_scheduler
from db import insert_jobs, insert_results, get_results
import dask.dataframe as dd

app = Flask(__name__)
DATA_PATH = Path("../data/jobs_10k.csv")

ALGORITHMS = {
    "FIFO": fifo_scheduler,
    "RoundRobin": round_robin_scheduler,
    "Priority": priority_scheduler
}

@app.route("/run-simulation", methods=["POST"])
def run_simulation():
    body = request.get_json(force=True)
    algo = body.get("algorithm", "FIFO")
    num_jobs = int(body.get("num_jobs", 10000))

    # 1) Generate jobs CSV (overwrites)
    generate_jobs_csv(DATA_PATH, n=num_jobs)

    # 2) Load jobs (parse arrival_time)
    df = pd.read_csv(DATA_PATH, parse_dates=["arrival_time"])
    # Convert arrival_time to ISO string for safe Mongo insertion
    jobs_for_db = df.copy()
    jobs_for_db["arrival_time"] = jobs_for_db["arrival_time"].astype(str)
    jobs_list = jobs_for_db.to_dict(orient="records")
    insert_jobs(jobs_list, collection="jobs")

    # Convert arrival_time back to pandas datetime for scheduling
    df["arrival_time"] = pd.to_datetime(df["arrival_time"])
    jobs = df.to_dict(orient="records")

    # 3) Run scheduler
    if algo not in ALGORITHMS:
        return jsonify({"error": "Unknown algorithm"}), 400

    scheduled = ALGORITHMS[algo](jobs)
    out_df = pd.DataFrame(scheduled)

    # Ensure datetime columns are proper datetimes
    for col in ["start_time", "end_time", "arrival_time"]:
        if col in out_df.columns:
            out_df[col] = pd.to_datetime(out_df[col])

    # 4) Compute metrics (Dask)
    ddf = dd.from_pandas(out_df, npartitions=4)
    avg_wait = ddf["waiting_time"].mean().compute()
    avg_turn = ddf["turnaround_time"].mean().compute()
    # throughput = total_jobs / total_elapsed_seconds
    start = out_df["arrival_time"].min()
    end = out_df["end_time"].max()
    total_seconds = (end - start).total_seconds() if pd.notnull(start) and pd.notnull(end) else None
    throughput = len(out_df) / total_seconds if total_seconds and total_seconds > 0 else None

    metrics = {
        "algorithm": algo,
        "avg_waiting_time": float(round(avg_wait, 4)),
        "avg_turnaround_time": float(round(avg_turn, 4)),
        "throughput": float(round(throughput, 6)) if throughput else None,
        "timestamp": datetime.utcnow().isoformat()
    }

    # 5) Prepare results for DB: convert datetimes to ISO strings
    out_db = out_df.copy()
    for col in ["start_time", "end_time", "arrival_time"]:
        if col in out_db.columns:
            out_db[col] = out_db[col].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    results_list = out_db.to_dict(orient="records")

    insert_results(results_list, metrics)

    return jsonify({"message": "Simulation complete", "metrics": metrics})

@app.route("/get-results", methods=["GET"])
def get_results_api():
    results, metrics = get_results()
    if not results:
        return jsonify({"error": "No results"}), 404
    # return top 100 results (already primitives)
    return jsonify({"metrics": metrics, "jobs": results[:100]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
