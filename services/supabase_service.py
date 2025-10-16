# services/supabase_service.py
from supabase import create_client, Client
from config import settings
from schemas import UserCreate
from security import get_password_hash
import uuid
from schemas import User

class SupabaseService:
    def __init__(self):
        self.client: Client = None

    def initialize_client(self):
        print("Initializing Supabase client...")
        url: str = settings.SUPABASE_URL
        key: str = settings.SUPABASE_KEY
        self.client = create_client(url, key)
        print("Supabase client initialized successfully.")

    def create_user(self, user: UserCreate):
        """Creates a new user in the database."""
        hashed_password = get_password_hash(user.password)
        try:
            # Note: The Supabase Python client v1 returns a list, v2 will return a model.
            # This code is for v1.
            response = self.client.table('users').insert({
                "name": user.name,
                "email": user.email,
                "hashed_password": hashed_password
            }).execute()
            
            # Check if data was returned and is not empty
            if response.data and len(response.data) > 0:
                return response.data[0] # Return the created user data
            else:
                return {"error": "User creation failed, no data returned."}

        except Exception as e:
            if "duplicate key value violates unique constraint" in str(e):
                return {"error": "A user with this email already exists."}
            return {"error": f"An unexpected database error occurred: {str(e)}"}
        
    def get_user_by_email(self, email: str):
        """Fetches a single user by their email address."""
        try:
            response = self.client.table('users').select("*").eq('email', email).limit(1).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"Error fetching user by email: {str(e)}")
            return None
        
    def upload_symptom_image(self, user_id: int, image_bytes: bytes, content_type: str):
        """Uploads an image to the symptom_images storage bucket."""
        try:
            # Create a unique file path for the image
            file_path = f"{user_id}/{uuid.uuid4()}.jpg"
            
            # Upload the file
            self.client.storage.from_("symptom_images").upload(
                path=file_path,
                file=image_bytes,
                file_options={"content-type": content_type}
            )
            
            # Get the public URL of the uploaded file
            public_url = self.client.storage.from_("symptom_images").get_public_url(file_path)
            return public_url
        except Exception as e:
            print(f"Error uploading image: {str(e)}")
            return None

    def save_query_history(self, user_id: int, symptom_text: str, response_data: dict, image_url: str = None):
        """Saves a query and its response to the database."""
        try:
            self.client.table('query_history').insert({
                "user_id": user_id,
                "symptom_text": symptom_text,
                "response_data": response_data,
                "image_url": image_url
            }).execute()
            return True
        except Exception as e:
            print(f"Error saving query history: {str(e)}")
            return False

    def get_user_history(self, user_id: int):
        """Retrieves all query history for a specific user."""
        try:
            response = self.client.table('query_history').select("*").eq('user_id', user_id).order('created_at', desc=True).execute()
            return response.data
        except Exception as e:
            print(f"Error fetching user history: {str(e)}")
            return []
        
        
# Create a single, reusable instance for the app to use
supabase_service = SupabaseService()