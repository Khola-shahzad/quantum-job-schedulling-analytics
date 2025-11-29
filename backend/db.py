# db.py
from pymongo import MongoClient

client = MongoClient("mongodb://mongo:27017/")
db = client["schedulerDB"]


def insert_jobs(jobs, collection="jobs"):
    db[collection].delete_many({})
    db[collection].insert_many(jobs)


def insert_results(job_slices, metrics):
    db["results"].delete_many({})
    db["results"].insert_many(job_slices)
    db["metrics"].delete_many({})
    db["metrics"].insert_one(metrics)


def get_results():
    jobs = list(db["results"].find({}, {"_id": 0}))
    metrics = db["metrics"].find_one({}, {"_id": 0})
    return jobs, metrics
