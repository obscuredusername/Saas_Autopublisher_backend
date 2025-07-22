# Curl Commands with JWT Authentication

This guide provides curl commands for all API endpoints with JWT authentication. **Database selection is done on the admin dashboard** - users select a database on the dashboard, and all operations use that selected database automatically.

## Quick Start

1. **Sign up** (if you don't have an account)
2. **Login** to get your JWT token
3. **Select database** on the admin dashboard
4. **Use the token** in the Authorization header for all other requests

## Authentication Setup

### 1. Sign Up
```bash
curl -X POST "http://localhost:8000/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "password": "your-secure-password"
  }'
```

### 2. Login (Get JWT Token)
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "password": "your-secure-password"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Save your token:**
```bash
export JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Database Management (Admin Dashboard)

### Store Database Configuration
```bash
curl -X POST "http://localhost:8000/admin/store-db-config" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "name": "my-database",
    "target_db_uri": "mongodb://localhost:27017",
    "target_db": "my_database",
    "description": "My custom database configuration"
  }'
```

### Select Database (This affects all operations)
```bash
curl -X POST "http://localhost:8000/admin/select-db" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "name": "my-database"
  }'
```

### List Database Configurations
```bash
curl -X GET "http://localhost:8000/admin/list-db-configs" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Get Current Target Database
```bash
curl -X GET "http://localhost:8000/admin/get-target-db" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Set Target Database
```bash
curl -X POST "http://localhost:8000/admin/set-target-db" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "target_db_uri": "mongodb://localhost:27017",
    "target_db": "my_database"
  }'
```

### Delete Database Configuration
```bash
curl -X DELETE "http://localhost:8000/admin/delete-db-config/my-database" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

## Keywords Endpoints

### Process Keywords (Uses Dashboard Database)

```bash
curl -X POST "http://localhost:8000/keywords/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "keywords": [
      {
        "text": "artificial intelligence",
        "minLength": 1000
      },
      {
        "text": "machine learning",
        "minLength": 800
      }
    ],
    "country": "us",
    "language": "en",
    "user_email": "your-email@example.com"
  }'
```

### Check Task Status
```bash
curl -X GET "http://localhost:8000/keywords/task-status/YOUR_TASK_ID" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Get User Tasks
```bash
curl -X GET "http://localhost:8000/keywords/my-tasks" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

## News Endpoints

### Get Supported Countries
```bash
curl -X GET "http://localhost:8000/news/supported-countries" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Process News (Uses Dashboard Database)

**POST Method:**
```bash
curl -X POST "http://localhost:8000/news/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "country": "us",
    "language": "en",
    "category": "technology",
    "user_email": "your-email@example.com"
  }'
```

**GET Method:**
```bash
curl -X GET "http://localhost:8000/news/?country=us&language=en&category=technology" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Get User News
```bash
curl -X GET "http://localhost:8000/news/my-news" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

## Content Endpoints

### Generate Content
```bash
curl -X POST "http://localhost:8000/content/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "keywords": [
      {
        "text": "blockchain technology",
        "minLength": 1200
      }
    ],
    "country": "us",
    "language": "en",
    "user_email": "your-email@example.com"
  }'
```

## User Management

### Get Current User Info
```bash
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Refresh Token
```bash
curl -X POST "http://localhost:8000/auth/refresh" \
  -H "Authorization: Bearer YOUR_REFRESH_TOKEN"
```

## Example Workflows

### Workflow 1: Setup and Use Database
```bash
# 1. Login
export JWT_TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}' | \
  jq -r '.access_token')

# 2. Store database configuration
curl -X POST "http://localhost:8000/admin/store-db-config" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "name": "my-blog-db",
    "target_db_uri": "mongodb://localhost:27017",
    "target_db": "blog_content"
  }'

# 3. Select the database (this affects all operations)
curl -X POST "http://localhost:8000/admin/select-db" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{"name": "my-blog-db"}'

# 4. Generate content (uses selected database)
curl -X POST "http://localhost:8000/keywords/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "keywords": [{"text": "AI trends 2024", "minLength": 1000}],
    "country": "us",
    "language": "en",
    "user_email": "user@example.com"
  }'
```

### Workflow 2: Switch Databases
```bash
# 1. Check current database
curl -X GET "http://localhost:8000/admin/get-target-db" \
  -H "Authorization: Bearer $JWT_TOKEN"

# 2. Switch to different database
curl -X POST "http://localhost:8000/admin/select-db" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{"name": "news-db"}'

# 3. Process news (uses new database)
curl -X POST "http://localhost:8000/news/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{
    "country": "us",
    "language": "en",
    "category": "technology",
    "user_email": "user@example.com"
  }'
```

## Response Examples

### Successful Task Creation
```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "queued"
}
```

### Task Status Response
```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "SUCCESS",
  "result": "Content generation completed successfully"
}
```

### Database Selection Response
```json
{
  "success": true,
  "message": "Database 'my-database' activated successfully. All operations will now use blog_content",
  "target_db_uri": "mongodb://localhost:27017",
  "target_db": "blog_content"
}
```

### Error Response
```json
{
  "detail": "Could not validate credentials"
}
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized**: Token expired or invalid
   - Solution: Login again to get a new token

2. **400 Bad Request**: Missing required fields
   - Solution: Check the request body format

3. **404 Not Found**: Endpoint not found
   - Solution: Verify the URL and ensure the server is running

4. **500 Internal Server Error**: Server error
   - Solution: Check server logs for details

5. **"invalid country" Error**: Invalid country code passed to NewsAPI
   - Solution: Use only supported country codes (ISO 3166-1 alpha-2 format)
   - Check supported countries: `GET /news/supported-countries`
   - Common valid codes: `us`, `gb`, `in`, `au`, `ca`, `de`, `fr`, `it`, `nl`, `no`, `se`, `br`, `mx`, `ar`, `co`, `ve`, `my`, `sg`, `th`, `id`, `ph`, `jp`, `kr`, `cn`, `tw`, `hk`, `il`, `ae`, `sa`, `za`, `ng`, `eg`, `ma`
   - Invalid examples: `usa`, `uk`, `india` (use `us`, `gb`, `in` instead)

### Token Management

```bash
# Check if token is valid
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer $JWT_TOKEN"

# If token is expired, login again
export JWT_TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}' | \
  jq -r '.access_token')
```

## Environment Variables

Make sure these are set in your `.env` file:

```env
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
MONGODB_URL=mongodb://localhost:27017
TARGET_DB_URI=mongodb://localhost:27017
TARGET_DB=CRM
```

## Notes

- **Database Selection**: Done on admin dashboard, not in request forms
- **Global Selection**: Changing database on dashboard affects all operations
- **No Form Fields**: No `target_db_name` needed in keywords/news requests
- **Token Expiration**: Tokens expire after 30 minutes by default
- **Background Processing**: All content generation runs in the background
- **Task Tracking**: Use task IDs to monitor progress 