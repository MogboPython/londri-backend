from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="londri_app")

def get_location(address: str):
    location = geolocator.geocode(address)
    if location is None:
        return None, None
    return location.latitude, location.longitude