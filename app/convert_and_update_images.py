import os
import re
import tempfile
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
from PIL import Image
import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("TARGET_DB_URI")
MONGO_DB = os.getenv("TARGET_DB")
MONGO_COLLECTION = os.getenv("TARGET_COLLECTION", "posts")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION", "eu-north-1")

assert MONGO_URI and MONGO_DB and AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET, "Missing required environment variables."

# S3 client
s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=S3_REGION
)

def download_image(url):
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"❌ Failed to download {url}: {e}")
        return None

def convert_to_webp(image_bytes, quality=60):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webp") as tmp_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as jpg_file:
                jpg_file.write(image_bytes)
                jpg_file.flush()
                with Image.open(jpg_file.name) as im:
                    rgb_im = im.convert('RGB')
                    rgb_im.save(tmp_file.name, 'WEBP', quality=quality, method=6)
        return tmp_file.name
    except Exception as e:
        print(f"❌ Failed to convert image to WebP: {e}")
        return None

def upload_to_s3(filepath):
    try:
        s3_key = f"bfl-images/{os.path.basename(filepath)}"
        s3.upload_file(
            Filename=filepath,
            Bucket=S3_BUCKET,
            Key=s3_key,
            ExtraArgs={'ContentType': 'image/webp'}
        )
        url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
        return url
    except (BotoCoreError, NoCredentialsError, Exception) as e:
        print(f"❌ Failed to upload to S3: {e}")
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
        for url in image_urls[:2]:
            print(f"Processing image: {url}")
            img_bytes = download_image(url)
            if not img_bytes:   
                new_image_urls.append(url)
                continue
            webp_path = convert_to_webp(img_bytes, quality=60)
            if not webp_path:
                new_image_urls.append(url)
                continue
            new_url = upload_to_s3(webp_path)
            os.remove(webp_path)
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