from hdfs import InsecureClient
import os

def get_hdfs_client():
    """
    Connect to HDFS NameNode using the environment variable HDFS_URL.
    Example: http://hadoop-namenode:9870
    """
    hdfs_url = os.getenv("HDFS_URL", "http://hadoop-namenode:9870")
    return InsecureClient(hdfs_url, user="root")


def save_to_hdfs(local_path, hdfs_path):
    """
    Uploads a local file to HDFS.
    Creates directory if missing.
    """
    try:
        client = get_hdfs_client()
        client.makedirs(os.path.dirname(hdfs_path))
        client.upload(hdfs_path, local_path, overwrite=True)
        print(f"Saved to HDFS: {hdfs_path}")
    except Exception as e:
        print(f"HDFS upload failed: {e}")
