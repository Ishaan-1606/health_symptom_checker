import io
import google.generativeai as genai # type: ignore
import json
from config import settings
from PIL import Image

genai.configure(api_key=settings.GOOGLE_API_KEY)

async def get_symptom_analysis(symptoms: str):
    """
    Sends symptoms to the Gemini API and gets a structured analysis.
    """
    # This is a crucial step: engineering the prompt.
    # We instruct the model to return a JSON object with a specific structure.
    prompt = f"""
    Analyze the following symptoms and provide a probable medical condition analysis.
    The user's symptoms are: "{symptoms}".

    Based on these symptoms, please return a JSON object with the following structure:
    {{
      "possible_conditions": [
        {{
          "condition": "Name of the condition",
          "confidence_score": "A percentage indicating your confidence (e.g., '75%')."
        }}
      ],
      "recommended_next_steps": "Provide a few clear, actionable next steps for the user.",
      "disclaimer": "This is for informational purposes only and not a substitute for professional medical advice. Please consult a healthcare provider."
    }}

    Only return the raw JSON object. Do not include any other text or markdown formatting like ```json.
    """

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = await model.generate_content_async(prompt)
        
        # Clean the response to ensure it's valid JSON
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        
        # Parse the JSON string into a Python dictionary
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Error during Gemini API call: {e}")
        return {"error": "Failed to get analysis from the model."}
    
async def get_multimodal_analysis(symptoms: str, image_bytes: bytes):
    """
    Sends both text symptoms and an image to the Gemini API for analysis.
    """
    prompt = f"""
    Analyze the following symptoms and the attached image to provide a probable medical condition analysis.
    The user's symptoms are: "{symptoms}".

    Based on the text and the image, please return a JSON object with the following structure:
    {{
      "possible_conditions": [
        {{
          "condition": "Name of the condition",
          "confidence_score": "A percentage indicating your confidence (e.g., '75%')."
        }}
      ],
      "recommended_next_steps": "Provide a few clear, actionable next steps for the user based on both image and text.",
      "disclaimer": "This is for informational purposes only and not a substitute for professional medical advice. Please consult a healthcare provider."
    }}

    Only return the raw JSON object. Do not include any other text or markdown formatting like ```json.
    """

    try:
        # Load the image from bytes
        img = Image.open(io.BytesIO(image_bytes))

        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # The prompt is a list containing the text and the image
        response = await model.generate_content_async([prompt, img])
        
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Error during Gemini API multimodal call: {e}")
        return {"error": f"An internal error occurred: {str(e)}"}