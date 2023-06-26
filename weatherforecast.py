import requests
from geopy.geocoders import Nominatim
import firebase_admin
from firebase_admin import db, credentials
from firebase_admin import auth

cred = credentials.Certificate('./credentials.json')

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://weather-forecast-c3699-default-rtdb.firebaseio.com/'
})

weatherapi_api_key = 'f0cc5a1940444c4885145528232406'
cache = {}
retrived_user_id = None
location_input_value = None

def get_id_token(uid):
    id_token = auth.create_custom_token(uid)
    return id_token

def get_current_user_id(id_token):
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        return uid
    except auth.AuthError:
        return None

def sign_out_user():
    try:
        auth.revoke_refresh_tokens(retrived_user_id)
        print("User signed out successfully.")
        cache = {}
        retrived_user_id = None
        location_input_value = None
    except auth.AuthError as e:
        print(f"Error signing out user: {e}")

def is_valid_uid(uid):
    try:
        auth.get_user(uid)
        return True
    except auth.AuthError:
        return False

def sign_up_user(email, password):
    try:
        user = auth.create_user(
            email=email,
            password=password
        )
        return user.uid
    except Exception as e:
        print(f"Error creating user: {str(e)}\n")
        return None

def sign_in_user(email, password):
    try:
        user = auth.get_user_by_email(email)
        return user.uid
    except Exception as e:
        print(f"Error signing in user: {str(e)}\n")
        return None

def store_weather_data(city, weather_data):
    ref = db.reference('/weather_data')
    ref.child(city).set(weather_data)

def get_weather_data(city):
    ref = db.reference('/weather_data')
    return ref.child(city).get()

def add_favorite_location(user_id, location):
    ref = db.reference('/users')
    ref.child(user_id).child('favorite_locations').push(location)

def get_favorite_locations(user_id):
    ref = db.reference('/users')
    return ref.child(user_id).child('favorite_locations').get()

def calculate_string_similarity(string1, string2):
    set1 = set(string1.lower())
    set2 = set(string2.lower())
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    similarity = len(intersection) / len(union)
    return similarity

def compare_string_with_array(string, array):
    string_lower = string.lower()
    similarity_dict = {}
    
    for element in array:
        similarity = calculate_string_similarity(string_lower, element)
        if similarity > 0.5:
            similarity_dict[element] = similarity * 100
    return similarity_dict


def get_similar_locations(city):
    geolocator = Nominatim(user_agent='weather_app')
    location = geolocator.geocode(city)

    if location:
        query = location.raw['display_name'].split(',')[0]
        search_result = geolocator.geocode(query, exactly_one=False, limit=10)
        similar_locations = {}
        if search_result:
            for result in search_result:
                similar_locations.update(compare_string_with_array(city, result.raw['display_name'].split(',')))
            if(len(similar_locations) > 0):
                cache[city]['suggestions'] = similar_locations



def display_suggestions(city, suggestions):
    print(f"\nDid you mean one of the following similar locations for '{city}'? If so, please try again.\n")
    print(", ".join(suggestions.keys()))


def display_weather_data(city):
    data = cache[city]
    if 'suggestions' in data:
        display_suggestions(city, data['suggestions'])
    elif 'error' in data:
        print_error(data['error'])
    else:
        region = data['location']['region']
        current_weather = data['current']['condition']['text']
        temperature = data['current']['temp_c']
        humidity = data['current']['humidity']
        country = data['location']['country']
        local_time = data['location']['localtime']
        wind_kph = data['current']['wind_kph']

        print('\n*****************************************************************************\n')
        print(f'Weather in {city}, {region}, {country} (WeatherAPI):\n')
        print(f'Current weather: {current_weather}')
        print(f'Temperature: {temperature} °C')
        print(f'Humidity: {humidity}%')
        print(f'Wind speed: {wind_kph} kph')
        print(f'Local time: {local_time}')
        print('\n*****************************************************************************\n')

        if(location_input_value == "str" and retrived_user_id != None):
            answer = input("Do you want to store this location as a favorite? (y/n): ")
            if(answer.lower() == "y"):
                add_favorite_location(retrived_user_id, city)
                print("Location added to favorites successfully!")

def print_error(error):
    print(f'\nError with WeatherAPI: {error}')


def get_weather(city):
    print('\nLoading...')
    data = {}
    try:
        url = f'https://api.weatherapi.com/v1/current.json?key={weatherapi_api_key}&q={city}'
        response = requests.get(url)
        data = response.json()
        cache[city] = data
        
        if 'error' in data:
            if 'error' in data and data['error']['code'] == 1006:
                get_similar_locations(city)
            raise Exception(data['error']['message'])

    except Exception as e:
        cache[city]['error'] = str(e)

    display_weather_data(city)

    get_input_data()

def check_integer_or_string(value):
    try:
        value = int(value)
        return "int"
    except ValueError:
        return "str"

def get_input_data():
    print('\n-----------------------------------------------------------------------------')
    try:
        text = 'Enter a city name (or press (CTRL + C) to quit): '
        location_dict = {}
        if(retrived_user_id != None):
            fav_location = get_favorite_locations(retrived_user_id)
            if(fav_location != None and len(fav_location) > 0):
                text = 'Enter a city name (or Enter favourite), (or press (CTRL + C) to quit): '
                print('\nYour favourite locations:')
                i = 1
                for city in fav_location:
                    location_dict[i] = fav_location[city]
                    print(f"{i}. {fav_location[city]}")
                    i = i + 1
    
        city_name_option = input(f'\n{text}')

        global location_input_value
        location_input_value = check_integer_or_string(city_name_option)
        try:
            if(location_input_value == "int"):
                city_name = str(location_dict[int(city_name_option)])
            elif(location_input_value == "str"):
                city_name = city_name_option
            else:
                print('\nInvalid input. Please try again.')
                get_input_data()

            if city_name in cache:
                print('\nfrom cache')
                display_weather_data(city_name)
                get_input_data()
            else:
                get_weather(city_name)
        except Exception:
            print('\nInvalid input. Please try again.')
            get_input_data()

    except KeyboardInterrupt:
        print('\n\nGoodbye!\n')
        pass

def prompt_user():
    print('Welcome!\n')
    print("1. Sign in")
    print("2. Sign up")
    print("3. Search city")
    print("4. Exit")

    try:
        choice = input("\nPlease choose an option: ")
        if choice == "1":
            print('\nSign in :')
            print('\n-------------------------')
            email = input("Enter your email: ")
            password = input("Enter your password: ")
            uid = sign_in_user(email, password)
            if(uid == None):
                return None
            else:
                print(f"User '{email}' Logged in successfully!")
                return uid
        elif choice == "2":
            print('\nSign up')
            print('\n-------------------------')
            email = input("Enter your email: ")
            password = input("Enter your password: ")
            uid = sign_up_user(email, password)
            if(uid == None):
                return None
            else:
                print(f"User '{email}' created successfully!")
                return uid
        elif choice == "3":
            get_input_data()
        elif choice == "4":
            exit()
        else:
            print("Invalid choice. Please try again.\n")
            prompt_user()
    except KeyboardInterrupt:
        print('\n\nGoodbye!\n')
        exit()

def main():
    print('\n                           Weather Forecast')
    print('\n-----------------------------------------------------------------------------\n')
    uid = None
    while(True):
        if(uid == None):
            uid = prompt_user()
        if(uid != None and is_valid_uid(uid)):
            global retrived_user_id
            retrived_user_id = uid
            get_input_data()
            break

main()
