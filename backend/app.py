from flask import Flask, request, jsonify
from pathlib import Path
from datetime import datetime
import pandas as pd
import dask.dataframe as dd

from utils_hdfs import save_to_hdfs
from data_generator import generate_jobs_csv
from schedulers import fifo_scheduler, round_robin_scheduler, priority_scheduler
from db import insert_jobs, insert_results, get_results

app = Flask(__name__)

DATA_PATH = Path("/app/data/jobs.csv")
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

ALGORITHMS = {
    "FIFO": fifo_scheduler,
    "RoundRobin": round_robin_scheduler,
    "Priority": priority_scheduler
}

@app.route("/run-simulation", methods=["POST"])
def run_simulation():
    try:
        body = request.get_json(force=True)
        algo = body.get("algorithm", "FIFO")
        num_jobs = int(body.get("num_jobs", 10000))

        # Generate fresh jobs
        generate_jobs_csv(DATA_PATH, n=num_jobs)
        df = pd.read_csv(DATA_PATH, parse_dates=["arrival_time"])

        # Save raw jobs to MongoDB
        jobs_json = df.copy()
        jobs_json["arrival_time"] = jobs_json["arrival_time"].astype(str)
        insert_jobs(jobs_json.to_dict(orient="records"))

        jobs = df.to_dict(orient="records")

        if algo not in ALGORITHMS:
            return jsonify({"error": f"Unknown algorithm '{algo}'"}), 400

        # Run scheduler
        scheduled = ALGORITHMS[algo](jobs)
        out_df = pd.DataFrame(scheduled)

        for col in ["arrival_time", "start_time", "end_time"]:
            if col in out_df.columns:
                out_df[col] = pd.to_datetime(out_df[col])

        # Metrics
        ddf = dd.from_pandas(out_df, npartitions=4)

        avg_wait = float((ddf["start_time"] - ddf["arrival_time"]).dt.total_seconds().mean().compute())
        avg_turn = float((ddf["end_time"] - ddf["arrival_time"]).dt.total_seconds().mean().compute())

        start = out_df["arrival_time"].min()
        end = out_df["end_time"].max()

        total_s = (end - start).total_seconds()
        throughput = len(out_df) / total_s if total_s > 0 else None

        metrics = {
            "algorithm": algo,
            "avg_waiting_time": round(avg_wait, 4),
            "avg_turnaround_time": round(avg_turn, 4),
            "throughput": round(throughput, 6) if throughput else None,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Convert to JSON-safe data
        save_df = out_df.copy()
        for col in ["arrival_time", "start_time", "end_time"]:
            save_df[col] = save_df[col].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        insert_results(save_df.to_dict(orient="records"), metrics)

        # Save to HDFS
        csv_path = "/app/data/results.csv"
        out_df.to_csv(csv_path, index=False)
        save_to_hdfs(csv_path, f"/simulations/{algo}_results.csv")

        return jsonify({"message": "Simulation complete", "metrics": metrics})

    except Exception as e:
        print("Backend error:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/get-results", methods=["GET"])
def results_endpoint():
    results, metrics = get_results()
    if not results:
        return jsonify({"error": "No results"}), 404
    return jsonify({"metrics": metrics, "jobs": results[:300]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
