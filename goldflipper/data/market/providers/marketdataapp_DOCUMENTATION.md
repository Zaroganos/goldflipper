import requests

# Your token
token = 'your_token_here'

# The API endpoint for retrieving stock quotes for SPY
url = 'https://api.marketdata.app/v1/stocks/quotes/SPY/'

# Setting up the headers for authentication
headers = {
    'Accept': 'application/json',
    'Authorization': f'Bearer {token}'
}

# Making the GET request to the API
response = requests.get(url, headers=headers)

# Checking if the request was successful
if response. status_code in (200, 203):
    # Parsing the JSON response
    data = response.json()
    print(data)
else:
    print(f'Failed to retrieve data: {response.status_code}')

__________________________________________________________
import requests

url = "https://api.marketdata.app/v1/options/lookup/AAPL%207/28/2023%20200%20Call"
response = requests.request("GET", url)

print(response.text)

___________________________________________________________
import requests

url = "https://api.marketdata.app/v1/options/chain/AAPL/"
response = requests.request("GET", url)

print(response.text)

___________________________________________________________
import requests

url = "https://api.marketdata.app/v1/options/quotes/AAPL250117C00150000/"
response = requests.request("GET", url)

print(response.text)

___________________________________________________________
import requests

url = "https://api.marketdata.app/headers/"
response = requests.get(url)

print(response.text)


