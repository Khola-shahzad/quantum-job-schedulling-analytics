"""
Generate synthetic quantum job logs.
Fields: job_id, arrival_time (ISO), qubits_required, execution_time, priority
"""
import csv
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

def generate_jobs_csv(path: str, n: int = 10000):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["job_id", "arrival_time", "qubits_required", "execution_time", "priority"]

    start_time = datetime.utcnow()
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i in range(n):
            job_id = str(uuid.uuid4())
            # arrivals spaced randomly around start_time
            arrival = start_time + timedelta(seconds=random.expovariate(1 / 5) * i % 7200)
            qubits_required = random.choices([1,2,3,4,5], weights=[40,30,15,10,5])[0]
            execution_time = max(1, int(random.gauss(30 * qubits_required, 10)))
            priority = random.choices([1,2,3], weights=[10,30,60])[0]  # 1 highest
            writer.writerow({
                "job_id": job_id,
                "arrival_time": arrival.isoformat(),
                "qubits_required": qubits_required,
                "execution_time": execution_time,
                "priority": priority,
            })
    print(f"Generated {n} jobs to {path}")

if __name__ == "__main__":
    generate_jobs_csv("../data/jobs_10k.csv", 10000)
