# main.py
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware # Import the CORS middleware
from schemas import SymptomCheckRequest, UserCreate, User
from services import gemini_service, location_service
from services.supabase_service import supabase_service
from fastapi.security import OAuth2PasswordRequestForm
from security import verify_password, create_access_token
from dependencies import get_current_user

app = FastAPI(
    title="Healthcare Symptom Checker API",
    description="An API to suggest possible conditions based on symptoms.",
    version="0.1.0",
)

# --- THIS IS THE FIX ---
# Define the list of allowed origins (your frontend URL)
origins = [
    "https'://medilens-o54a.onrender.com",
    "http://localhost",
    "http://localhost:8080",
    # Add any other origins you might test from, like a local development server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)
# --- END OF FIX ---


@app.on_event("startup")
async def startup_supabase_client():
    supabase_service.initialize_client()

@app.get("/")
def read_root():
    return {"message": "Symptom Checker API is running!"}

# ... (the rest of your main.py file remains exactly the same)
@app.post("/signup", response_model=User)
async def create_user(user: UserCreate):
    db_user = supabase_service.create_user(user)
    if "error" in db_user:
        raise HTTPException(status_code=400, detail=db_user["error"])
    return db_user

@app.post("/login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = supabase_service.get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.get("hashed_password")):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/history")
async def get_user_query_history(current_user: User = Depends(get_current_user)):
    history = supabase_service.get_user_history(current_user.id)
    return history

@app.post("/analyze/text")
async def analyze_symptoms(request: SymptomCheckRequest, current_user: User = Depends(get_current_user)):
    analysis_result = await gemini_service.get_symptom_analysis(request.symptoms)
    if "error" in analysis_result:
        raise HTTPException(status_code=500, detail=analysis_result["error"])
    
    if request.latitude and request.longitude:
        hospitals = await location_service.get_nearby_hospitals(request.latitude, request.longitude)
        analysis_result["nearby_hospitals"] = hospitals
        
    supabase_service.save_query_history(user_id=current_user.id, symptom_text=request.symptoms, response_data=analysis_result)
    return analysis_result

@app.post("/analyze/image")
async def analyze_symptoms_with_image(
    image: UploadFile = File(...),
    symptoms: Optional[str] = Form(default="No additional text symptoms provided."),
    latitude: Optional[float] = Form(default=None),
    longitude: Optional[float] = Form(default=None),
    current_user: User = Depends(get_current_user)
):
    image_bytes = await image.read()
    image_url = supabase_service.upload_symptom_image(user_id=current_user.id, image_bytes=image_bytes, content_type=image.content_type)
    if not image_url:
        raise HTTPException(status_code=500, detail="Failed to upload image.")

    analysis_result = await gemini_service.get_multimodal_analysis(symptoms=symptoms, image_bytes=image_bytes)
    if "error" in analysis_result:
        raise HTTPException(status_code=500, detail=analysis_result["error"])
        
    if latitude is not None and longitude is not None:
        hospitals = await location_service.get_nearby_hospitals(latitude, longitude)
        analysis_result["nearby_hospitals"] = hospitals
    
    supabase_service.save_query_history(user_id=current_user.id, symptom_text=symptoms, response_data=analysis_result, image_url=image_url)
    return analysis_result