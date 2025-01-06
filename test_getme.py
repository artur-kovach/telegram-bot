import requests

TOKEN = "7890592508:AAGBVL2XvUewLkyDP1H9AW50d7hDa8hxom8"
url = f"https://api.telegram.org/bot{TOKEN}/getMe"

response = requests.get(url)
print(response.json())
