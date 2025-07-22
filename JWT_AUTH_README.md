# JWT Authentication System

This document explains the JWT authentication system implemented for your API. All endpoints now require proper authentication using JWT tokens.

## 🔐 Features

- **JWT Token Authentication**: Secure token-based authentication
- **User Registration & Login**: Complete user management
- **Token Refresh**: Automatic token refresh capability
- **Protected Endpoints**: All API endpoints require authentication
- **User-Specific Operations**: Operations are tied to authenticated users

## 📁 Files Modified/Added

### 1. **`app/dependencies/auth.py`** - Authentication Dependencies
- **`get_current_user()`**: JWT token verification dependency
- **`get_current_active_user()`**: Active user validation
- **`get_current_admin_user()`**: Admin user validation (placeholder)

### 2. **`app/services/auth_service.py`** - Enhanced Auth Service
- **Improved JWT handling**: Better token creation and verification
- **User management**: User creation, authentication, and validation
- **Token refresh**: Refresh token functionality
- **Database integration**: Proper MongoDB integration

### 3. **`app/routes/auth.py`** - Authentication Routes
- **`POST /auth/signup`**: User registration
- **`POST /auth/login`**: User login
- **`POST /auth/refresh`**: Token refresh
- **`GET /auth/me`**: Get current user info

### 4. **Protected Routes** - All routes now require authentication
- **`app/routes/keywords.py`**: Keyword processing endpoints
- **`app/routes/news.py`**: News processing endpoints
- **`app/routes/admin.py`**: Admin management endpoints
- **`app/routes/content.py`**: Content processing endpoints

### 5. **`main.py`** - Updated Main Application
- **Database middleware**: Proper database injection
- **Enhanced logging**: Better startup messages

## ⚙️ Configuration

### Environment Variables

Add these to your `.env` file:

```env
# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Database Configuration
MONGODB_URL=mongodb://localhost:27017
TARGET_DB_URI=mongodb://localhost:27017
SOURCE_DB=scraper_db
TARGET_DB=CRM
SOURCE_COLLECTION=generated_content
TARGET_COLLECTION=posts
```

### JWT Secret Key

**IMPORTANT**: Generate a strong secret key:

```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 🚀 How to Use

### 1. User Registration

```bash
curl -X POST "http://localhost:8000/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

**Response:**
```json
{
  "email": "user@example.com"
}
```

### 2. User Login

```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 3. Using Protected Endpoints

```bash
curl -X POST "http://localhost:8000/keywords/" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": [{"text": "artificial intelligence"}],
    "target_db_name": "my_database"
  }'
```

### 4. Token Refresh

```bash
curl -X POST "http://localhost:8000/auth/refresh" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 5. Get Current User Info

```bash
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## 📋 API Endpoints

### Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/signup` | Create new user account | No |
| POST | `/auth/login` | Login and get JWT token | No |
| POST | `/auth/refresh` | Refresh JWT token | Yes |
| GET | `/auth/me` | Get current user info | Yes |

### Protected Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/keywords/` | Process keywords | Yes |
| GET | `/keywords/task-status/{task_id}` | Get task status | Yes |
| GET | `/keywords/my-tasks` | Get user's tasks | Yes |
| POST | `/news/` | Process news | Yes |
| GET | `/news/` | Get news articles | Yes |
| GET | `/news/my-news` | Get user's news | Yes |
| POST | `/content/keywords` | Process content | Yes |
| POST | `/admin/store-db-config` | Store DB config | Yes |
| POST | `/admin/select-db` | Select database | Yes |
| GET | `/admin/list-db-configs` | List DB configs | Yes |
| DELETE | `/admin/delete-db-config/{name}` | Delete DB config | Yes |
| POST | `/admin/set-target-db` | Set target DB | Yes |
| GET | `/admin/get-target-db` | Get target DB | Yes |

## 🔒 Security Features

### JWT Token Security
- **Secret Key**: Uses environment variable for secret key
- **Algorithm**: HS256 (configurable)
- **Expiration**: Configurable token expiration (default: 30 minutes)
- **Payload**: Includes user email, expiration, and token type

### User Management
- **Password Hashing**: Uses bcrypt for secure password storage
- **User Validation**: Checks for existing users during registration
- **Account Status**: Supports user account activation/deactivation
- **Email Validation**: Uses Pydantic EmailStr for email validation

### Database Security
- **User Isolation**: Operations are tied to authenticated users
- **Input Validation**: All inputs are validated using Pydantic models
- **Error Handling**: Proper error responses without exposing sensitive data

## 🧪 Testing

### Test User Registration

```bash
# Test registration
curl -X POST "http://localhost:8000/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass123"}'
```

### Test Login and Protected Endpoint

```bash
# Login and get token
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass123"}' | \
  jq -r '.access_token')

# Use token for protected endpoint
curl -X POST "http://localhost:8000/keywords/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"keywords": [{"text": "test"}], "target_db_name": "test_db"}'
```

## 🔧 Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check if JWT token is valid and not expired
   - Verify token format: `Bearer <token>`
   - Check JWT_SECRET_KEY environment variable

2. **400 Bad Request (Registration)**
   - Email already exists
   - Invalid email format
   - Password too weak

3. **401 Unauthorized (Login)**
   - Incorrect email or password
   - User account deactivated

4. **500 Internal Server Error**
   - Check MongoDB connection
   - Verify environment variables
   - Check application logs

### Debug Mode

To enable debug logging, modify the logging level:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📊 Database Schema

### Users Collection

```javascript
{
  "_id": ObjectId("..."),
  "email": "user@example.com",
  "password": "$2b$12$...", // bcrypt hashed
  "created_at": ISODate("2024-01-15T10:30:00Z"),
  "is_active": true
}
```

### DB Configs Collection

```javascript
{
  "_id": ObjectId("..."),
  "name": "config_name",
  "target_db_uri": "mongodb://...",
  "target_db": "database_name",
  "description": "Description",
  "created_by": "user@example.com",
  "created_at": ISODate("2024-01-15T10:30:00Z")
}
```

## 🎯 Benefits

✅ **Secure**: JWT-based authentication with proper token management  
✅ **Scalable**: Stateless authentication suitable for distributed systems  
✅ **User-Specific**: All operations are tied to authenticated users  
✅ **Configurable**: Easy to adjust token expiration and security settings  
✅ **Standard**: Uses industry-standard JWT tokens  
✅ **Comprehensive**: Complete authentication flow with refresh tokens  

## 🔄 Migration from Unauthenticated

If you were using the API without authentication before:

1. **Create a user account** using `/auth/signup`
2. **Login** to get your JWT token
3. **Include the token** in all API requests using the `Authorization` header
4. **Update your client code** to handle authentication

The API will now automatically associate all operations with the authenticated user, providing better security and user isolation. 