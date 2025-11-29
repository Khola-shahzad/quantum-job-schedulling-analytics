# utils_hdfs.py
import requests
import os

HDFS_NAMENODE = os.getenv("HDFS_URL", "http://hadoop-namenode:9870")

def save_to_hdfs(local_file, hdfs_path):
    """
    Upload files to HDFS using WebHDFS REST API (no CLI needed).
    """
    try:
        # WebHDFS requires two-step upload
        url = f"{HDFS_NAMENODE}/webhdfs/v1{hdfs_path}?op=CREATE&overwrite=true"
        r1 = requests.put(url, allow_redirects=False)

        if "Location" not in r1.headers:
            print("HDFS error: missing redirect:", r1.text)
            return False

        upload_url = r1.headers["Location"]

        with open(local_file, "rb") as f:
            r2 = requests.put(upload_url, data=f)

        if r2.status_code not in (200, 201):
            print("Upload failed:", r2.text)
            return False

        print("Saved to HDFS:", hdfs_path)
        return True

    except Exception as e:
        print("HDFS upload exception:", str(e))
        return False
