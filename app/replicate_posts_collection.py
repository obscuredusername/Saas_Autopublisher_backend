import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

SOURCE_URI = os.getenv("SOURCE_DB_URI") or os.getenv("MONGODB_URL")
SOURCE_DB = os.getenv("SOURCE_DB")
TARGET_URI = os.getenv("TARGET_DB_URI")
TARGET_DB = os.getenv("TARGET_DB")
TARGET_COLLECTION = os.getenv("TARGET_COLLECTION", "posts")
NEW_COLLECTION = os.getenv("NEW_COLLECTION", "posts_backup")

assert SOURCE_URI and SOURCE_DB and TARGET_URI and TARGET_DB and TARGET_COLLECTION and NEW_COLLECTION, "Missing required environment variables."

def main():
    target_client = MongoClient(TARGET_URI)
    source_client = MongoClient(SOURCE_URI)
    target_col = target_client[TARGET_DB][TARGET_COLLECTION]
    new_col = source_client[SOURCE_DB][NEW_COLLECTION]

    total = 0
    copied = 0
    for doc in target_col.find():
        total += 1
        if new_col.find_one({"_id": doc["_id"]}):
            print(f"Skipping existing doc: {doc['_id']}")
            continue
        try:
            new_col.insert_one(doc)
            copied += 1
            print(f"Copied doc: {doc['_id']}")
        except Exception as e:
            print(f"❌ Failed to copy doc {doc['_id']}: {e}")
    print(f"Done. Total: {total}, Copied: {copied}, Skipped: {total - copied}")

if __name__ == "__main__":
    main() 