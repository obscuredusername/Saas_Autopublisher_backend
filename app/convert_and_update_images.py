import os
import re
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("TARGET_DB_URI")
MONGO_DB = os.getenv("TARGET_DB")
MONGO_COLLECTION = os.getenv("TARGET_COLLECTION", "posts")
FASTAPI_URL = os.getenv("IMAGE_SERVER_URL", "http://localhost:8000/save-image")
API_KEY = os.getenv("IMAGE_SERVER_API_KEY", "b7e2c1f4-8a2e-4c3a-9e1d-2f6b7a5c9e3f")

assert MONGO_URI and MONGO_DB, "Missing required environment variables."

def sanitize_name(name):
    return re.sub(r'[^a-zA-Z0-9_-]', '', name)

def upload_via_fastapi(image_url, name):
    payload = {
        "apikey": API_KEY,
        "name": sanitize_name(name),
        "image_url": image_url
    }
    try:
        resp = requests.post(FASTAPI_URL, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return data["url"]
        else:
            print(f"❌ FastAPI error: {data}")
            return None
    except Exception as e:
        print(f"❌ FastAPI upload failed: {e}")
        return None

def replace_img_srcs(content, old_new_url_map):
    def replacer(match):
        src = match.group(1)
        return match.group(0).replace(src, old_new_url_map.get(src, src))
    return re.sub(r'<img\s+[^>]*src="([^"]+)"[^>]*>', replacer, content)

def main():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[MONGO_COLLECTION]
    total = 0
    updated = 0
    for doc in collection.find({"image_urls": {"$exists": True, "$ne": []}}):
        total += 1
        image_urls = doc.get("image_urls", [])
        content = doc.get("content", "")
        if not image_urls or not content:
            continue
        old_new_url_map = {}
        new_image_urls = []
        for idx, url in enumerate(image_urls[:2]):
            print(f"Processing image: {url}")
            # Use doc _id and idx for unique name if needed
            name = f"{doc.get('_id', 'img')}_{idx}"
            new_url = upload_via_fastapi(url, name)
            if new_url:
                old_new_url_map[url] = new_url
                new_image_urls.append(new_url)
            else:
                new_image_urls.append(url)
        # Update content
        new_content = replace_img_srcs(content, old_new_url_map)
        # Update DB
        result = collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"image_urls": new_image_urls, "content": new_content}}
        )
        if result.modified_count:
            updated += 1
            print(f"✅ Updated post {doc['_id']} with new image URLs.")
    print(f"Done. Processed {total} posts, updated {updated}.")

if __name__ == "__main__":
    main() 