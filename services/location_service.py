import httpx # type: ignore
from config import settings

async def get_nearby_hospitals(latitude: float, longitude: float):
    """
    Finds nearby hospitals using the Geoapify Places API.
    Use supported categories: healthcare.hospital and healthcare.clinic_or_praxis
    """
    api_key = settings.GEOAPIFY_API_KEY
    base_url = "https://api.geoapify.com/v2/places"

    # Preferred categories: hospital + clinic_or_praxis (supported by Geoapify)
    preferred_categories = "healthcare.hospital,healthcare.clinic_or_praxis"
    fallback_categories = "healthcare.hospital,healthcare"  # fallback if strict categories rejected
    params = {
        "categories": preferred_categories,
        "filter": f"circle:{longitude},{latitude},5000",
        "bias": f"proximity:{longitude},{latitude}",
        "limit": 7,
        "apiKey": api_key
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            hospitals = []
            for feature in data.get("features", []):
                properties = feature.get("properties", {})
                hospitals.append({
                    "name": properties.get("name", "N/A"),
                    "address": properties.get("address_line2", properties.get("formatted", "Address not available")),
                    "distance_meters": int(properties.get("distance", 0))
                })
            return hospitals

        except httpx.HTTPStatusError as e:
            # If Geoapify rejects our preferred category, try a fallback category set once
            status = e.response.status_code
            body = e.response.text
            print(f"Geoapify HTTP error: {status} - {body}")

            # If 400 and looks like "Invalid parameters" for categories, attempt fallback
            if status == 400 and "Invalid parameters" in body:
                print("Attempting fallback categories:", fallback_categories)
                params["categories"] = fallback_categories
                try:
                    resp2 = await client.get(base_url, params=params)
                    resp2.raise_for_status()
                    data2 = resp2.json()
                    hospitals = []
                    for feature in data2.get("features", []):
                        properties = feature.get("properties", {})
                        hospitals.append({
                            "name": properties.get("name", "N/A"),
                            "address": properties.get("address_line2", properties.get("formatted", "Address not available")),
                            "distance_meters": int(properties.get("distance", 0))
                        })
                    return hospitals
                except httpx.HTTPStatusError as e2:
                    print(f"Fallback also failed: {e2.response.status_code} - {e2.response.text}")
                    return {"error": f"Error from location service: {e2.response.status_code} - {e2.response.text}"}
                except Exception as ex2:
                    print("Unexpected error on fallback:", ex2)
                    return {"error": "Unexpected error contacting location service in fallback."}
            else:
                return {"error": f"Error from location service: {status} - {body}"}

        except httpx.RequestError as e:
            print(f"Request error while contacting Geoapify: {e}")
            return {"error": "Failed to connect to the location service."}

        except Exception as e:
            print("Unexpected exception in get_nearby_hospitals:", e)
            return {"error": f"An unexpected error occurred: {str(e)}"}
