from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any, Optional, List
import os
from google import genai

# 1. INITIALIZATION
app = FastAPI(title="Smart Blog Editor API")

# 2. CORS SETUP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. CONFIGURATION
SECRET_KEY = os.getenv("SECRET_KEY", "$92940234$%@") 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

MONGO_URL = "mongodb+srv://sharmanikhil87841:Airmarshall90@cluster0.yhj3pnh.mongodb.net/?appName=Cluster0"
client = AsyncIOMotorClient(MONGO_URL)
db = client.blog_editor 
posts_collection = db.posts
users_collection = db.users

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDPeXN98S-4SvCGDWIPNgd9QOApusLOyAA")
genai_client = genai.Client(api_key=GEMINI_API_KEY)

class User(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class PostSchema(BaseModel):
    id: str
    title: str
    content: Dict[str, Any]
    status: str

class PostUpdateSchema(BaseModel):
    title: Optional[str] = None
    content: Optional[Dict[str, Any]] = None

class AIRequest(BaseModel):
    text: str

# 5. AUTH UTILITIES
def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception

# 6. AUTH ENDPOINTS
@app.post("/api/signup")
async def signup(user: User):
    existing_user = await users_collection.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    user_dict = {
        "username": user.username,
        "hashed_password": hash_password(user.password)
    }
    await users_collection.insert_one(user_dict)
    return {"message": "User created successfully"}

@app.post("/api/login", response_model=Token)
async def login(user: User):
    db_user = await users_collection.find_one({"username": user.username})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# 7. BLOG POST ENDPOINTS


@app.post("/api/posts/")
async def create_post(post: PostSchema, current_user: str = Depends(get_current_user)):
    post_data = post.model_dump()
    post_data["_id"] = post_data.pop("id")
    post_data["author"] = current_user
    post_data["created_at"] = datetime.now()
    
    await posts_collection.update_one(
        {"_id": post_data["_id"]},
        {"$set": post_data},
        upsert=True
    )
    return {"message": "Draft saved", "id": post_data["_id"]}
@app.patch("/api/posts/{post_id}")
async def update_post(
    post_id: str,
    update_data: PostUpdateSchema,
    current_user: str = Depends(get_current_user)
):
    # Prepare fields to update
    updated_fields = {
        k: v for k, v in update_data.dict().items() if v is not None
    }

    updated_fields["updated_at"] = datetime.now()

    # Upsert: update if exists, create if not
    await posts_collection.update_one(
        {"_id": post_id},
        {
            "$set": updated_fields,
            "$setOnInsert": {
                "author": current_user,
                "created_at": datetime.now(),
                "status": "Draft"
            }
        },
        upsert=True
    )

    return {"message": "Auto-save successful"}

@app.post("/api/posts/{post_id}/publish")
async def publish_post(post_id: str, current_user: str = Depends(get_current_user)):
    result = await posts_collection.update_one(
        {"_id": post_id, "author": current_user},
        {"$set": {"status": "Published", "published_at": datetime.utcnow()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Post not found or unauthorized")
    return {"message": "Published"}

# 8. AI ENDPOINT
@app.post("/api/ai/generate")
async def generate_summary(request: AIRequest, current_user: str = Depends(get_current_user)):
    try:
        prompt = f"Summarize the following content in 2 sentences: {request.text}"
        response = genai_client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt
        )
        return {"summary": response.text or "Could not generate summary."}
    except Exception as e:
        raise HTTPException(status_code=500, detail="AI Service Error")

# 9. GET USER POSTS (Bonus for Sidebar)
@app.get("/api/posts/", response_model=List[Dict[str, Any]])
async def get_user_posts(current_user: str = Depends(get_current_user)):
    cursor = posts_collection.find({"author": current_user})
    posts = await cursor.to_list(length=100)
    for p in posts:
        p["id"] = p.pop("_id")
    return posts