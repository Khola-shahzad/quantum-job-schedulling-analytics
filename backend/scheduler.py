"""
Scheduling algorithms: FIFO, Round Robin, Priority.
Assumes job['arrival_time'] is a datetime-like object and execution_time is seconds (int).
"""
from datetime import timedelta
from collections import deque
import copy

def fifo_scheduler(jobs):
    jobs_sorted = sorted(jobs, key=lambda j: j["arrival_time"])
    current_time = jobs_sorted[0]["arrival_time"] if jobs_sorted else None
    scheduled = []
    for j in jobs_sorted:
        arrival = j["arrival_time"]
        if current_time is None or current_time < arrival:
            current_time = arrival
        start = current_time
        end = start + timedelta(seconds=int(j["execution_time"]))
        waiting = (start - arrival).total_seconds()
        turnaround = (end - arrival).total_seconds()
        scheduled.append({**j, "start_time": start, "end_time": end, "waiting_time": waiting, "turnaround_time": turnaround})
        current_time = end
    return scheduled

def round_robin_scheduler(jobs, time_slice=10):
    jobs_sorted = sorted(jobs, key=lambda j: j["arrival_time"])
    # copy and add remaining/first_start
    queue = deque()
    results = []
    idx = 0
    current_time = jobs_sorted[0]["arrival_time"] if jobs_sorted else None
    proc = []
    for j in jobs_sorted:
        r = dict(j)
        r["remaining"] = int(r["execution_time"])
        r["first_start"] = None
        proc.append(r)

    while idx < len(proc) or queue:
        while idx < len(proc) and proc[idx]["arrival_time"] <= current_time:
            queue.append(proc[idx]); idx += 1
        if not queue:
            if idx < len(proc):
                current_time = proc[idx]["arrival_time"]
                continue
            else:
                break
        job = queue.popleft()
        if job["first_start"] is None:
            job["first_start"] = current_time
        run = min(time_slice, job["remaining"])
        job["remaining"] -= run
        start = current_time
        current_time = current_time + timedelta(seconds=run)
        if job["remaining"] > 0:
            # enqueue newly arrived
            while idx < len(proc) and proc[idx]["arrival_time"] <= current_time:
                queue.append(proc[idx]); idx += 1
            queue.append(job)
        else:
            waiting = (job["first_start"] - job["arrival_time"]).total_seconds()
            turnaround = (current_time - job["arrival_time"]).total_seconds()
            results.append({**job, "start_time": job["first_start"], "end_time": current_time, "waiting_time": waiting, "turnaround_time": turnaround})
    return results

def priority_scheduler(jobs):
    jobs_sorted = sorted(jobs, key=lambda j: j["arrival_time"])
    current_time = jobs_sorted[0]["arrival_time"] if jobs_sorted else None
    ready = []
    results = []
    idx = 0
    while idx < len(jobs_sorted) or ready:
        while idx < len(jobs_sorted) and jobs_sorted[idx]["arrival_time"] <= current_time:
            ready.append(jobs_sorted[idx]); idx += 1
        if not ready:
            if idx < len(jobs_sorted):
                current_time = jobs_sorted[idx]["arrival_time"]
                continue
            else:
                break
        # smallest priority number = highest priority
        ready.sort(key=lambda j: j["priority"])
        job = ready.pop(0)
        start = current_time
        end = start + timedelta(seconds=int(job["execution_time"]))
        waiting = (start - job["arrival_time"]).total_seconds()
        turnaround = (end - job["arrival_time"]).total_seconds()
        results.append({**job, "start_time": start, "end_time": end, "waiting_time": waiting, "turnaround_time": turnaround})
        current_time = end
    return results
