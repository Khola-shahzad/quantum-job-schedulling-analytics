"""
MongoDB helper (pymongo).
Insert / fetch jobs, results, metrics.
"""
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

# MongoDB connection settings
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "quantum_scheduler")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

def insert_jobs(jobs, collection="jobs"):
    """
    Replace all jobs in the given collection.
    """
    db[collection].delete_many({})
    if jobs:
        db[collection].insert_many(jobs)
    print(f"Inserted {len(jobs)} jobs into '{collection}'")


def insert_results(results, metrics, collection="results"):
    """
    Insert simulation results and metrics, replacing previous data.
    Ensures that inserted data is JSON-safe.
    """
    db[collection].delete_many({})
    db["metrics"].delete_many({})

    # Remove MongoDB ObjectIds if re-inserting previously fetched docs
    clean_results = []
    for r in results:
        r.pop("_id", None)
        clean_results.append(r)

    clean_metrics = dict(metrics)
    clean_metrics.pop("_id", None)

    if clean_results:
        db[collection].insert_many(clean_results)

    db["metrics"].insert_one(clean_metrics)
    print("Inserted results and metrics")


def get_results():
    """
    Fetch results and metrics as pure JSON-serializable objects.
    """
    results = list(db["results"].find({}, {"_id": 0}))
    metrics = db["metrics"].find_one({}, {"_id": 0})
    return results, metrics
