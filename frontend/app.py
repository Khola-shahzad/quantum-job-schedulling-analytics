from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

BACKEND_URL = "http://backend:5000"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/run-simulation", methods=["POST"])
def run_sim():
    algo = request.form.get("algorithm")
    num_jobs = request.form.get("num_jobs")

    resp = requests.post(
        f"{BACKEND_URL}/run-simulation",
        json={"algorithm": algo, "num_jobs": int(num_jobs)}
    )

    return jsonify(resp.json())


@app.route("/get-results", methods=["GET"])
def get_results():
    resp = requests.get(f"{BACKEND_URL}/get-results")
    return jsonify(resp.json())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501)
