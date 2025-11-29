import requests

url = "https://api.marketdata.app/status/"
response = requests.get(url)

print(response.text)
