# schedulers.py
"""
Scheduling algorithms: FIFO, Round Robin, Priority.
Each job is a dict with:
    job_id, arrival_time (datetime), execution_time (int), priority
"""

from datetime import timedelta
from collections import deque


def fifo_scheduler(jobs):
    jobs_sorted = sorted(jobs, key=lambda j: j["arrival_time"])
    current_time = jobs_sorted[0]["arrival_time"]
    result = []

    for j in jobs_sorted:
        arrival = j["arrival_time"]
        if current_time < arrival:
            current_time = arrival

        start = current_time
        end = start + timedelta(seconds=j["execution_time"])

        result.append({
            "job_id": j["job_id"],
            "arrival_time": arrival,
            "start_time": start,
            "end_time": end
        })

        current_time = end

    return result


def round_robin_scheduler(jobs, time_slice=10):
    jobs_sorted = sorted(jobs, key=lambda j: j["arrival_time"])
    queue = deque()
    slices = []
    idx = 0

    if not jobs_sorted:
        return []

    current_time = jobs_sorted[0]["arrival_time"]

    # extend job objects
    jobs_ex = []
    for j in jobs_sorted:
        jobs_ex.append({
            **j,
            "remaining": j["execution_time"]
        })

    while idx < len(jobs_ex) or queue:
        # load jobs into queue
        while idx < len(jobs_ex) and jobs_ex[idx]["arrival_time"] <= current_time:
            queue.append(jobs_ex[idx])
            idx += 1

        if not queue:
            current_time = jobs_ex[idx]["arrival_time"]
            continue

        job = queue.popleft()
        run = min(time_slice, job["remaining"])

        start = current_time
        end = start + timedelta(seconds=run)

        slices.append({
            "job_id": job["job_id"],
            "arrival_time": job["arrival_time"],
            "start_time": start,
            "end_time": end
        })

        job["remaining"] -= run
        current_time = end

        # add newly arrived jobs during execution
        while idx < len(jobs_ex) and jobs_ex[idx]["arrival_time"] <= current_time:
            queue.append(jobs_ex[idx])
            idx += 1

        if job["remaining"] > 0:
            queue.append(job)

    return slices


def priority_scheduler(jobs):
    jobs_sorted = sorted(jobs, key=lambda j: j["arrival_time"])
    current_time = jobs_sorted[0]["arrival_time"]
    ready = []
    idx = 0
    result = []

    while idx < len(jobs_sorted) or ready:
        while idx < len(jobs_sorted) and jobs_sorted[idx]["arrival_time"] <= current_time:
            ready.append(jobs_sorted[idx])
            idx += 1

        if not ready:
            current_time = jobs_sorted[idx]["arrival_time"]
            continue

        ready.sort(key=lambda j: j["priority"])
        j = ready.pop(0)

        start = current_time
        end = start + timedelta(seconds=j["execution_time"])

        result.append({
            "job_id": j["job_id"],
            "arrival_time": j["arrival_time"],
            "start_time": start,
            "end_time": end
        })

        current_time = end

    return result
