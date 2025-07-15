# Updated cURL Commands for Keywords and News Processing

## Database Structure:
- **Keywords** → `keywords.posts` collection
- **News** → `news.posts` collection  
- **Broker** → `broker.posts` collection (stays the same)

## 1. Keywords Processing (goes to keywords.posts)

```bash
curl -X POST "http://localhost:8000/keywords" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": [
      {"text": "digital marketing strategies"},
      {"text": "e-commerce trends 2024"},
      {"text": "artificial intelligence applications"}
    ],
    "target_db_name": "keywords",
    "user_email": "test@keywords.com"
  }'
```

## 2. News Processing (goes to news.posts)

```bash
curl -X POST "http://localhost:8000/news" \
  -H "Content-Type: application/json" \
  -d '{
    "country": "us",
    "language": "en",
    "category": "technology",
    "target_db_name": "news",
    "user_email": "test@news.com"
  }'
```

## 3. Check Task Status

```bash
curl -X GET "http://localhost:8000/tasks/{task_id}"
```

## 4. Check Posts Status (Broker Database)

```bash
# Connect to broker database and check posts
python -c "
from pymongo import MongoClient
client = MongoClient('mongodb+srv://zubairisworking:Ki66bNWmpi70Y9Ql@cluster0.dtdmgdx.mongodb.net/broker')
db = client['broker']
posts = list(db['posts'].find({}, {'title': 1, 'scheduledAt': 1, 'status': 1, 'target_db': 1, 'target_collection': 1}))
for post in posts:
    print(f'Title: {post.get(\"title\", \"No title\")}')
    print(f'Scheduled: {post.get(\"scheduledAt\")}')
    print(f'Status: {post.get(\"status\")}')
    print(f'Target: {post.get(\"target_db\")}.{post.get(\"target_collection\")}')
    print('---')
"
```

## 5. Check Published Posts

### Check Keywords Database:
```bash
python -c "
from pymongo import MongoClient
client = MongoClient('mongodb+srv://cryptoanalysis45:Zz5e0HLdDoF9SJXA@cluster0.zqdhkxn.mongodb.net/keywords')
db = client['keywords']
posts = list(db['posts'].find({}, {'title': 1, 'createdAt': 1, 'status': 1}))
print(f'Found {len(posts)} posts in keywords.posts')
for post in posts:
    print(f'Title: {post.get(\"title\", \"No title\")}')
    print(f'Created: {post.get(\"createdAt\")}')
    print(f'Status: {post.get(\"status\")}')
    print('---')
"
```

### Check News Database:
```bash
python -c "
from pymongo import MongoClient
client = MongoClient('mongodb+srv://cryptoanalysis45:Zz5e0HLdDoF9SJXA@cluster0.zqdhkxn.mongodb.net/news')
db = client['news']
posts = list(db['posts'].find({}, {'title': 1, 'createdAt': 1, 'status': 1}))
print(f'Found {len(posts)} posts in news.posts')
for post in posts:
    print(f'Title: {post.get(\"title\", \"No title\")}')
    print(f'Created: {post.get(\"createdAt\")}')
    print(f'Status: {post.get(\"status\")}')
    print('---')
"
```

## Scheduling:
- **Keywords**: 5-minute gaps between posts
- **News**: 10-minute gaps between posts
- **Broker**: Stores all posts initially, then publishes to respective databases 