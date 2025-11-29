# data_generator.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_jobs_csv(path, n=10000):
    now = datetime.utcnow()

    arrival_times = [now + timedelta(seconds=np.random.randint(0, 1000)) for _ in range(n)]
    exec_times = np.random.randint(1, 30, n)
    priorities = np.random.randint(1, 10, n)

    df = pd.DataFrame({
        "job_id": range(1, n + 1),
        "arrival_time": arrival_times,
        "execution_time": exec_times,
        "priority": priorities
    })

    df.to_csv(path, index=False)
