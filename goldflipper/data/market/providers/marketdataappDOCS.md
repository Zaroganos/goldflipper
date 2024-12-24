
# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\authentication.mdx

---
title: Authentication
sidebar_position: 3
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

The Market Data API uses a **Bearer Token** for authentication. The token is required for each request you make to the API. There are two ways to pass this token to the API with your requests:

1. Header Authentication
2. URL Parameter Authentication

:::tip
We recommend using header-based authentication to ensure your token is not stored or cached. While Market Data makes a conscientious effort to delete tokens from our own server logs, we cannot guarantee that your token will not be stored by any of our third party cloud infrastructure partners.
:::

## Header Authentication

Add the token to the ```Authorization``` header using the word ```Bearer```. 

### Code Examples

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

```http
GET /v1/stocks/quotes/SPY/ HTTP/1.1
Host: api.marketdata.app
Accept: application/json
Authorization: Bearer {token}
```

:::tip
The curly braces around token are a placeholder for this example. Do not actually wrap your token with curly braces. 
:::

</TabItem>
<TabItem value="Node.js" label="Node.js">

```javascript
const https = require('https');

// Your token
const token = 'your_token_here';

// The API endpoint for retrieving stock quotes for SPY
const url = 'https://api.marketdata.app/v1/stocks/quotes/SPY/';

// Making the GET request to the API
https.get(url, {
    headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`
    }
}, (response) => {
    let data = '';

    // A chunk of data has been received.
    response.on('data', (chunk) => {
        data += chunk;
    });

    // The whole response has been received. Print out the result.
    response.on('end', () => {
        if (response.statusCode === 200 || response.statusCode === 203) {
            console.log(JSON.parse(data));
        } else {
            console.log(`Failed to retrieve data: ${response.statusCode}`);
        }
    });
}).on("error", (err) => {
    console.log("Error: " + err.message);
});
```

</TabItem>
<TabItem value="Python" label="Python">

```python
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
```

</TabItem>


<TabItem value="Go" label="Go">

```go
// Import the Market Data SDK
import api "github.com/MarketDataApp/sdk-go"

func main() {
    // Create a new Market Data client instance
    marketDataClient := api.New()

    // Set the token for authentication
    // Replace "your_token_here" with your actual token
    marketDataClient.Token("your_token_here")

    // Now the client is ready to make authenticated requests to the Market Data API
    
    // Use the client to create a StockQuoteRequest
	sqr, err := api.StockQuote(marketDataClient).Symbol("SPY").Get()
    if err != nil {
		fmt.Println("Error fetching stock quotes:", err)
		return
	}

	// Process the retrieved quote
	for _, quote := range quotes {
		fmt.Printf(quote)
	}
}
```

</TabItem>
</Tabs>


## URL Parameter Authentication

Add the token as a variable directly in the URL using the format ```token=YOUR_TOKEN_HERE```. For example:

```
https://api.marketdata.app/v1/stocks/quotes/SPY/?token={token}
```

:::tip
The curly braces around token are a placeholder for this example. Do not actually wrap your token with curly braces. 
:::

### Demo The API With No Authentication

You can try stock, option, and index endpoints with several different symbols that are unlocked and do not require a token. 

- Try any stock endpoint with **AAPL**, no token required.
- Try any option endpoint with any AAPL contract, for example: **AAPL250117C00150000**. No token required.
- Try any index endpoint using **VIX**, no token required.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\compact\authentication.mdx

---
title: Authentication
sidebar_position: 3
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

The Market Data API uses a **Bearer Token** for authentication. The token is required for each request you make to the API. There are two ways to pass this token to the API with your requests:

1. Header Authentication
2. URL Parameter Authentication

:::tip
We recommend using header-based authentication to ensure your token is not stored or cached. While Market Data makes a conscientious effort to delete tokens from our own server logs, we cannot guarantee that your token will not be stored by any of our third party cloud infrastructure partners.
:::

## Header Authentication

Add the token to the ```Authorization``` header using the word ```Bearer```. 

### Code Examples

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

```http
GET /v1/stocks/quotes/SPY/ HTTP/1.1
Host: api.marketdata.app
Accept: application/json
Authorization: Bearer {token}
```

:::tip
The curly braces around token are a placeholder for this example. Do not actually wrap your token with curly braces. 
:::

</TabItem>
<TabItem value="Node.js" label="Node.js">

```javascript
const https = require('https');

// Your token
const token = 'your_token_here';

// The API endpoint for retrieving stock quotes for SPY
const url = 'https://api.marketdata.app/v1/stocks/quotes/SPY/';

// Making the GET request to the API
https.get(url, {
    headers: {
        'Accept': 'application/json',
        'Authorization': `Bearer ${token}`
    }
}, (response) => {
    let data = '';

    // A chunk of data has been received.
    response.on('data', (chunk) => {
        data += chunk;
    });

    // The whole response has been received. Print out the result.
    response.on('end', () => {
        if (response.statusCode === 200 || response.statusCode === 203) {
            console.log(JSON.parse(data));
        } else {
            console.log(`Failed to retrieve data: ${response.statusCode}`);
        }
    });
}).on("error", (err) => {
    console.log("Error: " + err.message);
});
```

</TabItem>
<TabItem value="Python" label="Python">

```python
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
```

</TabItem>


<TabItem value="Go" label="Go">

```go
// Import the Market Data SDK
import api "github.com/MarketDataApp/sdk-go"

func main() {
    // Create a new Market Data client instance
    marketDataClient := api.New()

    // Set the token for authentication
    // Replace "your_token_here" with your actual token
    marketDataClient.Token("your_token_here")

    // Now the client is ready to make authenticated requests to the Market Data API
    
    // Use the client to create a StockQuoteRequest
	sqr, err := api.StockQuote(marketDataClient).Symbol("SPY").Get()
    if err != nil {
		fmt.Println("Error fetching stock quotes:", err)
		return
	}

	// Process the retrieved quote
	for _, quote := range quotes {
		fmt.Printf(quote)
	}
}
```

</TabItem>
</Tabs>


## URL Parameter Authentication

Add the token as a variable directly in the URL using the format ```token=YOUR_TOKEN_HERE```. For example:

```
https://api.marketdata.app/v1/stocks/quotes/SPY/?token={token}
```

:::tip
The curly braces around token are a placeholder for this example. Do not actually wrap your token with curly braces. 
:::

### Demo The API With No Authentication

You can try stock, option, and index endpoints with several different symbols that are unlocked and do not require a token. 

- Try any stock endpoint with **AAPL**, no token required.
- Try any option endpoint with any AAPL contract, for example: **AAPL250117C00150000**. No token required.
- Try any index endpoint using **VIX**, no token required.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\compact\candles.mdx

---
title: Candles tg h
sidebar_position: 1
tags:
  - "API: High Usage"
---

Get historical price candles for a stock.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/stocks/candles/{resolution}/{symbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/stocks/candles/D/AAPL?from=2020-01-01&to=2020-12-31](https://api.marketdata.app/v1/stocks/candles/D/AAPL?from=2020-01-01&to=2020-12-31)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch(
  "https://api.marketdata.app/v1/stocks/candles/D/AAPL?from=2020-01-01&to=2020-12-31"
)
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });

```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/stocks/candles/D/AAPL?from=2020-01-01&to=2020-12-31"

response = requests.request("GET", url)

print(response.text)
```
</TabItem>
<TabItem value="Go" label="Go">

```go title="stockCandles.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleStockCandlesRequest() {
	candles, err := StockCandles().Resolution("D").Symbol("AAPL").From("2020-01-01").To("2020-12-31").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, candle := range candles {
		fmt.Println(candle)
	}
}

```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "c": [217.68, 221.03, 219.89],
  "h": [222.49, 221.5, 220.94],
  "l": [217.19, 217.1402, 218.83],
  "o": [221.03, 218.55, 220],
  "t": [1569297600, 1569384000, 1569470400],
  "v": [33463820, 24018876, 20730608]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **resolution** `string`

  The duration of each candle.

  - Minutely Resolutions: (`minutely`, `1`, `3`, `5`, `15`, `30`, `45`, ...)
  - Hourly Resolutions: (`hourly`, `H`, `1H`, `2H`, ...)
  - Daily Resolutions: (`daily`, `D`, `1D`, `2D`, ...)
  - Weekly Resolutions: (`weekly`, `W`, `1W`, `2W`, ...)
  - Monthly Resolutions: (`monthly`, `M`, `1M`, `2M`, ...)
  - Yearly Resolutions:(`yearly`, `Y`, `1Y`, `2Y`, ...)

- **symbol** `string`

  The company's ticker symbol.

</TabItem>
<TabItem value="date" label="Dates">

All `date` parameters are optional. By default the most recent candle is returned if no date parameters are provided.

- **from** `date`

  The leftmost candle on a chart (inclusive). From and countback are mutually exclusive. If you use `countback`, `from` must be omitted. Accepted timestamp inputs: ISO 8601, unix, spreadsheet. 

- **to** `date`

  The rightmost candle on a chart (inclusive). Accepted timestamp inputs: ISO 8601, unix, spreadsheet.

- **countback** `number`

  Will fetch a specific number of candles before (to the left of) `to`. From and countback are mutually exclusive. If you use `from`, `countback` must be omitted.

:::note
There is no maximum date range limit on daily candles. When requesting intraday candles of any resolution, no more than 1 year of data can be requested in a single request.
:::

</TabItem>
<TabItem value="optional" label="Optional">

- **extended** `boolean`

  Include extended hours trading sessions when returning *intraday* candles. Daily resolutions _never_ return extended hours candles.

  - Daily candles default: `false`.
  - Intraday candles default: `false`.

- **adjustsplits** `boolean`

  Adjust historical data for stock splits. Market Data uses the CRSP methodology for adjustment.

  - Daily candles default: `true`.
  - Intraday candles default: `false`.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  ll always be `ok` when there is data for the candles requested.

- **o** `array[number]`

  Open price.

- **h** `array[number]`

  High price.

- **l** `array[number]`

  Low price.

- **c** `array[number]`

  Close price.

- **v** `array[number]`

  Volume.

- **t** `array[number]`
  Candle time (Unix timestamp, UTC). Daily, weekly, monthly, yearly candles are returned without times.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no candles are found for the request.

- **nextTime** `number` optional

  Unix time of the next quote if there is no data in the requested period, but there is data in a subsequent period.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\compact\chain.mdx

---
title: Option Chain
sidebar_position: 3
---

Get a current or historical end of day options chain for an underlying ticker symbol. Optional parameters allow for extensive filtering of the chain. Use the optionSymbol returned from this endpoint to get quotes, greeks, or other information using the other endpoints.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/options/chain/{underlyingSymbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/options/chain/AAPL/?expiration=2025-01-17&side=call](https://api.marketdata.app/v1/options/chain/AAPL/?expiration=2025-01-17&side=call)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch("https://api.marketdata.app/v1/options/chain/AAPL/")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/options/chain/AAPL/"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="optionChain.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleOptionChainRequest() {
	AAPL, err := OptionChain().UnderlyingSymbol("AAPL").Get()
	if err != nil {
		fmt.Println("Error fetching option chain:", err)
		return
	}
	for _, contract := range AAPL {
		fmt.Println(contract)
	}
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "optionSymbol": [
    "AAPL230616C00060000", "AAPL230616C00065000", "AAPL230616C00070000", "AAPL230616C00075000", "AAPL230616C00080000", "AAPL230616C00085000", "AAPL230616C00090000", "AAPL230616C00095000", "AAPL230616C00100000", "AAPL230616C00105000", "AAPL230616C00110000", "AAPL230616C00115000", "AAPL230616C00120000", "AAPL230616C00125000", "AAPL230616C00130000", "AAPL230616C00135000", "AAPL230616C00140000", "AAPL230616C00145000", "AAPL230616C00150000", "AAPL230616C00155000", "AAPL230616C00160000", "AAPL230616C00165000", "AAPL230616C00170000", "AAPL230616C00175000", "AAPL230616C00180000", "AAPL230616C00185000", "AAPL230616C00190000", "AAPL230616C00195000", "AAPL230616C00200000", "AAPL230616C00205000", "AAPL230616C00210000", "AAPL230616C00215000", "AAPL230616C00220000", "AAPL230616C00225000", "AAPL230616C00230000", "AAPL230616C00235000", "AAPL230616C00240000", "AAPL230616C00245000", "AAPL230616C00250000", "AAPL230616C00255000", "AAPL230616C00260000", "AAPL230616C00265000", "AAPL230616C00270000", "AAPL230616C00280000", "AAPL230616C00290000", "AAPL230616C00300000", "AAPL230616P00060000", "AAPL230616P00065000", "AAPL230616P00070000", "AAPL230616P00075000", "AAPL230616P00080000", "AAPL230616P00085000", "AAPL230616P00090000", "AAPL230616P00095000", "AAPL230616P00100000", "AAPL230616P00105000", "AAPL230616P00110000", "AAPL230616P00115000", "AAPL230616P00120000", "AAPL230616P00125000", "AAPL230616P00130000", "AAPL230616P00135000", "AAPL230616P00140000", "AAPL230616P00145000", "AAPL230616P00150000", "AAPL230616P00155000", "AAPL230616P00160000", "AAPL230616P00165000", "AAPL230616P00170000", "AAPL230616P00175000", "AAPL230616P00180000", "AAPL230616P00185000", "AAPL230616P00190000", "AAPL230616P00195000", "AAPL230616P00200000", "AAPL230616P00205000", "AAPL230616P00210000", "AAPL230616P00215000", "AAPL230616P00220000", "AAPL230616P00225000", "AAPL230616P00230000", "AAPL230616P00235000", "AAPL230616P00240000", "AAPL230616P00245000", "AAPL230616P00250000", "AAPL230616P00255000", "AAPL230616P00260000", "AAPL230616P00265000", "AAPL230616P00270000", "AAPL230616P00280000", "AAPL230616P00290000", "AAPL230616P00300000"
  ],
  "underlying": [
    "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL"
  ],
  "expiration": [
    1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600
  ],
  "side": [
    "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put"
  ],
  "strike": [
    60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160, 165, 170, 175, 180, 185, 190, 195, 200, 205, 210, 215, 220, 225, 230, 235, 240, 245, 250, 255, 260, 265, 270, 280, 290, 300, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160, 165, 170, 175, 180, 185, 190, 195, 200, 205, 210, 215, 220, 225, 230, 235, 240, 245, 250, 255, 260, 265, 270, 280, 290, 300
  ],
  "firstTraded": [
    1617197400, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616506200, 1616506200, 1616506200, 1616506200, 1616506200, 1616506200, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1617370200, 1617888600, 1618234200, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1626701400, 1626701400, 1626701400, 1626701400, 1617197400, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616506200, 1616506200, 1616506200, 1616506200, 1616506200, 1616506200, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1617370200, 1617888600, 1618234200, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1626701400, 1626701400, 1626701400, 1626701400
  ],
  "dte": [
    26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26
  ],
  "updated": [
    1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875
  ],
  "bid": [
    114.1, 108.6, 103.65, 98.6, 93.6, 88.9, 84.3, 80.2, 74.75, 70, 64.35, 59.4, 54.55, 50, 45.1, 40.45, 35.75, 30.8, 25.7, 20.6, 15.9, 11.65, 7.55, 4.15, 1.77, 0.57, 0.18, 0.07, 0.03, 0.02, 0.02, 0.01, 0.01, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.01, 0.01, 0.02, 0.02, 0.03, 0.04, 0.06, 0.07, 0.11, 0.14, 0.22, 0.32, 0.52, 0.92, 1.74, 3.3, 5.9, 9.8, 14.7, 19.3, 24.25, 28.7, 32.95, 38.65, 44.7, 48.4, 53.05, 58.8, 63.55, 68.05, 73.2, 78.5, 84.1, 88.05, 92.9, 103.15, 113.4, 123.05
  ],
  "bidSize": [
    90, 90, 90, 90, 90, 90, 90, 98, 90, 102, 90, 90, 90, 90, 102, 90, 95, 95, 99, 258, 118, 202, 96, 38, 36, 30, 180, 310, 31, 319, 5, 822, 216, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 14, 64, 10, 163, 2, 5, 79, 31, 4, 1, 208, 30, 146, 5, 35, 1, 5, 6, 98, 90, 90, 90, 90, 90, 98, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90
  ],
  "mid": [
    115.5, 110.38, 105.53, 100.5, 95.53, 90.28, 85.53, 80.68, 75.58, 70.75, 65.55, 60.67, 55.55, 50.9, 45.88, 40.7, 35.88, 30.93, 26.3, 20.93, 16.18, 11.78, 7.62, 4.2, 1.79, 0.58, 0.18, 0.08, 0.04, 0.03, 0.03, 0.01, 0.02, 0.09, 0.05, 0.09, 0.01, 0.08, 0.01, 0.08, 0.03, 0.23, 0.26, 0.51, 0.01, 0.01, 0.01, 0.01, 0.01, 0.03, 0.01, 0.08, 0.08, 0.01, 0.01, 0.01, 0.03, 0.07, 0.07, 0.04, 0.07, 0.08, 0.11, 0.16, 0.23, 0.33, 0.53, 0.94, 1.76, 3.33, 5.97, 10.2, 14.95, 20.52, 24.95, 30, 34.83, 39.88, 45, 49.83, 54.85, 59.85, 64.82, 69.75, 74.78, 80.12, 85.4, 89.9, 94.8, 104.95, 114.68, 124.82
  ],
  "ask": [
    116.9, 112.15, 107.4, 102.4, 97.45, 91.65, 86.75, 81.15, 76.4, 71.5, 66.75, 61.95, 56.55, 51.8, 46.65, 40.95, 36, 31.05, 26.9, 21.25, 16.45, 11.9, 7.7, 4.25, 1.81, 0.6, 0.19, 0.08, 0.05, 0.04, 0.03, 0.02, 0.03, 0.17, 0.1, 0.17, 0.01, 0.16, 0.02, 0.16, 0.05, 0.46, 0.51, 1.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.05, 0.02, 0.16, 0.16, 0.01, 0.02, 0.02, 0.04, 0.12, 0.1, 0.05, 0.07, 0.09, 0.12, 0.18, 0.23, 0.34, 0.54, 0.95, 1.78, 3.35, 6.05, 10.6, 15.2, 21.75, 25.65, 31.3, 36.7, 41.1, 45.3, 51.25, 56.65, 60.9, 66.1, 71.45, 76.35, 81.75, 86.7, 91.75, 96.7, 106.75, 115.95, 126.6
  ],
  "askSize": [
    90, 90, 90, 90, 90, 90, 90, 102, 90, 96, 90, 90, 90, 90, 96, 102, 90, 95, 96, 114, 103, 126, 90, 156, 20, 98, 397, 563, 251, 528, 238, 1, 30, 117, 99, 173, 89, 151, 196, 90, 92, 90, 90, 248, 1, 340, 180, 75, 50, 156, 1, 174, 231, 50, 500, 48, 2, 222, 136, 229, 587, 411, 226, 1, 128, 105, 142, 188, 34, 61, 45, 120, 105, 109, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90
  ],
  "last": [
    115, 107.82, 105.75, 100.45, 94.2, 90.66, 86, 81, 75.59, 71.08, 66.07, 61.64, 55.8, 50.77, 46.12, 41.05, 35.9, 30.81, 25.95, 21.3, 16.33, 11.8, 7.6, 4.2, 1.78, 0.59, 0.18, 0.08, 0.05, 0.02, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, null, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.02, 0.02, 0.02, 0.02, 0.04, 0.05, 0.06, 0.08, 0.11, 0.16, 0.23, 0.33, 0.52, 0.93, 1.76, 3.27, 6, 10.1, 14.84, 20.74, 25.39, 30.65, 37.1, null, 44.8, 59.6, 55.35, null, 83.49, null, 101.5, null, 109.39, null, 120.55, 128.67, 139.85, 151.1
  ],
  "openInterest": [
    21957, 3012, 2796, 1994, 1146, 558, 2598, 988, 6574, 509, 1780, 917, 2277, 1972, 10751, 6080, 35508, 17559, 33003, 32560, 49905, 75976, 56201, 62509, 59821, 39370, 24498, 51472, 17565, 921, 13428, 273, 6935, 518, 4496, 533, 8128, 10, 14615, 100, 6765, 0, 2481, 3831, 2474, 17228, 57338, 9503, 13614, 8027, 7938, 3752, 21276, 13550, 46981, 14401, 26134, 40858, 34215, 33103, 92978, 47546, 67687, 35527, 87587, 51117, 72338, 82643, 43125, 12822, 2955, 619, 112, 2, 44, 3, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ],
  "volume": [
    0, 0, 1, 4, 0, 8, 1, 43, 15, 49, 10, 5, 6, 5, 58, 72, 31, 427, 207, 104, 380, 1070, 3179, 7619, 10678, 5488, 1267, 718, 420, 73, 18, 1, 137, 348, 844, 27, 6, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0, 0, 0, 5, 0, 0, 0, 50, 23, 36, 32, 250, 142, 155, 135, 1969, 1068, 2005, 3018, 2641, 7861, 13154, 6299, 6389, 664, 101, 12, 0, 0, 0, 0, 0, 100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ],
  "inTheMoney": [
    true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true
  ],
  "intrinsicValue": [
    115.13, 110.13, 105.13, 100.13, 95.13, 90.13, 85.13, 80.13, 75.13, 70.13, 65.13, 60.13, 55.13, 50.13, 45.13, 40.13, 35.13, 30.13, 25.13, 20.13, 15.13, 10.13, 5.13, 0.13, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4.87, 9.87, 14.87, 19.87, 24.87, 29.87, 34.87, 39.87, 44.87, 49.87, 54.87, 59.87, 64.87, 69.87, 74.87, 79.87, 84.87, 89.87, 94.87, 104.87, 114.87, 124.87
  ],
  "extrinsicValue": [
    0.37, 0.25, 0.4, 0.37, 0.4, 0.15, 0.4, 0.55, 0.45, 0.62, 0.42, 0.55, 0.42, 0.77, 0.75, 0.57, 0.75, 0.8, 1.17, 0.8, 1.05, 1.65, 2.5, 4.07, 1.79, 0.58, 0.18, 0.08, 0.04, 0.03, 0.03, 0.01, 0.02, 0.09, 0.05, 0.09, 0.01, 0.08, 0.01, 0.08, 0.03, 0.23, 0.26, 0.51, 0.01, 0.01, 0.01, 0.01, 0.01, 0.03, 0.01, 0.08, 0.08, 0.01, 0.01, 0.01, 0.03, 0.07, 0.07, 0.04, 0.07, 0.08, 0.11, 0.16, 0.23, 0.33, 0.53, 0.94, 1.76, 3.33, 1.1, 0.33, 0.08, 0.65, 0.08, 0.13, 0.05, 0, 0.13, 0.05, 0.02, 0.02, 0.05, 0.12, 0.09, 0.25, 0.53, 0.03, 0.07, 0.08, 0.19, 0.05
  ],
  "underlyingPrice": [
    175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13
  ],
  "iv": [
    1.629, 1.923, 1.829, 1.696, 1.176, 1.455, 1.023, 0.978, 0.929, 0.795, 0.757, 0.676, 0.636, 0.592, 0.546, 0.422, 0.393, 0.361, 0.331, 0.282, 0.257, 0.231, 0.21, 0.192, 0.176, 0.167, 0.171, 0.184, 0.2, 0.224, 0.254, 0.268, 0.296, 0.322, 0.347, 0.36, 0.384, 0.407, 0.429, 0.451, 0.472, 0.492, 0.512, 0.551, 0.589, 0.624, 1.268, 1.177, 1.093, 1.014, 0.942, 0.872, 0.807, 0.745, 0.708, 0.651, 0.628, 0.573, 0.539, 0.501, 0.469, 0.431, 0.395, 0.359, 0.325, 0.291, 0.26, 0.233, 0.212, 0.194, 0.177, 0.164, 0.223, 0.274, 0.322, 0.396, 0.432, 0.452, 0.476, 0.53, 0.66, 0.677, 0.661, 0.769, 0.776, 0.73, 0.873, 0.863, 0.974, 1.063, 1.013, 1.092
  ],
  "delta": [
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.998, 0.99, 0.971, 0.927, 0.849, 0.728, 0.549, 0.328, 0.147, 0.052, 0.014, 0.003, 0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -0.002, -0.01, -0.029, -0.073, -0.151, -0.272, -0.451, -0.672, -0.853, -0.948, -0.986, -0.997, -0.999, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1
  ],
  "gamma": [
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.001, 0.002, 0.006, 0.012, 0.021, 0.032, 0.043, 0.042, 0.028, 0.013, 0.004, 0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.001, 0.002, 0.006, 0.012, 0.021, 0.032, 0.043, 0.042, 0.028, 0.013, 0.004, 0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ],
  "theta": [
    -0.009, -0.009, -0.01, -0.011, -0.012, -0.012, -0.013, -0.014, -0.014, -0.015, -0.016, -0.017, -0.017, -0.018, -0.019, -0.02, -0.021, -0.023, -0.027, -0.036, -0.05, -0.067, -0.08, -0.08, -0.064, -0.038, -0.017, -0.006, -0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -0.009, -0.009, -0.01, -0.011, -0.012, -0.012, -0.013, -0.014, -0.014, -0.015, -0.016, -0.017, -0.017, -0.018, -0.019, -0.02, -0.021, -0.023, -0.027, -0.036, -0.05, -0.067, -0.08, -0.08, -0.064, -0.038, -0.017, -0.006, -0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ],
  "vega": [
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.001, 0.003, 0.012, 0.035, 0.068, 0.113, 0.158, 0.192, 0.177, 0.114, 0.051, 0.016, 0.005, 0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.001, 0.003, 0.012, 0.035, 0.068, 0.113, 0.158, 0.192, 0.177, 0.114, 0.051, 0.016, 0.005, 0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ],
  "rho": [
    0.046, 0.05, 0.054, 0.057, 0.061, 0.065, 0.069, 0.073, 0.076, 0.08, 0.084, 0.088, 0.092, 0.096, 0.099, 0.103, 0.107, 0.11, 0.113, 0.114, 0.112, 0.105, 0.092, 0.07, 0.042, 0.019, 0.007, 0.002, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.046, 0.05, 0.054, 0.057, 0.061, 0.065, 0.069, 0.073, 0.076, 0.08, 0.084, 0.088, 0.092, 0.096, 0.099, 0.103, 0.107, 0.11, 0.113, 0.114, 0.112, 0.105, 0.092, 0.07, 0.042, 0.019, 0.007, 0.002, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **underlyingSymbol** `string`

  The underlying ticker symbol for the options chain you wish to lookup.

</TabItem>
<TabItem value="optional" label="Optional">

- **date** `date`

  Use to lookup a historical end of day options chain from a specific trading day. If no date parameter is specified the chain will be the most current chain available during market hours. When the market is closed the chain will be from the previous session. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

</TabItem>

<TabItem value="expiration" label="Expiration Filters">

- **expiration** `date`

  - Limits the option chain to a specific expiration date. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.
  - If omitted the next monthly expiration for real-time quotes or the next monthly expiration relative to the `date` parameter for historical quotes will be returned.
  - Use the keyword `all` to return the complete option chain.

  :::caution
  Combining the `all` parameter with large options chains such as SPX, SPY, QQQ, etc. can cause you to consume your requests very quickly. The full SPX option chain has more than 20,000 contracts. A request is consumed for each contact you request with a price in the option chain.
  :::

- **dte** `number`

  Days to expiry. Limit the option chain to a single expiration date closest to the `dte` provided. Should not be used together with `from` and `to`. Take care before combining with `weekly`, `monthly`, `quarterly`, since that will limit the expirations `dte` can return. If you are using the `date` parameter, dte is relative to the `date` provided.

- **from** `date`

  Limit the option chain to expiration dates after `from` (inclusive). Should be combined with `to` to create a range. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`. If omitted all expirations will be returned.

- **to** `date`

  Limit the option chain to expiration dates before `to` (inclusive). Should be combined with `from` to create a range. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`. If omitted all expirations will be returned.

- **month** `number`

  Limit the option chain to options that expire in a specific month (**1-12**).

- **year** `number`

  Limit the option chain to options that expire in a specific **year**.

- **weekly** `boolean`

  Limit the option chain to weekly expirations by setting weekly to `true`. If set to `false`, no weekly expirations will be returned.

- **monthly** `boolean`

  Limit the option chain to standard monthly expirations by setting monthly to `true`. If set to `false`, no monthly expirations will be returned.

- **quarterly** `boolean`

  Limit the option chain to quarterly expirations by setting quarterly to `true`. If set to `false`, no quarterly expirations will be returned.

:::caution
When combining the `weekly`, `monthly`, and `quarterly` parameters, only identical boolean values will be honored. For example, `weekly=true&monthly=false` will return an error. You must use these parameters to either include or exclude values, but you may not include and exclude at the same time. A valid use would be `monthly=true&quarterly=true` to return both monthly and quarterly expirations.
:::


</TabItem>

<TabItem value="strike" label="Strike Filters">

- **strike** `string`

  - Limit the option chain to options with the specific strike specified. (e.g. `400`)
  - Limit the option chain to a specific set of strikes (e.g. `400,405`)
  - Limit the option chain to an open interval of strikes using a logical expression (e.g. `>400`)
  - Limit the option chain to a closed interval of strikes by specifying both endpoints. (e.g. `400-410`)

- **delta** `number`

  - Limit the option chain to a single strike closest to the `delta` provided. (e.g. `.50`)
  - Limit the option chain to a specific set of deltas (e.g. `.60,.30`)
  - Limit the option chain to an open interval of strikes using a logical expression (e.g. `>.50`)
  - Limit the option chain to a closed interval of strikes by specifying both endpoints. (e.g. `.30-.60`)

  :::tip
  Filter strikes using the absolute value of the delta. The values used will always return both sides of the chain (e.g. puts & calls). This means you must filter using `side` to exclude puts or calls. Delta cannot be used to filter the side of the chain, only the strikes.
  :::

- **strikeLimit** `number`

  Limit the number of total strikes returned by the option chain. For example, if a complete chain included 30 strikes and the limit was set to 10, the 20 strikes furthest from the money will be excluded from the response.

  :::tip
  If `strikeLimit` is combined with the `range` or `side` parameter, those parameters will be applied first. In the above example, if the range were set to `itm` (in the money) and side set to `call`, all puts and out of the money calls would be first excluded by the range parameter and then strikeLimit will return a maximum of 10 in the money calls that are closest to the money.
  If the `side` parameter has not been used but `range` has been specified, then `strikeLimit` will return the requested number of calls and puts for each side of the chain, but duplicating the number of strikes that are received.
  :::

  - **range** `string`

  Limit the option chain to strikes that are in the money, out of the money, at the money, or include all. If omitted all options will be returned. Valid inputs: `itm`, `otm`, `all`.

</TabItem>

<TabItem value="liquidity" label="Price/Liquidity Filters">

- **minBid** `number`

  Limit the option chain to options with a bid price greater than or equal to the `number` provided.

- **maxBid** `number`

  Limit the option chain to options with a bid price less than or equal to the `number` provided.

- **minAsk** `number`

  Limit the option chain to options with an ask price greater than or equal to the `number` provided.

- **maxAsk** `number`

  Limit the option chain to options with an ask price less than or equal to the `number` provided.

- **maxBidAskSpread** `number`

  Limit the option chain to options with a bid-ask spread less than or equal to the `number` provided.

- **maxBidAskSpreadPct** `number`

  Limit the option chain to options with a bid-ask spread less than or equal to the `percent` provided (relative to the underlying). For example, a value of `0.5%` would exclude all options trading with a bid-ask spread greater than $1.00 in an underlying that trades at $200.

- **minOpenInterest** `number`

  Limit the option chain to options with an open interest greater than or equal to the `number` provided.

- **minVolume** `number`

  Limit the option chain to options with a volume transacted greater than or equal to the `number` provided.

</TabItem>

<TabItem value="otherfilters" label="Other Filters">

- **nonstandard** `boolean`

  Include non-standard contracts by setting `nonstandard` to `true`. If set to `false`, no non-standard options expirations will be returned. If no parameter is provided, the output will default to false.

- **side** `string`

  Limit the option chain to either `call` or `put`. If omitted, both sides will be returned.

- **am** `boolean`

  Limit the option chain to A.M. expirations by setting `am` to `true`. If set to `false`, no A.M. expirations will be returned. This parameter is only applicable for index options such as SPX, NDX, etc. If no parameter is provided, both A.M. and P.M. expirations will be returned.

- **pm** `boolean`

  Limit the option chain to P.M. expirations by setting `pm` to `true`. If set to `false`, no P.M. expirations will be returned. This parameter is only applicable for index options such as SPX, NDX, etc. If no parameter is provided, both A.M. and P.M. expirations will be returned.

:::caution
The `am` and `pm` parameters are only applicable for index options such as SPX, NDX, etc. If they are used for stocks or ETFs, a bad parameters error will be returned.
:::

</TabItem>

</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Status will always be `ok` when there is the quote requested.

- **optionSymbol** `array[string]`

  The option symbol according to OCC symbology.

- **underlying** `array[string]`

  The ticker symbol of the underlying security.

- **expiration** `array[number]`

  The option's expiration date in Unix time.

- **side** `array[string]`

  The response will be `call` or `put`.

- **strike** `array[number]`

  The exercise price of the option.

- **firstTraded** `array[date]`

  The date the option was first traded.

- **dte** `array[number]`

  The number of days until the option expires.

- **ask** `array[number]`

  The ask price.

- **askSize** `array[number]`

  The number of contracts offered at the ask price.

- **bid** `array[number]`

  The bid price.

- **bidSize** `array[number]`

  The number of contracts offered at the bid price.

- **mid** `array[number]`

  The midpoint price between the ask and the bid, also known as the mark price.

- **last** `array[number]`

  The last price negotiated for this option contract at the time of this quote.

- **volume** `array[number]`

  The number of contracts negotiated during the trading day at the time of this quote.

- **openInterest** `array[number]`

  The total number of contracts that have not yet been settled at the time of this quote.

- **underlyingPrice** `array[number]`

  The last price of the underlying security at the time of this quote.

- **inTheMoney** `array[booleans]`

  Specifies whether the option contract was in the money true or false at the time of this quote.

- **intrinsicValue** `array[number]`

  The intrinsic value of the option.

- **extrinsicValue** `array[number]`

  The extrinsic value of the option.

- **updated** `array[number]`

  The date and time of this quote snapshot in Unix time.

- **iv** `array[number]`

  The [implied volatility](https://www.investopedia.com/terms/i/iv.asp) of the option.

- **delta** `array[number]`

  The [delta](https://www.investopedia.com/terms/d/delta.asp) of the option.

- **gamma** `array[number]`

  The [gamma](https://www.investopedia.com/terms/g/gamma.asp) of the option.

- **theta** `array[number]`

  The [theta](https://www.investopedia.com/terms/t/theta.asp) of the option.

- **vega** `array[number]`

  The [vega](https://www.investopedia.com/terms/v/vega.asp) of the option.

- **rho** `array[number]`

  The [rho](https://www.investopedia.com/terms/r/rho.asp) of the option.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no candles are found for the request.

- **nextTime** `number` optional

  Unix time of the next quote if there is no data in the requested period, but there is data in a subsequent period.

- **prevTime** `number` optional

  Unix time of the previous quote if there is no data in the requested period, but there is data in a previous period.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>

## Option Chain Endpoint Pricing

The cost of using the option chain API endpoint depends on the type of data feed you choose and your usage pattern. Here's a breakdown of the pricing:

| Data Feed Type     | Cost Basis                | Credits Required per Unit |
|--------------------|---------------------------|---------------------------|
| Real-Time Feed     | Per option symbol         | 1 credit                  |
| Cached Feed        | Per API call              | 1 credit                  |

### Examples

1. **Real-Time Feed Usage**
   - If you query all strikes and all expirations for SPX (which has 22,718 total option contracts) using the Real-Time Feed, it will cost you 22,718 credits.

2. **Cached Feed Usage**
   - A single API call to SPX using the Cached Feed, regardless of the number of option symbols queried, will cost you 1 credit.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\compact\expirations.mdx

---
title: Expirations
sidebar_position: 1
---

Get a list of current or historical option expiration dates for an underlying symbol. If no optional parameters are used, the endpoint returns all expiration dates in the option chain.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/options/expirations/{underlyingSymbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/options/expirations/AAPL](https://api.marketdata.app/v1/options/expirations/AAPL)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch("https://api.marketdata.app/v1/options/expirations/AAPL")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/options/expirations/AAPL"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="optionExpirations.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleOptionsExpirationsRequest() {
	expirations, err := OptionsExpirations().UnderlyingSymbol("AAPL").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, expiration := range expirations {
		fmt.Println(expiration)
	}
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "expirations": [
    "2022-09-23",
    "2022-09-30",
    "2022-10-07",
    "2022-10-14",
    "2022-10-21",
    "2022-10-28",
    "2022-11-18",
    "2022-12-16",
    "2023-01-20",
    "2023-02-17",
    "2023-03-17",
    "2023-04-21",
    "2023-06-16",
    "2023-07-21",
    "2023-09-15",
    "2024-01-19",
    "2024-06-21",
    "2025-01-17"
  ],
  "updated": 1663704000
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **underlyingSymbol** `string`

  The underlying ticker symbol for the options chain you wish to lookup.

</TabItem>
<TabItem value="optional" label="Optional">

- **strike** `number`

  Limit the lookup of expiration dates to the strike provided. This will cause the endpoint to only return expiration dates that include this strike.

- **date** `date`

  Use to lookup a historical list of expiration dates from a specific previous trading day. If date is omitted the expiration dates will be from the current trading day during market hours or from the last trading day when the market is closed. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Status will always be `ok` when there is strike
  data for the underlying/expirations requested.

- **expirations** `array[date]`

  The expiration dates requested for the underlying with the option strikes for each expiration.

- **updated** `date`

  The date and time of this list of options strikes was updated in Unix time. For historical strikes, this number should match the `date` parameter.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no data is found for the request.

- **nextTime** `number` optional

  Unix time of the next quote if there is no data in the requested period, but there is data in a subsequent period.

- **prevTime** `number` optional

  Unix time of the previous quote if there is no data in the requested period, but there is data in a previous period.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\compact\lookup.mdx

---
title: Lookup
sidebar_position: 1
---

Generate a properly formatted OCC option symbol based on the user's human-readable description of an option. This endpoint converts text such as "AAPL 7/28/23 $200 Call" to OCC option symbol format: AAPL230728C00200000. The user input must be URL-encoded.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/options/lookup/{userInput}
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/options/lookup/AAPL%207/28/2023%20200%20Call](https://api.marketdata.app/v1/options/lookup/AAPL%207/28/2023%20200%20Call)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch(
  "https://api.marketdata.app/v1/options/lookup/AAPL%207/28/2023%20200%20Call"
)
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/options/lookup/AAPL%207/28/2023%20200%20Call"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="optionLookup.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleOptionLookupRequest() {
	optionSymbol, err := OptionLookup().UserInput("AAPL 7/28/2023 200 Call").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	fmt.Println(optionSymbol)
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "optionSymbol": "AAPL230728C00200000"
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **userInput** `string`

  The human-readable string input that contains (1) stock symbol (2) strike (3) expiration date (4) option side (i.e. put or call). This endpoint will translate the user's input into a valid OCC option symbol.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Status will always be `ok` when the OCC option symbol is successfully generated.

- **optionSymbol** `string`

  The generated OCC option symbol based on the user's input.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>

## Notes

- This endpoint will return an error if the option symbol that would be formed by the user's input does not exist.


# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\compact\quotes.mdx

---
title: Quotes
sidebar_position: 3
---

Get a real-time price quote for a stock.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/stocks/quotes/{symbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/stocks/quotes/AAPL/](https://api.marketdata.app/v1/stocks/quotes/AAPL/)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch("https://api.marketdata.app/v1/stocks/quotes/AAPL/")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/stocks/quotes/AAPL/"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="stockQuote.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleStockQuoteRequest() {
	quotes, err := StockQuote().Symbol("AAPL").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, quote := range quotes {
		fmt.Println(quote)
	}
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "symbol": ["AAPL"],
  "ask": [149.08],
  "askSize": [200],
  "bid": [149.07],
  "bidSize": [600],
  "mid": [149.07],
  "last": [149.09],
  "volume": [66959442],
  "updated": [1663958092]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **symbol** `string`

  The company's ticker symbol.

</TabItem>
<TabItem value="Optional" label="Optional">

- **52week** `boolean`

  Enable the output of 52-week high and 52-week low data in the quote output. By default this parameter is `false` if omitted.

- **extended** `boolean`

  Control the inclusion of extended hours data in the quote output. Defaults to `true` if omitted. 

  - When set to `true`, the most recent quote is always returned, without regard to whether the market is open for primary trading or extended hours trading.
  - When set to `false`, only quotes from the primary trading session are returned. When the market is closed or in extended hours, a historical quote from the last closing bell of the primary trading session is returned instead of an extended hours quote. 

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Will always be `ok` when there is data for the symbol requested.

- **symbol** `array[string]`

  The symbol of the stock.

- **ask** `array[number]`

  The ask price of the stock.

- **askSize** `array[number]`

  The number of shares offered at the ask price.

- **bid** `array[number]`

  The bid price.

- **bidSize** `array[number]`

  The number of shares that may be sold at the bid price.

- **mid** `array[number]`

  The midpoint price between the ask and the bid.

- **last** `array[number]`

  The last price the stock traded at.

- **change** `array[number]`

  The difference in price in currency units compared to the closing price of the previous primary trading session.

- **changepct** `array[number]`

  The difference in price in percent, expressed as a decimal, compared to the closing price of the previous day. For example, a 3% change will be represented as 0.3.

:::note
  - When the market is open for primary trading, **change** and **changepct** are always calculated using the last traded price and the last primary session close. When the market is closed or in extended hours, this criteria is also used as long as `extended` is omitted or set to `true`.
  - When `extended` is set to `false`, and the market is closed or in extended hours, quotes from extended hours are not considered. The values for **change** and **changepct** will be calculated using the last two closing prices instead.
:::

- **52weekHigh** `array[number]`

  The 52-week high for the stock. This parameter is omitted unless the optional 52week request parameter is set to true.

- **52weekLow** `array[number]`

  The 52-week low for the stock. This parameter is omitted unless the optional 52week request parameter is set to true.

- **volume** `array[number]`

  The number of shares traded during the current session.

- **updated** `array[date]`

  The date/time of the current stock quote.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no quote can be found for the symbol.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\compact\strikes.mdx

---
title: Strikes
sidebar_position: 2
---

Get a list of current or historical options strikes for an underlying symbol. If no optional parameters are used, the endpoint returns the strikes for every expiration in the chain.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/options/strikes/{underlyingSymbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/options/strikes/AAPL/?date=2023-01-03&expiration=2023-01-20](https://api.marketdata.app/v1/options/strikes/AAPL/?date=2023-01-03&expiration=2023-01-20)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch(
  "https://api.marketdata.app/v1/options/strikes/AAPL/?date=2023-01-03&expiration=2023-01-20"
)
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/options/strikes/AAPL/?date=2023-01-03&expiration=2023-01-20"

response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="optionStrikes.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleOptionsStrikesRequest() {
	expirations, err := OptionsStrikes().UnderlyingSymbol("AAPL").Date("2023-01-03").Expiration("2023-01-20").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, expiration := range expirations {
		fmt.Println(expiration)
	}
}

```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "updated": 1663704000,
  "2023-01-20": [
    30.0, 35.0, 40.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0,
    95.0, 100.0, 105.0, 110.0, 115.0, 120.0, 125.0, 130.0, 135.0, 140.0, 145.0,
    150.0, 155.0, 160.0, 165.0, 170.0, 175.0, 180.0, 185.0, 190.0, 195.0, 200.0,
    205.0, 210.0, 215.0, 220.0, 225.0, 230.0, 235.0, 240.0, 245.0, 250.0, 260.0,
    270.0, 280.0, 290.0, 300.0
  ]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **underlyingSymbol** `string`

  The underlying ticker symbol for the options chain you wish to lookup.

</TabItem>
<TabItem value="optional" label="Optional">

- **expiration** `date`

  Limit the lookup of strikes to options that expire on a specific expiration date. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

- **date** `date`

  - Use to lookup a historical list of strikes from a specific previous trading day.
  - If date is omitted the expiration dates will be from the current trading day during market hours or from the last trading day when the market is closed.
  - Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Status will always be `ok` when there is strike
  data for the underlying/expirations requested.

- **dates** `array[number]`

  The expiration dates requested for the underlying with the option strikes for each expiration.

- **updated** `array[number]`

  The date and time of this list of options strikes was updated in Unix time. For historical strikes, this number should match the `date` parameter.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no data is found for the request.

- **nextTime** `number` optional

  Unix time of the next quote if there is no data in the requested period, but there is data in a subsequent period.

- **prevTime** `number` optional

  Unix time of the previous quote if there is no data in the requested period, but there is data in a previous period.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\dates-and-times.mdx

---
title: Dates and Times
sidebar_position: 5
---

All Market Data endpoints support advanced date-handling features to allow you to work with dates in a way that works best for your application. Our API will accept date inputs in any of the following formats:

- **American Numeric Notation** Dates and times in MM/DD/YYYY format. For example, closing bell on Dec 30, 2020 for the NYSE would be: 12/30/2020 4:00 PM.

- **Timestamp** An ISO 8601 timestamp in the format YYYY-MM-DD. For example, closing bell on Dec 30, 2020 for the NYSE would be: 2020-12-30 16:00:00.

- **Unix** Dates and times in unix format (seconds after the unix epoch). For example, closing bell on Dec 30, 2020 for the NYSE would be: 1609362000.

- **Spreadsheet** Dates and times in spreadsheet format (days after the Excel epoch). For example, closing bell on Dec 30, 2020 for the NYSE would be: 44195.66667

- **Relative Dates and Times** Keywords or key phrases that indicate specific days, relative to the current date. For example, "today" or "yesterday".

- **Option Expiration Dates** Keyphrase that select specific dates that correspond with dates in the US option expiration calendar.


## Relative Dates and Times

This feature allows you to use natural language to specify dates and times in a way that is easy for humans to read and understand, but can be tricky for machines to parse.

Relative dates allow Market Data endpoints to continually modify the date sent to the endpoint based on the current date. We have a lot of relative date keywords supported already and quite a few more planned for the future, so keep an eye out on this section for continual improvements to this feature.

- **Time-based Parameters** Time keyphrases let you select a specific time of day, relative to the current time. Time-based parameters are typically used to model intraday stock movements.

  - `now` Equivalent to the current time. Use this keyword to select the current open candle, for example.

  - `-[number] minutes` Use negative minutes to specify a time in the past _n_ minutes before. When this is used alone, it is relative to the current time. When used in conjunction in `from` field (i.e. the starting date/time), it is relative to the `to` field (i.e. the ending date/time). For example, if the current time is 10:30 AM, but 10:00 AM is used in the `to` field and `-10 minutes` in the `from` field, then the starting time will be 9:50 AM. The query would return values from 9:50 AM to 10:00 AM. However, if the `to` field were to be omitted, then the same query would return data from 10:20 AM to 10:30 AM since `-10 minutes` would be relative to the current time of 10:30 AM.
  
  - `[number] minutes ago` The `minutes ago` keyword lets you select a relative time, _n_ minutes before the current time. For example, if the time is 10:00 AM then `30 minutes ago` would refer to 9:30 AM of the current day.
 
  - `-[number] hours` Use negative hours to specify a time in the past _n_ hours before. When this is used alone, it is relative to the current time. When used in conjunction in `from` field (i.e. the starting date/time), it is relative to the `to` field (i.e. the ending date/time). For example, if the current time is 10:30 AM, but 10:00 AM is used in the `to` field and `-1 hour` in the `from` field, then the starting time will be 9:00 AM. The query would return values from 9:00 AM to 10:00 AM. However, if the `to` field were to be omitted, then the same query would return data from 9:30 AM to 10:30 AM since `-1 hour` would be relative to the current time of 10:30 AM.
    
  - `[number] hours ago` The `hours ago` keyword lets you select a relative time, _n_ hours before the current time. For example, if the time is 4:00 PM then `4 hours ago` would refer to 12:00 PM of the current day.

- **Daily Parameters** Daily keyphrases let you select a specific day, relative to the current day.

  - `today` Equivalent to today's date.

  - `yesterday` Yesterday's date.
 
  - `-[number] days` Use negative days to specify a time in the past _n_ days before. When this is used alone, it is relative to the current day. When used in conjunction in `from` field (i.e. the starting date), it is relative to the `to` field (i.e. the ending date). For example, if the current date is January 20, but January 10 is used in the `to` field and `-5 days` in the `from` field, then the starting day will be January 5. The query would return values from January 5 to January 10. However, if the `to` field were to be omitted, then the same query would return data from January 15 to January 20 since `-5 days` would be relative to the current date of January 20.

  - `[number] days ago` The `days ago` keyword lets you select a relative day, _n_ days before the current date. For example, if today is January 5, 2024, then using `2 days ago` would select the date January 3, 2024.
 
- **Weekly Parameters** Weekly keyphrases let you select a day of the week in the current, previous, or following week.

  - `-[number] weeks` Use negative weeks to specify a date in the past _n_ weeks before. When this is used alone, it is relative to the current day. When used in conjunction in `from` field (i.e. the starting date), it is relative to the date in the `to` field (i.e. the ending date). For example, if the current date is October 15, 2023 but October 8 is used in the `to` field and `-1 week` in the `from` field, then the starting day will be October 2, 2023. The query would return values from October 2 to October 8. However, if the `to` field were to be omitted, then the same query would return data from October 9 to October 15 since `-5 days` would be relative to the current date of January 20.

  - `[number] weeks ago` The `weeks ago` keyword lets you select a relative week, _n_ weeks before the current date. For example, if today is January 1, 2024, then using `2 weeks ago` would select the date January 3, 2024.

- **Monthly Dates** Monthly keyphrases let you select a specific day of a specific month.

  - `-[number] months` Use negative months to specify a date in the past _n_ months before. When this is used alone, it is relative to the current day. When used in conjunction in `from` field (i.e. the starting date), it is relative to the date in the `to` field (i.e. the ending date). For example, if the current date is October 15 but October 8 is used in the `to` field and `-1 month` in the `from` field, then the starting day will be September 8. The query would return values from September 8 to October 8. However, if the `to` field were to be omitted, then the same query would return data from September 15 to October since `-1 month` would be relative to the current date of October 15.

  - `[number] months ago` The months ago keyword lets you select a relative date, _n_ months before the current date. For example, if today is January 5, 2024, then using `3 months ago` would select the date October 5, 2023.

- **Yearly Dates** Yearly keyphrases let you select a specific day of in the current, previous, or following year.

  - `-[number] years` Use negative years to specify a date in the past _n_ years before. When this is used alone, it is relative to the current day. When used in conjunction in `from` field (i.e. the starting date), it is relative to the date in the `to` field (i.e. the ending date). For example, if the current date is October 15, 2023 but October 8, 2023 is used in the `to` field and `-1 year` in the `from` field, then the starting day will be September 8, 2022. The query would return values from September 8, 2022 to October 8, 2023. However, if the `to` field were to be omitted, then the same query would return data from September 15, 2022 to October 15, 2023 since `-1 year` would be relative to the current date of October 15, 2023.

  - `[number] years ago` The years ago keyword lets you select a relative date, 365 days before the current date. For example, if today is January 5, 2024, then using `2 years ago` would select the date January 5, 2022.

:::caution Coming Soon

The following relative date parameters are planned for the future and have not yet been implemented.

:::

- **Time-based Parameters** Time keyphrases let you select a specific time of day, relative to the current time. Time-based parameters are typically used to model intraday stock movements.

  - `at open`, `opening bell`, `market open` These keyphrases let you select the opening time for the market day. The phase is relative to each exchange's opening time. For example, if you were trading AAPL in the United States, using `at open` would set a time of 9:30 AM ET. 

  - `at close`, `closing bell`, `market close` These keyphrases let you select the closing time for the market day. The phase is relative to each exchange's closing time. For example, if you were trading AAPL in the United States, using `at close` would set a time of 4:00 PM ET.

  - `[number] [minutes|hours] before [open|close]` These before keyword lets you select a relative time before market open or close. For example `30 minutes before close` would select the time 3:30 PM ET if you are trading a stock on a U.S. exchange.

  - `[number] [minutes|hours] after [open|close]` These after keyword lets you select a relative time after market open or close. For example `1 hour after open` would select the time 10:30 AM ET if you are trading a stock on a U.S. exchange.

- **Weekly Parameters** Weekly keyphrases let you select a day of the week in the current, previous, or following week.

  - `this [day of the week]` Works the same way as specifying the day without adding _this_. The day in the _current_ week. For example, if today is Tuesday and the expression is `this Monday`, the date returned would be yesterday. If the expression were `this Wednesday` the date returned would be tomorrow. The word _this_ is optional. If it is omitted, the keyword will still return the date in the current week that corresponds with the day mentioned.

  - `last [day of the week]` The day in the _previous_ week. For example, if today is Tuesday and the expression used is `last Monday`, it would not refer to the Monday that occurred yesterday, but the Monday 8 days prior that occurred in the previous week.

  - `next [day of the week]` The day in the _following_ week. For example, if today is Monday and the expression is `next Tuesday` it would not refer to tomorrow, but the Tuesday that occurs 8 days from now.

- **Monthly Dates** Monthly keyphrases let you select a specific day of a specific month.

  - `[ordinal number] of [the|this] month` - The nth day of the current month. For example, if today is September 10th and the phrase used is, `8th of this month` the date returned would be September 8. The keyphrase `of [the/this] month` is optional. Using a single ordinal number `8th` will also return the 8th of the current month.

  - `[ordinal number] of last month` - The nth day of the current month. For example, if today is December 15th and the phrase used is, `8th of last month` the date returned would be November 8.

  - `ordinal number] of next month` - The nth day of the following month. For example, if today is December 15th and the phrase used is, `8th of next month` the date returned would be January 8 of the following year.

  - `last day of [the|this|last|next] month` - Using the `last day of` keyword will always select the final day of the month. Since months can end on the 28th, 29th, 30th, or 31st, this keyword allows you to always select the final day of a month. For example: `last day of this month`, `last day of next month`. It can also be used to select the last day in February without needing to determine whether the current year is a leap year, `last day of february`.

  - `ordinal number] [day of the week] of [the|this|last|next] month` - Combine ordinal numbers and weekdays to specify a specific day of the week in the current, previous, or following month. For example, ``3nd Friday of last month``.

  - `last [day of the week] of [the|this|last|next] month` - Selects the last day of the week in a month relative to the current month. If the last Monday of the month is needed, instead of using the keyphrase `4th Monday of this month`, it is safer to use `last Monday of this month`, since months can have 4 or 5 Mondays, depending on length. 

  - `last [day of the week] in [month` - Selects the last day of the week in a specific month. For example, Memorial Day could be selected by using the keyphrase `last Monday in May`.

- **Yearly Dates** Yearly keyphrases let you select a specific day of in the current, previous, or following year.

  - `[month] [number]` A specific date in the current year. For example `February 18` would return February 18 of the current year.

  - `[month] [number] [this|last|next] year` A specific date in the current, previous, or following year. For example, if today was Dec 31, 2022, `February 18 next year` would return February 18, 2023.

## Option Expiration Dates

Option expiration dates let you target the expiration dates for option contracts. Dates are based on the US option expirations calendar and are only meant for use with US markets.

:::caution

Option date parameters are planned for the future and have not yet been implemented.

---

Option-related keyphrases cannot be used to return expiration dates far in the future for options which have not yet been traded or for options in the past which have already expired. For example, if today is January 15, 2023, you couldn't use `November 2023's 1st weekly expiration` since weekly options for November would not exist yet. The formula will return a `No data` response if you try to request an expiration that does not exist, whether in the future or the past.

:::

- **Monthly Expirations** - Target a relative month or specific month's option expiration date.

  - `[month] [year] expiration` - The standard monthly option expiration date for [month] during [year]. This is useful for targeting the expiration date for a specific month. Although options normally expire the 3rd Friday, sometimes market holidays can modify this schedule. Using an option expiration keyphrase will ensure that you always obtain the exact date that options expire in a specific month. For example, if today was January 1, 2022, using `December expiration` or `December 2022 expiration` would both return _December 16, 2022_. 

    - [year] is optional. If [month] is used without [year] the lookup is relative to the current date and expired options will not be returned. For example, if today is April 8, 2022, `January expiration` will return January 20, 2023 and not the options which expired in January of 2022.

  - `this|last|next] month's expiration` - Returns the monthly option expiration date for the current, previous, or following month relative to the current month. For example if today is October 5, 2022, and `next month's expiration` is used, the date returned would be _November 18, 2022_.

:::tip

Not all underlying tickers offer weekly or quarterly options. Before building an API request that uses them, ensure that your underlying offers weekly or quarterly option contracts.

:::

- **Weekly Expirations** - Target a relative week or specific week's option expiration date.

  - `[this|last|next] week's expiration` - Returns the weekly option expiration date for the current, previous, or following week relative to the current week. For example if today is October 5, 2022, and `next week's expiration` is used, the date returned would be _October 14, 2022_.

  - `expiration in [number] weeks` - Returns closest expiration that will occur [number] weeks from today without taking into account the current week. For example, if today is August 1, 2022 the phrase `expiration in 6 weeks` would return September 16, 2022.

  - `[month] [year] [ordinal number] weekly expiration` - Returns the nth option expiration date for [month] during [year]. When both a month and year are combined, this can be used to lookup a weekly option date for an expired or unexpired option. For example, `March 2020's 2nd expiration` would return _March 14, 2020_.

- **Quarterly Expirations** - Returns a quarterly expiration date for a relative date or specifically targeted date.

  - `[ordinal number] quarter's expiration` - Returns the quarterly option expiration date for the 1st, 2nd, 3rd, or 4th quarter in the current financial year. For example if today is March 1, 2022, and `4th quarter's expiration` is used, the date returned would be _December 30, 2022_. This will lookup both expired and unexpired options.

  - `[this|last|next] quarter's expiration` - Returns the quarterly option expiration date for the current, previous, or following quarter relative to the current date. For example if today is March 1, 2026, and `this quarter's expiration` is used, the date returned would be _March 31, 2026_.

  - `[expiration in [number] quarters` - Returns closest quarterly expiration that will occur [number] quarters from today without taking into account the current quarter. For example, if today is March 1, 2022 the phrase `expiration in 2 quarters` would return September 30, 2022.

  - `[year] [ordinal number] quarter expiration` - Returns the option expiration date for [nth] quarter during [year]. For example, `2020's 2nd quarter expiration` would return _June 30, 2020_.

- **Specific Contract Expirations** - Target a specific date based on when a contract is first traded or when it expires.

  - `at expiration` - Returns the expiration date for the option contract. This must be used in the context of a specific option contract. For example, if you used at expiration with AAPL230120C00150000, the date returned would be January 20, 2023.

  - `first traded` - Returns the date when the contract was traded for the first time. This must be used in the context of a specific option contract. For example, if you used first traded with AAPL230120C00150000, the date returned would be September 14, 2020.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\funds\candles.mdx

---
title: Candles tg n
sidebar_position: 1
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

Get historical price candles for a mutual fund.

:::warning
This endpoint will be live on May 1, 2024. Before May 1, use the stocks/candles endpoint to query mutual fund candles.
:::

## Endpoint
```
https://api.marketdata.app/v1/funds/candles/{resolution}/{symbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/funds/candles/D/VFINX?from=2020-01-01&to=2020-01-10](https://api.marketdata.app/v1/funds/candles/D/VFINX?from=2020-01-01&to=2020-01-10)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="fundCandles.js"
fetch(
  "https://api.marketdata.app/v1/funds/candles/D/VFINX?from=2020-01-01&to=2020-01-10"
)
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });

```

</TabItem>
<TabItem value="Python" label="Python">

```python title="fundCandles.py"
import requests

url = "https://api.marketdata.app/v1/funds/candles/D/VFINX?from=2020-01-01&to=2020-01-10"

response = requests.request("GET", url)

print(response.text)
```
</TabItem>
<TabItem value="Go" label="Go">

```go title="fundCandles.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleFundCandlesRequest() {
  fcr, err := FundCandles().Resolution("D").Symbol("VFINX").From("2023-01-01").To("2023-01-06").Get()
  if err != nil {
    fmt.Print(err)
    return
  }

  for _, candle := range fcr {
    fmt.Println(candle)
  }
}

```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s":"ok",
  "t":[1577941200,1578027600,1578286800,1578373200,1578459600,1578546000,1578632400],
  "o":[300.69,298.6,299.65,298.84,300.32,302.39,301.53],
  "h":[300.69,298.6,299.65,298.84,300.32,302.39,301.53],
  "l":[300.69,298.6,299.65,298.84,300.32,302.39,301.53],
  "c":[300.69,298.6,299.65,298.84,300.32,302.39,301.53]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **resolution** `string`

  The duration of each candle.

  - Daily Resolutions: (`daily`, `D`, `1D`, `2D`, ...)
  - Weekly Resolutions: (`weekly`, `W`, `1W`, `2W`, ...)
  - Monthly Resolutions: (`monthly`, `M`, `1M`, `2M`, ...)
  - Yearly Resolutions:(`yearly`, `Y`, `1Y`, `2Y`, ...)

- **symbol** `string`

  The mutual fund's ticker symbol.

- **from** `date`

  The leftmost candle on a chart (inclusive). If you use `countback`, `to` is not required. Accepted timestamp inputs: ISO 8601, unix, spreadsheet.

- **to** `date`

  The rightmost candle on a chart (inclusive). Accepted timestamp inputs: ISO 8601, unix, spreadsheet.

- **countback** `number`

  Will fetch a number of candles before (to the left of) `to`. If you use `from`, `countback` is not required.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  ll always be `ok` when there is data for the candles requested.

- **o** `array[number]`

  Open price.

- **h** `array[number]`

  High price.

- **l** `array[number]`

  Low price.

- **c** `array[number]`

  Close price.

- **t** `array[number]`

  Candle time (Unix timestamp, Eastern Time Zone). Daily, weekly, monthly, yearly candles are returned without times.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no candles are found for the request.

- **nextTime** `number` optional

  Unix time of the next quote if there is no data in the requested period, but there is data in a subsequent period.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>




# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\funds\index.mdx

---
title: Mutual Funds
slug: /funds
sidebar_position: 9
---

The mutual funds endpoints offer access to historical pricing data for mutual funds.

## Root Endpoint For Mutual Funds
```
https://api.marketdata.app/v1/funds/
```

## Funds Endpoints

import DocCardList from "@theme/DocCardList";
import { useCurrentSidebarCategory } from "@docusaurus/theme-common";

<DocCardList items={useCurrentSidebarCategory().items} />



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\indices\candles.mdx

---
title: Candles
sidebar_position: 1
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

Get historical price candles for an index.

## Endpoint
```
https://api.marketdata.app/v1/indices/candles/{resolution}/{symbol}/
```
#### Method
```
GET
```

## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/indices/candles/D/VIX?from=2022-09-01&to=2022-09-05](https://api.marketdata.app/v1/indices/candles/D/VIX?from=2022-09-01&to=2022-09-05)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch(
  "https://api.marketdata.app/v1/indices/candles/D/VIX?from=2022-09-01&to=2022-09-05"
)
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/indices/candles/D/VIX?from=2022-09-01&to=2022-09-05"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="indexCandles.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleIndicesCandlesRequest_get() {
	vix, err := IndexCandles().Symbol("VIX").Resolution("D").From("2022-09-01").To("2022-09-05").Get()
	if err != nil {
		fmt.Println("Error retrieving VIX index candles:", err.Error())
		return
	}

	for _, candle := range vix {
		fmt.Println(candle)
	}
}
```

</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "c": [22.84, 23.93, 21.95, 21.44, 21.15],
  "h": [23.27, 24.68, 23.92, 22.66, 22.58],
  "l": [22.26, 22.67, 21.68, 21.44, 20.76],
  "o": [22.41, 24.08, 23.86, 22.06, 21.5],
  "t": [1659326400, 1659412800, 1659499200, 1659585600, 1659672000]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **resolution** `string`

  The duration of each candle.

  Minutely Resolutions: (`minutely`, `1`, `3`, `5`, `15`, `30`, `45`, ...)
  Hourly Resolutions: (`hourly`, `H`, `1H`, `2H`, ...)
  Daily Resolutions: (`daily`, `D`, `1D`, `2D`, ...)
  Weekly Resolutions: (`weekly`, `W`, `1W`, `2W`, ...)
  Monthly Resolutions: (`monthly`, `M`, `1M`, `2M`, ...)
  Yearly Resolutions:(`yearly`, `Y`, `1Y`, `2Y`, ...)

- **symbol** `string`

  The index symbol, without any leading or trailing index identifiers. For example, use DJI do not use $DJI, ^DJI, .DJI, DJI.X, etc.

</TabItem>
<TabItem value="date" label="Dates">

All `date` parameters are optional. By default the most recent candle is returned if no date parameters are provided.

- **from** `date`

  The leftmost candle on a chart (inclusive). From and countback are mutually exclusive. If you use `countback`, `from` must be omitted. Accepted timestamp inputs: ISO 8601, unix, spreadsheet. 

- **to** `date`

  The rightmost candle on a chart (inclusive). Accepted timestamp inputs: ISO 8601, unix, spreadsheet.

- **countback** `number`

  Will fetch a specific number of candles before (to the left of) `to`. From and countback are mutually exclusive. If you use `from`, `countback` must be omitted.

:::note
There is no maximum date range limit on daily candles. When requesting intraday candles of any resolution, no more than 1 year of data can be requested in a single request.
:::

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Will always be `ok` when there is data for the candles requested.

- **o** `array[number]`

  Open price.

- **h** `array[number]`

  High price.

- **l** `array[number]`

  Low price.

- **c** `array[number]`

  Close price.

- **t** `array[number]`

  Candle time (Unix timestamp, UTC). Daily, weekly, monthly, yearly candles are returned without times.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no candles are found for the request.

- **nextTime** `number` optional

  Unix time of the next quote if there is no data in the requested period, but there is data in a subsequent period.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`

  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\indices\index.mdx

---
title: Indices
slug: /indices
sidebar_position: 8
---

The index endpoints provided by the Market Data API offer access to both real-time and historical data related to financial indices. These endpoints are designed to cater to a wide range of financial data needs.

## Root Endpoint For Indices
```
https://api.marketdata.app/v1/indices/
```

## Indices Endpoints

import DocCardList from "@theme/DocCardList";
import { useCurrentSidebarCategory } from "@docusaurus/theme-common";

<DocCardList items={useCurrentSidebarCategory().items} />



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\indices\quotes.mdx

---
title: Quotes
sidebar_position: 2
---

Get a real-time quote for an index.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/indices/quotes/{symbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/indices/quotes/VIX/](https://api.marketdata.app/v1/indices/quotes/VIX/)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch("https://api.marketdata.app/v1/indices/quotes/VIX/")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/indices/quotes/VIX/"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="indexQuote.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleIndexQuoteRequest() {
	vix, err := IndexQuotes().Symbol("VIX").Get()
	if err != nil {
    fmt.Println("Error retrieving VIX index candles:", err)
		return
	}

	for _, quote := range vix {
		fmt.Println(quote)
	}
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "symbol": ["VIX"],
  "last": [29.92],
  "updated": [1664224409]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **symbol** `string`

  The index symbol, without any leading or trailing index identifiers. For example, use DJI do not use $DJI, ^DJI, .DJI, DJI.X, etc.

</TabItem>
<TabItem value="Optional" label="Optional">

- **52week** `boolean`

  Enable the output of 52-week high and 52-week low data in the quote output. By default this parameter is `false` if omitted.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Will always be `ok` when there is data for the symbol requested.

- **symbol** `array[string]`

  The symbol of the index.

- **last** `array[number]`

  The last price of the index.

- **change** `array[number]`

  The difference in price in dollars (or the index's native currency if different from dollars) compared to the closing price of the previous day.

- **changepct** `array[number]`

The difference in price in percent, expressed as a decimal, compared to the closing price of the previous day. For example, a 30% change will be represented as 0.30.

- **52weekHigh** `array[number]`

  The 52-week high for the index.

- **52weekLow** `array[number]`

  The 52-week low for the index.

- **updated** `array[date]`

  The date/time of the quote.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no quote can be found for the symbol.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\intro.md

---
title: Introduction
sidebar_position: 1
slug: /
---

The Market Data API is designed around REST and supports standard HTTP response codes and methods. All responses are delivered via JSON for programmatic use of the information or via CSV files to load into your preferred spreadsheet application.

:::info Root Endpoint
https://api.marketdata.app/
:::

## Try Our API

The easiest way to try out our API is using our [Swagger User Interface](https://api.marketdata.app/), which will allow you to try out your API requests directly from your browser.

:::tip
Our endpoints have **lots of optional parameters** to allow users to sort and filter responses. It can be overwhelming to new users at first. When you're first getting started testing our API in Swagger, scroll to the required parameters and ignore all the optional ones. Most endpoints require only a ticker symbol as a required parameter.
:::

<iframe width="560" height="315" src="https://www.youtube.com/embed/tOIZi7s6nqQ?si=sFxMcDQGsfnQHhhb" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>

#### Get Started Quick — No Registration Required!

You can try stock, option, index, and mutual fund endpoints with several different symbols that are unlocked and require no authorization token. That means these symbols can be used throughout our API with no registration required!

- Stock endpoints: Use **AAPL**.
- Options endpoints: Use any AAPL contract, for example: **AAPL250117C00150000**.
- Index endpoints: Use **VIX**.
- Mutual fund endpoints: Use **VFINX**.

Once you would like to experiment with other symbols, [register a free account](https://www.marketdata.app/signup/) (no credit card required) and you be able to choose a free trial. After your trial ends, if you decide not to subscribe, you will still get 100 free requests per day. Make the decision to pay only after making a complete trial of our API.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\markets\index.mdx

---
title: Markets
slug: /markets
sidebar_position: 5
---

The Markets endpoints provide reference and status data about the markets covered by Market Data.

## Root Endpoint For Markets
```
https://api.marketdata.app/v1/markets/
```
## Markets Endpoints

import DocCardList from "@theme/DocCardList";
import { useCurrentSidebarCategory } from "@docusaurus/theme-common";

<DocCardList items={useCurrentSidebarCategory().items} />



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\markets\status.mdx

---
title: Status
sidebar_position: 1
---

Get the past, present, or future status for a stock market. The endpoint will respond with "open" for trading days or "closed" for weekends or market holidays.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/markets/status/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/markets/status/?from=2020-01-01&to=2020-12-31](https://api.marketdata.app/v1/markets/status/?from=2020-01-01&to=2020-12-31)

**GET** [https://api.marketdata.app/v1/markets/status/?date=yesterday](https://api.marketdata.app/v1/markets/status/?date=yesterday)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch(
  "https://api.marketdata.app/v1/markets/status/?from=2020-01-01&to=2020-12-31"
)
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });

fetch("https://api.marketdata.app/v1/markets/status/?date=yesterday")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url1 = "https://api.marketdata.app/v1/markets/status/?from=2020-01-01&to=2020-12-31"
url2 = "https://api.marketdata.app/v1/markets/status/?date=yesterday"

response1 = requests.request("GET", url1)
response2 = requests.request("GET", url2)

print(response1.text)
print(response2.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="marketstatus.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleMarketStatus() {
	msr, err := api.MarketStatus().From("2020-01-01").To("2020-12-31").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, report := range msr {
		fmt.Println(report)
	}
}

func ExampleMarketStatus_relativeDates() {
	msr, err := api.MarketStatus().Date("yesterday").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, report := range msr {
		fmt.Println(report)
	}
}
```

</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "date": [1680580800],
  "status": ["open"]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required">

- There are no required parameters for `status`. If no parameter is given, the request will return the market status in the United States for the current day.

</TabItem>
<TabItem value="optional" label="Optional" default>

- **country** `string`

  Use to specify the country. Use the two digit ISO 3166 country code. If no country is specified, `US` will be assumed. Only countries that Market Data supports for stock price data are available (currently only the United States).

- **date** `date`

  Consult whether the market was open or closed on the specified date. Accepted timestamp inputs: ISO 8601, unix, spreadsheet, relative date strings.

- **from** `date`

  The earliest date (inclusive). If you use countback, from is not required. Accepted timestamp inputs: ISO 8601, unix, spreadsheet, relative date strings.

- **to** `date`

  The last date (inclusive). Accepted timestamp inputs: ISO 8601, unix, spreadsheet, relative date strings.

- **countback** `number`

  Countback will fetch a number of dates before `to` If you use from, countback is not required.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  ll always be `ok` when there is data for the dates requested.

- **date** `array[dates]`

  The date.

- **status** `array[string]`

  The market status. This will always be `open` or `closed` or `null`. Half days or partial trading days are reported as `open`. Requests for days further in the past or further in the future than our data will be returned as `null`.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no data is found for the request.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\options\chain.mdx

---
title: Option Chain
sidebar_position: 3
---

Get a current or historical end of day options chain for an underlying ticker symbol. Optional parameters allow for extensive filtering of the chain. Use the optionSymbol returned from this endpoint to get quotes, greeks, or other information using the other endpoints.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/options/chain/{underlyingSymbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/options/chain/AAPL/?expiration=2025-01-17&side=call](https://api.marketdata.app/v1/options/chain/AAPL/?expiration=2025-01-17&side=call)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch("https://api.marketdata.app/v1/options/chain/AAPL/")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/options/chain/AAPL/"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="optionChain.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleOptionChainRequest() {
	AAPL, err := OptionChain().UnderlyingSymbol("AAPL").Get()
	if err != nil {
		fmt.Println("Error fetching option chain:", err)
		return
	}
	for _, contract := range AAPL {
		fmt.Println(contract)
	}
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "optionSymbol": [
    "AAPL230616C00060000", "AAPL230616C00065000", "AAPL230616C00070000", "AAPL230616C00075000", "AAPL230616C00080000", "AAPL230616C00085000", "AAPL230616C00090000", "AAPL230616C00095000", "AAPL230616C00100000", "AAPL230616C00105000", "AAPL230616C00110000", "AAPL230616C00115000", "AAPL230616C00120000", "AAPL230616C00125000", "AAPL230616C00130000", "AAPL230616C00135000", "AAPL230616C00140000", "AAPL230616C00145000", "AAPL230616C00150000", "AAPL230616C00155000", "AAPL230616C00160000", "AAPL230616C00165000", "AAPL230616C00170000", "AAPL230616C00175000", "AAPL230616C00180000", "AAPL230616C00185000", "AAPL230616C00190000", "AAPL230616C00195000", "AAPL230616C00200000", "AAPL230616C00205000", "AAPL230616C00210000", "AAPL230616C00215000", "AAPL230616C00220000", "AAPL230616C00225000", "AAPL230616C00230000", "AAPL230616C00235000", "AAPL230616C00240000", "AAPL230616C00245000", "AAPL230616C00250000", "AAPL230616C00255000", "AAPL230616C00260000", "AAPL230616C00265000", "AAPL230616C00270000", "AAPL230616C00280000", "AAPL230616C00290000", "AAPL230616C00300000", "AAPL230616P00060000", "AAPL230616P00065000", "AAPL230616P00070000", "AAPL230616P00075000", "AAPL230616P00080000", "AAPL230616P00085000", "AAPL230616P00090000", "AAPL230616P00095000", "AAPL230616P00100000", "AAPL230616P00105000", "AAPL230616P00110000", "AAPL230616P00115000", "AAPL230616P00120000", "AAPL230616P00125000", "AAPL230616P00130000", "AAPL230616P00135000", "AAPL230616P00140000", "AAPL230616P00145000", "AAPL230616P00150000", "AAPL230616P00155000", "AAPL230616P00160000", "AAPL230616P00165000", "AAPL230616P00170000", "AAPL230616P00175000", "AAPL230616P00180000", "AAPL230616P00185000", "AAPL230616P00190000", "AAPL230616P00195000", "AAPL230616P00200000", "AAPL230616P00205000", "AAPL230616P00210000", "AAPL230616P00215000", "AAPL230616P00220000", "AAPL230616P00225000", "AAPL230616P00230000", "AAPL230616P00235000", "AAPL230616P00240000", "AAPL230616P00245000", "AAPL230616P00250000", "AAPL230616P00255000", "AAPL230616P00260000", "AAPL230616P00265000", "AAPL230616P00270000", "AAPL230616P00280000", "AAPL230616P00290000", "AAPL230616P00300000"
  ],
  "underlying": [
    "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL", "AAPL"
  ],
  "expiration": [
    1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600, 1686945600
  ],
  "side": [
    "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "call", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put", "put"
  ],
  "strike": [
    60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160, 165, 170, 175, 180, 185, 190, 195, 200, 205, 210, 215, 220, 225, 230, 235, 240, 245, 250, 255, 260, 265, 270, 280, 290, 300, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160, 165, 170, 175, 180, 185, 190, 195, 200, 205, 210, 215, 220, 225, 230, 235, 240, 245, 250, 255, 260, 265, 270, 280, 290, 300
  ],
  "firstTraded": [
    1617197400, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616506200, 1616506200, 1616506200, 1616506200, 1616506200, 1616506200, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1617370200, 1617888600, 1618234200, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1626701400, 1626701400, 1626701400, 1626701400, 1617197400, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616506200, 1616506200, 1616506200, 1616506200, 1616506200, 1616506200, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1616592600, 1617370200, 1617888600, 1618234200, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1619184600, 1682083800, 1626701400, 1626701400, 1626701400, 1626701400
  ],
  "dte": [
    26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26
  ],
  "updated": [
    1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875, 1684702875
  ],
  "bid": [
    114.1, 108.6, 103.65, 98.6, 93.6, 88.9, 84.3, 80.2, 74.75, 70, 64.35, 59.4, 54.55, 50, 45.1, 40.45, 35.75, 30.8, 25.7, 20.6, 15.9, 11.65, 7.55, 4.15, 1.77, 0.57, 0.18, 0.07, 0.03, 0.02, 0.02, 0.01, 0.01, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.01, 0.01, 0.02, 0.02, 0.03, 0.04, 0.06, 0.07, 0.11, 0.14, 0.22, 0.32, 0.52, 0.92, 1.74, 3.3, 5.9, 9.8, 14.7, 19.3, 24.25, 28.7, 32.95, 38.65, 44.7, 48.4, 53.05, 58.8, 63.55, 68.05, 73.2, 78.5, 84.1, 88.05, 92.9, 103.15, 113.4, 123.05
  ],
  "bidSize": [
    90, 90, 90, 90, 90, 90, 90, 98, 90, 102, 90, 90, 90, 90, 102, 90, 95, 95, 99, 258, 118, 202, 96, 38, 36, 30, 180, 310, 31, 319, 5, 822, 216, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 14, 64, 10, 163, 2, 5, 79, 31, 4, 1, 208, 30, 146, 5, 35, 1, 5, 6, 98, 90, 90, 90, 90, 90, 98, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90
  ],
  "mid": [
    115.5, 110.38, 105.53, 100.5, 95.53, 90.28, 85.53, 80.68, 75.58, 70.75, 65.55, 60.67, 55.55, 50.9, 45.88, 40.7, 35.88, 30.93, 26.3, 20.93, 16.18, 11.78, 7.62, 4.2, 1.79, 0.58, 0.18, 0.08, 0.04, 0.03, 0.03, 0.01, 0.02, 0.09, 0.05, 0.09, 0.01, 0.08, 0.01, 0.08, 0.03, 0.23, 0.26, 0.51, 0.01, 0.01, 0.01, 0.01, 0.01, 0.03, 0.01, 0.08, 0.08, 0.01, 0.01, 0.01, 0.03, 0.07, 0.07, 0.04, 0.07, 0.08, 0.11, 0.16, 0.23, 0.33, 0.53, 0.94, 1.76, 3.33, 5.97, 10.2, 14.95, 20.52, 24.95, 30, 34.83, 39.88, 45, 49.83, 54.85, 59.85, 64.82, 69.75, 74.78, 80.12, 85.4, 89.9, 94.8, 104.95, 114.68, 124.82
  ],
  "ask": [
    116.9, 112.15, 107.4, 102.4, 97.45, 91.65, 86.75, 81.15, 76.4, 71.5, 66.75, 61.95, 56.55, 51.8, 46.65, 40.95, 36, 31.05, 26.9, 21.25, 16.45, 11.9, 7.7, 4.25, 1.81, 0.6, 0.19, 0.08, 0.05, 0.04, 0.03, 0.02, 0.03, 0.17, 0.1, 0.17, 0.01, 0.16, 0.02, 0.16, 0.05, 0.46, 0.51, 1.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.05, 0.02, 0.16, 0.16, 0.01, 0.02, 0.02, 0.04, 0.12, 0.1, 0.05, 0.07, 0.09, 0.12, 0.18, 0.23, 0.34, 0.54, 0.95, 1.78, 3.35, 6.05, 10.6, 15.2, 21.75, 25.65, 31.3, 36.7, 41.1, 45.3, 51.25, 56.65, 60.9, 66.1, 71.45, 76.35, 81.75, 86.7, 91.75, 96.7, 106.75, 115.95, 126.6
  ],
  "askSize": [
    90, 90, 90, 90, 90, 90, 90, 102, 90, 96, 90, 90, 90, 90, 96, 102, 90, 95, 96, 114, 103, 126, 90, 156, 20, 98, 397, 563, 251, 528, 238, 1, 30, 117, 99, 173, 89, 151, 196, 90, 92, 90, 90, 248, 1, 340, 180, 75, 50, 156, 1, 174, 231, 50, 500, 48, 2, 222, 136, 229, 587, 411, 226, 1, 128, 105, 142, 188, 34, 61, 45, 120, 105, 109, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90, 90
  ],
  "last": [
    115, 107.82, 105.75, 100.45, 94.2, 90.66, 86, 81, 75.59, 71.08, 66.07, 61.64, 55.8, 50.77, 46.12, 41.05, 35.9, 30.81, 25.95, 21.3, 16.33, 11.8, 7.6, 4.2, 1.78, 0.59, 0.18, 0.08, 0.05, 0.02, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, null, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.02, 0.02, 0.02, 0.02, 0.04, 0.05, 0.06, 0.08, 0.11, 0.16, 0.23, 0.33, 0.52, 0.93, 1.76, 3.27, 6, 10.1, 14.84, 20.74, 25.39, 30.65, 37.1, null, 44.8, 59.6, 55.35, null, 83.49, null, 101.5, null, 109.39, null, 120.55, 128.67, 139.85, 151.1
  ],
  "openInterest": [
    21957, 3012, 2796, 1994, 1146, 558, 2598, 988, 6574, 509, 1780, 917, 2277, 1972, 10751, 6080, 35508, 17559, 33003, 32560, 49905, 75976, 56201, 62509, 59821, 39370, 24498, 51472, 17565, 921, 13428, 273, 6935, 518, 4496, 533, 8128, 10, 14615, 100, 6765, 0, 2481, 3831, 2474, 17228, 57338, 9503, 13614, 8027, 7938, 3752, 21276, 13550, 46981, 14401, 26134, 40858, 34215, 33103, 92978, 47546, 67687, 35527, 87587, 51117, 72338, 82643, 43125, 12822, 2955, 619, 112, 2, 44, 3, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ],
  "volume": [
    0, 0, 1, 4, 0, 8, 1, 43, 15, 49, 10, 5, 6, 5, 58, 72, 31, 427, 207, 104, 380, 1070, 3179, 7619, 10678, 5488, 1267, 718, 420, 73, 18, 1, 137, 348, 844, 27, 6, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0, 0, 0, 5, 0, 0, 0, 50, 23, 36, 32, 250, 142, 155, 135, 1969, 1068, 2005, 3018, 2641, 7861, 13154, 6299, 6389, 664, 101, 12, 0, 0, 0, 0, 0, 100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ],
  "inTheMoney": [
    true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, false, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true
  ],
  "intrinsicValue": [
    115.13, 110.13, 105.13, 100.13, 95.13, 90.13, 85.13, 80.13, 75.13, 70.13, 65.13, 60.13, 55.13, 50.13, 45.13, 40.13, 35.13, 30.13, 25.13, 20.13, 15.13, 10.13, 5.13, 0.13, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4.87, 9.87, 14.87, 19.87, 24.87, 29.87, 34.87, 39.87, 44.87, 49.87, 54.87, 59.87, 64.87, 69.87, 74.87, 79.87, 84.87, 89.87, 94.87, 104.87, 114.87, 124.87
  ],
  "extrinsicValue": [
    0.37, 0.25, 0.4, 0.37, 0.4, 0.15, 0.4, 0.55, 0.45, 0.62, 0.42, 0.55, 0.42, 0.77, 0.75, 0.57, 0.75, 0.8, 1.17, 0.8, 1.05, 1.65, 2.5, 4.07, 1.79, 0.58, 0.18, 0.08, 0.04, 0.03, 0.03, 0.01, 0.02, 0.09, 0.05, 0.09, 0.01, 0.08, 0.01, 0.08, 0.03, 0.23, 0.26, 0.51, 0.01, 0.01, 0.01, 0.01, 0.01, 0.03, 0.01, 0.08, 0.08, 0.01, 0.01, 0.01, 0.03, 0.07, 0.07, 0.04, 0.07, 0.08, 0.11, 0.16, 0.23, 0.33, 0.53, 0.94, 1.76, 3.33, 1.1, 0.33, 0.08, 0.65, 0.08, 0.13, 0.05, 0, 0.13, 0.05, 0.02, 0.02, 0.05, 0.12, 0.09, 0.25, 0.53, 0.03, 0.07, 0.08, 0.19, 0.05
  ],
  "underlyingPrice": [
    175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13, 175.13
  ],
  "iv": [
    1.629, 1.923, 1.829, 1.696, 1.176, 1.455, 1.023, 0.978, 0.929, 0.795, 0.757, 0.676, 0.636, 0.592, 0.546, 0.422, 0.393, 0.361, 0.331, 0.282, 0.257, 0.231, 0.21, 0.192, 0.176, 0.167, 0.171, 0.184, 0.2, 0.224, 0.254, 0.268, 0.296, 0.322, 0.347, 0.36, 0.384, 0.407, 0.429, 0.451, 0.472, 0.492, 0.512, 0.551, 0.589, 0.624, 1.268, 1.177, 1.093, 1.014, 0.942, 0.872, 0.807, 0.745, 0.708, 0.651, 0.628, 0.573, 0.539, 0.501, 0.469, 0.431, 0.395, 0.359, 0.325, 0.291, 0.26, 0.233, 0.212, 0.194, 0.177, 0.164, 0.223, 0.274, 0.322, 0.396, 0.432, 0.452, 0.476, 0.53, 0.66, 0.677, 0.661, 0.769, 0.776, 0.73, 0.873, 0.863, 0.974, 1.063, 1.013, 1.092
  ],
  "delta": [
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.998, 0.99, 0.971, 0.927, 0.849, 0.728, 0.549, 0.328, 0.147, 0.052, 0.014, 0.003, 0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -0.002, -0.01, -0.029, -0.073, -0.151, -0.272, -0.451, -0.672, -0.853, -0.948, -0.986, -0.997, -0.999, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1
  ],
  "gamma": [
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.001, 0.002, 0.006, 0.012, 0.021, 0.032, 0.043, 0.042, 0.028, 0.013, 0.004, 0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.001, 0.002, 0.006, 0.012, 0.021, 0.032, 0.043, 0.042, 0.028, 0.013, 0.004, 0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ],
  "theta": [
    -0.009, -0.009, -0.01, -0.011, -0.012, -0.012, -0.013, -0.014, -0.014, -0.015, -0.016, -0.017, -0.017, -0.018, -0.019, -0.02, -0.021, -0.023, -0.027, -0.036, -0.05, -0.067, -0.08, -0.08, -0.064, -0.038, -0.017, -0.006, -0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -0.009, -0.009, -0.01, -0.011, -0.012, -0.012, -0.013, -0.014, -0.014, -0.015, -0.016, -0.017, -0.017, -0.018, -0.019, -0.02, -0.021, -0.023, -0.027, -0.036, -0.05, -0.067, -0.08, -0.08, -0.064, -0.038, -0.017, -0.006, -0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ],
  "vega": [
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.001, 0.003, 0.012, 0.035, 0.068, 0.113, 0.158, 0.192, 0.177, 0.114, 0.051, 0.016, 0.005, 0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.001, 0.003, 0.012, 0.035, 0.068, 0.113, 0.158, 0.192, 0.177, 0.114, 0.051, 0.016, 0.005, 0.001, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ],
  "rho": [
    0.046, 0.05, 0.054, 0.057, 0.061, 0.065, 0.069, 0.073, 0.076, 0.08, 0.084, 0.088, 0.092, 0.096, 0.099, 0.103, 0.107, 0.11, 0.113, 0.114, 0.112, 0.105, 0.092, 0.07, 0.042, 0.019, 0.007, 0.002, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.046, 0.05, 0.054, 0.057, 0.061, 0.065, 0.069, 0.073, 0.076, 0.08, 0.084, 0.088, 0.092, 0.096, 0.099, 0.103, 0.107, 0.11, 0.113, 0.114, 0.112, 0.105, 0.092, 0.07, 0.042, 0.019, 0.007, 0.002, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
  ]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **underlyingSymbol** `string`

  The underlying ticker symbol for the options chain you wish to lookup.

</TabItem>
<TabItem value="optional" label="Optional">

- **date** `date`

  Use to lookup a historical end of day options chain from a specific trading day. If no date parameter is specified the chain will be the most current chain available during market hours. When the market is closed the chain will be from the previous session. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

</TabItem>

<TabItem value="expiration" label="Expiration Filters">

- **expiration** `date`

  - Limits the option chain to a specific expiration date. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.
  - If omitted the next monthly expiration for real-time quotes or the next monthly expiration relative to the `date` parameter for historical quotes will be returned.
  - Use the keyword `all` to return the complete option chain.

  :::caution
  Combining the `all` parameter with large options chains such as SPX, SPY, QQQ, etc. can cause you to consume your requests very quickly. The full SPX option chain has more than 20,000 contracts. A request is consumed for each contact you request with a price in the option chain.
  :::

- **dte** `number`

  Days to expiry. Limit the option chain to a single expiration date closest to the `dte` provided. Should not be used together with `from` and `to`. Take care before combining with `weekly`, `monthly`, `quarterly`, since that will limit the expirations `dte` can return. If you are using the `date` parameter, dte is relative to the `date` provided.

- **from** `date`

  Limit the option chain to expiration dates after `from` (inclusive). Should be combined with `to` to create a range. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`. If omitted all expirations will be returned.

- **to** `date`

  Limit the option chain to expiration dates before `to` (inclusive). Should be combined with `from` to create a range. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`. If omitted all expirations will be returned.

- **month** `number`

  Limit the option chain to options that expire in a specific month (**1-12**).

- **year** `number`

  Limit the option chain to options that expire in a specific **year**.

- **weekly** `boolean`

  Limit the option chain to weekly expirations by setting weekly to `true`. If set to `false`, no weekly expirations will be returned.

- **monthly** `boolean`

  Limit the option chain to standard monthly expirations by setting monthly to `true`. If set to `false`, no monthly expirations will be returned.

- **quarterly** `boolean`

  Limit the option chain to quarterly expirations by setting quarterly to `true`. If set to `false`, no quarterly expirations will be returned.

:::caution
When combining the `weekly`, `monthly`, and `quarterly` parameters, only identical boolean values will be honored. For example, `weekly=true&monthly=false` will return an error. You must use these parameters to either include or exclude values, but you may not include and exclude at the same time. A valid use would be `monthly=true&quarterly=true` to return both monthly and quarterly expirations.
:::


</TabItem>

<TabItem value="strike" label="Strike Filters">

- **strike** `string`

  - Limit the option chain to options with the specific strike specified. (e.g. `400`)
  - Limit the option chain to a specific set of strikes (e.g. `400,405`)
  - Limit the option chain to an open interval of strikes using a logical expression (e.g. `>400`)
  - Limit the option chain to a closed interval of strikes by specifying both endpoints. (e.g. `400-410`)

- **delta** `number`

  - Limit the option chain to a single strike closest to the `delta` provided. (e.g. `.50`)
  - Limit the option chain to a specific set of deltas (e.g. `.60,.30`)
  - Limit the option chain to an open interval of strikes using a logical expression (e.g. `>.50`)
  - Limit the option chain to a closed interval of strikes by specifying both endpoints. (e.g. `.30-.60`)

  :::tip
  Filter strikes using the absolute value of the delta. The values used will always return both sides of the chain (e.g. puts & calls). This means you must filter using `side` to exclude puts or calls. Delta cannot be used to filter the side of the chain, only the strikes.
  :::

- **strikeLimit** `number`

  Limit the number of total strikes returned by the option chain. For example, if a complete chain included 30 strikes and the limit was set to 10, the 20 strikes furthest from the money will be excluded from the response.

  :::tip
  If `strikeLimit` is combined with the `range` or `side` parameter, those parameters will be applied first. In the above example, if the range were set to `itm` (in the money) and side set to `call`, all puts and out of the money calls would be first excluded by the range parameter and then strikeLimit will return a maximum of 10 in the money calls that are closest to the money.
  If the `side` parameter has not been used but `range` has been specified, then `strikeLimit` will return the requested number of calls and puts for each side of the chain, but duplicating the number of strikes that are received.
  :::

  - **range** `string`

  Limit the option chain to strikes that are in the money, out of the money, at the money, or include all. If omitted all options will be returned. Valid inputs: `itm`, `otm`, `all`.

</TabItem>

<TabItem value="liquidity" label="Price/Liquidity Filters">

- **minBid** `number`

  Limit the option chain to options with a bid price greater than or equal to the `number` provided.

- **maxBid** `number`

  Limit the option chain to options with a bid price less than or equal to the `number` provided.

- **minAsk** `number`

  Limit the option chain to options with an ask price greater than or equal to the `number` provided.

- **maxAsk** `number`

  Limit the option chain to options with an ask price less than or equal to the `number` provided.

- **maxBidAskSpread** `number`

  Limit the option chain to options with a bid-ask spread less than or equal to the `number` provided.

- **maxBidAskSpreadPct** `number`

  Limit the option chain to options with a bid-ask spread less than or equal to the `percent` provided (relative to the underlying). For example, a value of `0.5%` would exclude all options trading with a bid-ask spread greater than $1.00 in an underlying that trades at $200.

- **minOpenInterest** `number`

  Limit the option chain to options with an open interest greater than or equal to the `number` provided.

- **minVolume** `number`

  Limit the option chain to options with a volume transacted greater than or equal to the `number` provided.

</TabItem>

<TabItem value="otherfilters" label="Other Filters">

- **nonstandard** `boolean`

  Include non-standard contracts by setting `nonstandard` to `true`. If set to `false`, no non-standard options expirations will be returned. If no parameter is provided, the output will default to false.

- **side** `string`

  Limit the option chain to either `call` or `put`. If omitted, both sides will be returned.

- **am** `boolean`

  Limit the option chain to A.M. expirations by setting `am` to `true`. If set to `false`, no A.M. expirations will be returned. This parameter is only applicable for index options such as SPX, NDX, etc. If no parameter is provided, both A.M. and P.M. expirations will be returned.

- **pm** `boolean`

  Limit the option chain to P.M. expirations by setting `pm` to `true`. If set to `false`, no P.M. expirations will be returned. This parameter is only applicable for index options such as SPX, NDX, etc. If no parameter is provided, both A.M. and P.M. expirations will be returned.

:::caution
The `am` and `pm` parameters are only applicable for index options such as SPX, NDX, etc. If they are used for stocks or ETFs, a bad parameters error will be returned.
:::

</TabItem>

</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Status will always be `ok` when there is the quote requested.

- **optionSymbol** `array[string]`

  The option symbol according to OCC symbology.

- **underlying** `array[string]`

  The ticker symbol of the underlying security.

- **expiration** `array[number]`

  The option's expiration date in Unix time.

- **side** `array[string]`

  The response will be `call` or `put`.

- **strike** `array[number]`

  The exercise price of the option.

- **firstTraded** `array[date]`

  The date the option was first traded.

- **dte** `array[number]`

  The number of days until the option expires.

- **ask** `array[number]`

  The ask price.

- **askSize** `array[number]`

  The number of contracts offered at the ask price.

- **bid** `array[number]`

  The bid price.

- **bidSize** `array[number]`

  The number of contracts offered at the bid price.

- **mid** `array[number]`

  The midpoint price between the ask and the bid, also known as the mark price.

- **last** `array[number]`

  The last price negotiated for this option contract at the time of this quote.

- **volume** `array[number]`

  The number of contracts negotiated during the trading day at the time of this quote.

- **openInterest** `array[number]`

  The total number of contracts that have not yet been settled at the time of this quote.

- **underlyingPrice** `array[number]`

  The last price of the underlying security at the time of this quote.

- **inTheMoney** `array[booleans]`

  Specifies whether the option contract was in the money true or false at the time of this quote.

- **intrinsicValue** `array[number]`

  The intrinsic value of the option.

- **extrinsicValue** `array[number]`

  The extrinsic value of the option.

- **updated** `array[number]`

  The date and time of this quote snapshot in Unix time.

- **iv** `array[number]`

  The [implied volatility](https://www.investopedia.com/terms/i/iv.asp) of the option.

- **delta** `array[number]`

  The [delta](https://www.investopedia.com/terms/d/delta.asp) of the option.

- **gamma** `array[number]`

  The [gamma](https://www.investopedia.com/terms/g/gamma.asp) of the option.

- **theta** `array[number]`

  The [theta](https://www.investopedia.com/terms/t/theta.asp) of the option.

- **vega** `array[number]`

  The [vega](https://www.investopedia.com/terms/v/vega.asp) of the option.

- **rho** `array[number]`

  The [rho](https://www.investopedia.com/terms/r/rho.asp) of the option.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no candles are found for the request.

- **nextTime** `number` optional

  Unix time of the next quote if there is no data in the requested period, but there is data in a subsequent period.

- **prevTime** `number` optional

  Unix time of the previous quote if there is no data in the requested period, but there is data in a previous period.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>

## Option Chain Endpoint Pricing

The cost of using the option chain API endpoint depends on the type of data feed you choose and your usage pattern. Here's a breakdown of the pricing:

| Data Feed Type     | Cost Basis                | Credits Required per Unit |
|--------------------|---------------------------|---------------------------|
| Real-Time Feed     | Per option symbol         | 1 credit                  |
| Cached Feed        | Per API call              | 1 credit                  |

### Examples

1. **Real-Time Feed Usage**
   - If you query all strikes and all expirations for SPX (which has 22,718 total option contracts) using the Real-Time Feed, it will cost you 22,718 credits.

2. **Cached Feed Usage**
   - A single API call to SPX using the Cached Feed, regardless of the number of option symbols queried, will cost you 1 credit.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\options\expirations.mdx

---
title: Expirations
sidebar_position: 1
---

Get a list of current or historical option expiration dates for an underlying symbol. If no optional parameters are used, the endpoint returns all expiration dates in the option chain.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/options/expirations/{underlyingSymbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/options/expirations/AAPL](https://api.marketdata.app/v1/options/expirations/AAPL)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch("https://api.marketdata.app/v1/options/expirations/AAPL")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/options/expirations/AAPL"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="optionExpirations.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleOptionsExpirationsRequest() {
	expirations, err := OptionsExpirations().UnderlyingSymbol("AAPL").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, expiration := range expirations {
		fmt.Println(expiration)
	}
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "expirations": [
    "2022-09-23",
    "2022-09-30",
    "2022-10-07",
    "2022-10-14",
    "2022-10-21",
    "2022-10-28",
    "2022-11-18",
    "2022-12-16",
    "2023-01-20",
    "2023-02-17",
    "2023-03-17",
    "2023-04-21",
    "2023-06-16",
    "2023-07-21",
    "2023-09-15",
    "2024-01-19",
    "2024-06-21",
    "2025-01-17"
  ],
  "updated": 1663704000
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **underlyingSymbol** `string`

  The underlying ticker symbol for the options chain you wish to lookup.

</TabItem>
<TabItem value="optional" label="Optional">

- **strike** `number`

  Limit the lookup of expiration dates to the strike provided. This will cause the endpoint to only return expiration dates that include this strike.

- **date** `date`

  Use to lookup a historical list of expiration dates from a specific previous trading day. If date is omitted the expiration dates will be from the current trading day during market hours or from the last trading day when the market is closed. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Status will always be `ok` when there is strike
  data for the underlying/expirations requested.

- **expirations** `array[date]`

  The expiration dates requested for the underlying with the option strikes for each expiration.

- **updated** `date`

  The date and time of this list of options strikes was updated in Unix time. For historical strikes, this number should match the `date` parameter.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no data is found for the request.

- **nextTime** `number` optional

  Unix time of the next quote if there is no data in the requested period, but there is data in a subsequent period.

- **prevTime** `number` optional

  Unix time of the previous quote if there is no data in the requested period, but there is data in a previous period.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\options\index.mdx

---
title: Options
slug: /options
sidebar_position: 7
---

The Market Data API provides a comprehensive suite of options endpoints, designed to cater to various needs around options data. These endpoints are designed to be flexible and robust, supporting both real-time and historical data queries. They accommodate a wide range of optional parameters for detailed data retrieval, making the Market Data API a versatile tool for options traders and financial analysts.

## Root Endpoint For Options
```
https://api.marketdata.app/v1/options/
```
## Options Endpoints

import DocCardList from "@theme/DocCardList";
import { useCurrentSidebarCategory } from "@docusaurus/theme-common";

<DocCardList items={useCurrentSidebarCategory().items} />



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\options\lookup.mdx

---
title: Lookup
sidebar_position: 1
---

Generate a properly formatted OCC option symbol based on the user's human-readable description of an option. This endpoint converts text such as "AAPL 7/28/23 $200 Call" to OCC option symbol format: AAPL230728C00200000. The user input must be URL-encoded.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/options/lookup/{userInput}
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/options/lookup/AAPL%207/28/2023%20200%20Call](https://api.marketdata.app/v1/options/lookup/AAPL%207/28/2023%20200%20Call)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch(
  "https://api.marketdata.app/v1/options/lookup/AAPL%207/28/2023%20200%20Call"
)
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/options/lookup/AAPL%207/28/2023%20200%20Call"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="optionLookup.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleOptionLookupRequest() {
	optionSymbol, err := OptionLookup().UserInput("AAPL 7/28/2023 200 Call").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	fmt.Println(optionSymbol)
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "optionSymbol": "AAPL230728C00200000"
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **userInput** `string`

  The human-readable string input that contains (1) stock symbol (2) strike (3) expiration date (4) option side (i.e. put or call). This endpoint will translate the user's input into a valid OCC option symbol.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Status will always be `ok` when the OCC option symbol is successfully generated.

- **optionSymbol** `string`

  The generated OCC option symbol based on the user's input.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>

## Notes

- This endpoint will return an error if the option symbol that would be formed by the user's input does not exist.


# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\options\quotes.mdx

---
title: Quotes tg h
sidebar_position: 4
tags:
  - "API: High Usage"
---

Get a current or historical end of day quote for a single options contract.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/options/quotes/{optionSymbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/options/quotes/AAPL250117C00150000/](https://api.marketdata.app/v1/options/quotes/AAPL250117C00150000/)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch("https://api.marketdata.app/v1/options/quotes/AAPL250117C00150000/")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/options/quotes/AAPL250117C00150000/"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="optionQuotes.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleOptionQuoteRequest() {
	quotes, err := OptionQuote().OptionSymbol("AAPL250117C00150000").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, quote := range quotes {
		fmt.Println(quote)
	}
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "optionSymbol": ["AAPL250117C00150000"],
  "ask": [5.25],
  "askSize": [57],
  "bid": [5.15],
  "bidSize": [994],
  "mid": [5.2],
  "last": [5.25],
  "volume": [977],
  "openInterest": [61289],
  "underlyingPrice": [136.12],
  "inTheMoney": [false],
  "updated": [1665673292],
  "iv": [0.3468],
  "delta": [0.347],
  "gamma": [0.015],
  "theta": [-0.05],
  "vega": [0.264],
  "rho": [0.115],
  "intrinsicValue": [13.88],
  "extrinsicValue": [8.68]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **optionSymbol** `string`

  The option symbol (as defined by the OCC) for the option you wish to lookup. Use the current OCC option symbol format, even for historic options that quoted before the format change in 2010.

</TabItem>
<TabItem value="optional" label="Optional">

- **date** `date`

  Use to lookup a historical end of day quote from a specific trading day. If no date is specified the quote will be the most current price available during market hours. When the market is closed the quote will be from the last trading day. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

- **from** `date`

  Use to lookup a series of end of day quotes. From is the oldest (leftmost) date to return (inclusive). If from/to is not specified the quote will be the most current price available during market hours. When the market is closed the quote will be from the last trading day. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

- **to** `date`

  Use to lookup a series of end of day quotes. From is the newest (rightmost) date to return (exclusive). If from/to is not specified the quote will be the most current price available during market hours. When the market is closed the quote will be from the last trading day. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Status will always be `ok` when there is data for the quote requested.

- **optionSymbol** `array[string]`

  The option symbol according to OCC symbology.

- **ask** `array[number]`

  The ask price.

- **askSize** `array[number]`

  The number of contracts offered at the ask price.

- **bid** `array[number]`

  The bid price.

- **bidSize** `array[number]`

  The number of contracts offered at the bid price.

- **mid** `array[number]`

  The midpoint price between the ask and the bid, also known as the mark price.

- **last** `array[number]`

  The last price negotiated for this option contract at the time of this quote.

- **volume** `array[number]`

  The number of contracts negotiated during the trading day at the time of this quote.

- **openInterest** `array[number]`

  The total number of contracts that have not yet been settled at the time of this quote.

- **underlyingPrice** `array[number]`

  The last price of the underlying security at the time of this quote.

- **inTheMoney** `array[booleans]`

  Specifies whether the option contract was in the money true or false at the time of this quote.

- **intrinsicValue** `array[number]`

  The instrinisc value of the option.

- **extrnisicValue** `array[number]`

  The extrinsic value of the option.

- **updated** `array[number]`

  The date and time of this quote snapshot in Unix time.

- **iv** `array[number]`

  The [implied volatility](https://www.investopedia.com/terms/i/iv.asp) of the option.

- **delta** `array[number]`

  The [delta](https://www.investopedia.com/terms/d/delta.asp) of the option.

- **gamma** `array[number]`

  The [gamma](https://www.investopedia.com/terms/g/gamma.asp) of the option.

- **theta** `array[number]`

  The [theta](https://www.investopedia.com/terms/t/theta.asp) of the option.

- **vega** `array[number]`

  The [vega](https://www.investopedia.com/terms/v/vega.asp) of the option.

- **rho** `array[number]`

  The [rho](https://www.investopedia.com/terms/r/rho.asp) of the option.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no candles are found for the request.

- **nextTime** `number` optional

  Unix time of the next quote if there is no data in the requested period, but there is data in a subsequent period.

- **prevTime** `number` optional

  Unix time of the previous quote if there is no data in the requested period, but there is data in a previous period.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\options\strikes.mdx

---
title: Strikes
sidebar_position: 2
---

Get a list of current or historical options strikes for an underlying symbol. If no optional parameters are used, the endpoint returns the strikes for every expiration in the chain.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/options/strikes/{underlyingSymbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/options/strikes/AAPL/?date=2023-01-03&expiration=2023-01-20](https://api.marketdata.app/v1/options/strikes/AAPL/?date=2023-01-03&expiration=2023-01-20)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch(
  "https://api.marketdata.app/v1/options/strikes/AAPL/?date=2023-01-03&expiration=2023-01-20"
)
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/options/strikes/AAPL/?date=2023-01-03&expiration=2023-01-20"

response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="optionStrikes.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleOptionsStrikesRequest() {
	expirations, err := OptionsStrikes().UnderlyingSymbol("AAPL").Date("2023-01-03").Expiration("2023-01-20").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, expiration := range expirations {
		fmt.Println(expiration)
	}
}

```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "updated": 1663704000,
  "2023-01-20": [
    30.0, 35.0, 40.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0,
    95.0, 100.0, 105.0, 110.0, 115.0, 120.0, 125.0, 130.0, 135.0, 140.0, 145.0,
    150.0, 155.0, 160.0, 165.0, 170.0, 175.0, 180.0, 185.0, 190.0, 195.0, 200.0,
    205.0, 210.0, 215.0, 220.0, 225.0, 230.0, 235.0, 240.0, 245.0, 250.0, 260.0,
    270.0, 280.0, 290.0, 300.0
  ]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **underlyingSymbol** `string`

  The underlying ticker symbol for the options chain you wish to lookup.

</TabItem>
<TabItem value="optional" label="Optional">

- **expiration** `date`

  Limit the lookup of strikes to options that expire on a specific expiration date. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

- **date** `date`

  - Use to lookup a historical list of strikes from a specific previous trading day.
  - If date is omitted the expiration dates will be from the current trading day during market hours or from the last trading day when the market is closed.
  - Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Status will always be `ok` when there is strike
  data for the underlying/expirations requested.

- **dates** `array[number]`

  The expiration dates requested for the underlying with the option strikes for each expiration.

- **updated** `array[number]`

  The date and time of this list of options strikes was updated in Unix time. For historical strikes, this number should match the `date` parameter.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no data is found for the request.

- **nextTime** `number` optional

  Unix time of the next quote if there is no data in the requested period, but there is data in a subsequent period.

- **prevTime** `number` optional

  Unix time of the previous quote if there is no data in the requested period, but there is data in a previous period.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\rate-limiting.md

---
title: Rate Limits
sidebar_position: 4
---

We enforce rate limits to ensure our API remains accessible and efficient for all users. We have two types of rate limits: API credits (total requests per unit of time) and a concurrent request limit (simultaneous requests).

## API Credits

Normally each API call consumes a single credit. However, **if the response includes more than a single symbol, it can consume multiple credits**. Often, users can navigate around a rate limit by making the most of the diverse filters we provide (e.g. instead of retrieving an entire option chain, apply specific filters to narrow down the results).

**The rate limit is a hard limit. Once the limit has been reached, you will no longer be able to make requests until the request counter resets.** Requests in excess of the rate limit will generate 429 responses.

### Usage Counter Reset Time

The usage counter for all plans with a daily limit resets at **9:30 AM Eastern Time** (NYSE opening bell). This reset timing is crucial for users to understand so they can plan their API usage efficiently without hitting the rate limit unexpectedly.

:::tip Managing Timezone Changes
To handle the reset time accurately regardless of your local timezone, it's recommended to use the `America/New_York` timezone identifier. This ensures that your application adjusts for any changes in Eastern Time, including daylight saving shifts, automatically.

By aligning your application's timing functions with the `America/New_York` timezone, you can ensure that your usage of the API remains within the allocated rate limits, taking into account the precise reset timing at 9:30 AM Eastern Time.
:::

## Concurrent Request Limit

To maintain the stability and performance of our API, we enforce a limit of no more than 50 concurrent requests across all subscription plans. This means that at any given time, you should not have more than 50 active API calls in progress. Requests in excess of the concurrency limit will generate 429 responses.

To adhere to this limit, it is advisable to implement a worker or thread pool mechanism in your application that does not exceed 50 workers. Each worker should handle no more than one API request at a time. This setup helps in efficiently managing API calls without breaching the concurrent request limit and ensures fair usage among all users.

## Rate Limits By Plan
Different plans have specific rate limits, with most plans enforcing a daily rate limit while our Commercial Plan uses a per minute rate limit.

|                          | Free Forever | Starter   | Trader    | Commercial       |
|--------------------------|--------------|-----------|-----------|------------------|
| Daily API Credits        | 100          | 10,000    | 100,000   | No Limit         |
| Per Minute API Credits   | No Limit     | No Limit  | No Limit  | 60,000           |
| Concurrent Request Limit | 50           | 50        | 50        | 50               |


#### Summary

- **Free Forever Plan:** 100 credits per day.
- **Starter Plan:** 10,000 credits per day.
- **Trader Plan:** 100,000 credits per day.
- **Commercial Plan:** 60,000 credits per minute.

## Credits
Each time you make a request to the API, the system will increase your credits counter. Normally each successful response will increase your counter by 1 and each call to our API will be counted as a single credit. However, **if you request multiple symbols in a single API call using the bulkquotes, the bulkcandles, or the option chain endpoint, a request will be used for each symbol that is included in the response**.

:::caution 
For users working with options, take care before repeatedly requesting quotes for an entire option chain. **Each option symbol included in the response will consume a request**. If you were to download the entire SPX option chain (which has 20,000+ option symbols), you would exhaust your request limit very quickly. Use our extensive option chain filtering parameters to request only the strikes/expirations you need. 
:::

## Headers to Manage the Rate Limit
We provide the following headers in our responses to help you manage the rate limit and throttle your applications when necessary:

- `X-Api-Ratelimit-Limit`: The maximum number of requests you're permitted to make (per day for Free/Starter/Trader plans or per minute for commercial users).
- `X-Api-Ratelimit-Remaining`: The number of requests remaining in the current rate day/period.
- `X-Api-Ratelimit-Reset`: The time at which the current rate limit window resets in UTC epoch seconds.
- `X-Api-Ratelimit-Consumed`: The quantity of requests that were consumed in the current request.

## Detailed Rate Limit Rules
- Each successful response increases the counter by a minimum of 1 request.
- Only status 200/203 responses consume requests.
- NULL responses are not counted.
- Error responses are not counted.
- Requests consume more than 1 credit if the response includes prices for more than 1 symbol (i.e. options/chain or stocks/bulkquotes endpoints).
- Responses that include more than one symbol, but do not include the **bid**, **ask**, **mid**, or **last** columns _**do not**_ consume multiple credits and are counted as a single request.
- Certain free trial symbols like AAPL stock, AAPL options, the VIX index, and the VFINX mutual fund do not consume requests.

## Strategies To Avoid Rate Limiting
- Exclude the bid, ask, mid, and last columns from your option chain requests if the current price is not needed.
- Use the extensive option chain filters such as `strikeLimit` to exclude unnecessary strikes from your requests.
- Paying customers can make use of the reduced-price cached feed. Use the `feed=cached` parameter on the `stocks/bulkquotes` and `options/chain` endpoints to retrieve previously cached quotes instead of making a live request. This can save thousands of credits. For more details, refer to the [feed parameter documentation](/api/universal-parameters/feed).


# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\sdk.mdx

---
title: SDKs
sidebar_position: 2
---

## Official Market Data SDKs

We offer SDKs for various programming languages and platforms to cater to a wide range of developers and applications:

<div className="sdk-list">
  <div className="sdk-item">
    [![Postman Collection Logo](/img/postman-logo.svg)](/sdk/postman)
    ### [Postman Collection](/sdk/postman)
    [Comprehensive Postman Collection for easy API integration and testing.](/sdk/postman)
  </div>
  <div className="sdk-item">
    ![Python SDK Logo](/img/python-logo-only.svg)
    ### Python SDK
    _In development_. Perfect for data analysis, backend services, and automation scripts.
  </div>
  <div className="sdk-item">
    [![PHP SDK Logo](/img/php-logo.svg)](/sdk/php)
    ### [PHP SDK](/sdk/php)
    [Market Data integration for web applications and server-side processing.](/sdk/php)
  </div>
  <div className="sdk-item">
    [![Go SDK Logo](/img/Go-Logo_Aqua.svg)](/sdk/go)
    ### [Go SDK](/sdk/go)
    [High performance Market Data SDK integration for enterprise-level backend systems.](/sdk/go)
  </div>
</div>

Each SDK is designed with simplicity in mind, ensuring you can get up and running with minimal setup.

## Unofficial Client Libraries

We encourage our users to open source their implementations of our API in the languages of their choice and we will link to those implementations on this page. Please let us know if you have developed a Market Data client library and we will be happy to add a link to it.

### Python

- [guruappa/MarketDataApp](https://github.com/guruappa/MarketDataApp)
- [marts01/market_data](https://github.com/marts01/market_data)


# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\stocks\.status.mdx

---
title: Status tg n
sidebar_position: 10
---

Get the current trading status for a stock exchange or symbol. The endpoint will respond with detailed information to let you know whether a symbol is available to trade right now. Use the optional parameters to make a historical request to determine if a symbol was available to trade at a specific date or time in the past.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/stocks/status/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/stocks/status/?symbol=AAPL&dateformat=timestamp](https://api.marketdata.app/v1/stocks/status/?symbol=AAPL&dateformat=timestamp)

**GET** [https://api.marketdata.app/v1/stocks/status/?symbol=AAPL&date=2024-07-04&dateformat=timestamp](https://api.marketdata.app/v1/stocks/status/?symbol=AAPL&date=2024-07-24&dateformat=timestamp)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch(
  "https://api.marketdata.app/v1/stocks/status/?symbol=AAPL&dateformat=timestamp"
)
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });

fetch("https://api.marketdata.app/v1/stocks/status/?symbol=AAPL&date=2024-07-04&dateformat=timestamp")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url1 = "https://api.marketdata.app/v1/stocks/status/?symbol=AAPL&dateformat=timestamp"
url2 = "https://api.marketdata.app/v1/stocks/status/?symbol=AAPL&date=2024-07-04&dateformat=timestamp"

response1 = requests.request("GET", url1)
response2 = requests.request("GET", url2)

print(response1.text)
print(response2.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="stockstatus.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleStockStatus() {
	ess, err := api.StockStatus().Symbol("AAPL").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, status := range ess {
		fmt.Println(status)
	}
}

func ExampleStockStatus_historical() {
	ess, err := api.StockStatus().Symbol("AAPL")Date("2024-07-04").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, status := range ess {
		fmt.Println(status)
	}
}
```

</TabItem>
</Tabs>

## Response Example

<Tabs>
<TabItem value="Open" label="Open" default>

The following represents the output a for a normal day in the middle of the trading week.

```json
{
  "s": "ok",
  "status": {
    "activeSession": "primary",
    "status": "open",
    "reason": "Core Trading Session",    
    "primary": true,
    "preTrading": false,
    "postTrading": false,
    "exchangeName": "New York Stock Exchange",
    "exchangeMic": "XNYS",
    "exchangeTz": "America/New_York",
    "exchangeTime": "2024-07-09T11:00:00-04:00"
  },
  "current": {
    "date": "2024-07-09",
    "primary": {
      "name": "Core Trading Session",
      "type": "Primary Trading Session",
      "status": "open",
      "start": "2024-07-09T09:30:00-04:00",
      "end": "2024-07-09T16:00:00-04:00",
      "notes": "Market is currently open and trading as usual."
    },
    "preTrading": {
      "name": "Early Trading Session",
      "type": "Pre-Trading Session",
      "status": "closed",
      "start": "2024-07-09T04:00:00-04:00",
      "end": "2024-07-09T09:30:00-04:00",
      "notes": "Early trading is closed."
    },
    "postTrading": {
      "name": "Late Trading Session",
      "type": "Post-Trading Session",
      "status": "upcoming",
      "start": "2024-07-09T16:00:00-04:00",
      "end": "2024-07-09T20:00:00-04:00",
      "notes": "Late trading will start at 4:00 PM ET."
    }
  },
  "previous": {
    "date": "2024-07-08",
    "primary": {
      "name": "Core Trading Session",
      "type": "Primary Trading Session",
      "status": "closed",
      "start": "2024-07-08T09:30:00-04:00",
      "end": "2024-07-08T16:00:00-04:00",
      "notes": "Market was open and traded as usual."
    },
    "preTrading": {
      "name": "Early Trading Session",
      "type": "Pre-Trading Session",
      "status": "closed",
      "start": "2024-07-08T04:00:00-04:00",
      "end": "2024-07-08T09:30:00-04:00",
      "notes": "Early trading ended at 9:30 AM on 07/08/2024."
    },
    "postTrading": {
      "name": "Late Trading Session",
      "type": "Post-Trading Session",
      "status": "closed",
      "start": "2024-07-08T16:00:00-04:00",
      "end": "2024-07-08T20:00:00-04:00",
      "notes": "Late trading ended at 8:00 PM on 07/08/2024."
    }
  },
  "next": {
    "date": "2024-07-10",
    "primary": {
      "name": "Core Trading Session",
      "type": "Primary Trading Session",
      "status": "upcoming",
      "start": "2024-07-10T09:30:00-04:00",
      "end": "2024-07-10T16:00:00-04:00",
      "notes": "Next regular market session starts at 9:30 AM ET."
    },
    "preTrading": {
      "name": "Early Trading Session",
      "type": "Pre-Trading Session",
      "status": "upcoming",
      "start": "2024-07-10T04:00:00-04:00",
      "end": "2024-07-10T09:30:00-04:00",
      "notes": "Next early trading session starts at 4:00 AM ET."
    },
    "postTrading": {
      "name": "Late Trading Session",
      "type": "Post-Trading Session",
      "status": "upcoming",
      "start": "2024-07-10T16:00:00-04:00",
      "end": "2024-07-10T20:00:00-04:00",
      "notes": "Next late trading session starts at 4:00 PM ET."
    }
  }
}
```
</TabItem>
<TabItem value="Closed" label="Closed">

The following represents the output for a day the market was closed due to the Independence Day holiday.

```json
{
  "s": "ok",
  "status": {
    "activeSession": null,
    "status": "closed",
    "reason": "Market Holiday - Independence Day",    
    "primary": false,
    "preTrading": false,
    "postTrading": false,
    "exchangeName": "New York Stock Exchange",
    "exchangeMic": "XNYS",
    "exchangeTz": "America/New_York",
    "exchangeTime": "2024-07-04T11:00:00-04:00"
  },
  "current": {
    "date": "2024-07-04",
    "primary": null,
    "preTrading": null,
    "postTrading": null
  },
  "previous": {
    "date": "2024-07-03",
    "primary": {
      "name": "Core Trading Session",
      "type": "Primary Trading Session",
      "status": "closed",
      "start": "2024-07-038T09:30:00-04:00",
      "end": "2024-07-03T13:00:00-04:00",
      "notes": "Market closed early - Independence Day."
    },
    "preTrading": {
      "name": "Early Trading Session",
      "type": "Pre-Trading Session",
      "status": "closed",
      "start": "2024-07-03T04:00:00-04:00",
      "end": "2024-07-03T09:30:00-04:00",
      "notes": "Early trading ended at 9:30 AM on 07/03/2024."
    },
    "postTrading": {
      "name": "Late Trading Session",
      "type": "Post-Trading Session",
      "status": "closed",
      "start": "2024-07-03T13:00:00-04:00",
      "end": "2024-07-03T17:00:00-04:00",
      "notes": "Late trading closed early - Independence Day."
    }
  },
  "next": {
    "date": "2024-07-05",
    "primary": {
      "name": "Core Trading Session",
      "type": "Primary Trading Session",
      "status": "upcoming",
      "start": "2024-07-05T09:30:00-04:00",
      "end": "2024-07-05T16:00:00-04:00",
      "notes": "Next regular market session starts at 9:30 AM ET."
    },
    "preTrading": {
      "name": "Early Trading Session",
      "type": "Pre-Trading Session",
      "status": "upcoming",
      "start": "2024-07-05T04:00:00-04:00",
      "end": "2024-07-05T09:30:00-04:00",
      "notes": "Next early trading session starts at 4:00 AM ET."
    },
    "postTrading": {
      "name": "Late Trading Session",
      "type": "Post-Trading Session",
      "status": "upcoming",
      "start": "2024-07-05T16:00:00-04:00",
      "end": "2024-07-05T20:00:00-04:00",
      "notes": "Next late trading session starts at 4:00 PM ET."
    }
  }
}
```
</TabItem>
</Tabs>

## Request Parameters

<Tabs>
<TabItem value="required" label="Required">

There are no required parameters for `status`. If no parameter is given, the request will return the market status for the NYSE for the current day.

</TabItem>
<TabItem value="optional" label="Optional" default>

- **symbol** `string`

  Market Data will output the market status of the primary exchange where the symbol is traded.

- **exchange** `string`

  Market Data will output the market status of the exchange listed. Valid strings for the US include: `nyse`, `nasdaq`, `otc`. Mic codes may also be used: `xnys`, `xnas`, `otcm`.

- **date** `date`

  Consult the market status relative to the specified date. Accepted timestamp inputs: ISO 8601, unix, spreadsheet, relative date strings. The status will be output as if you ran the query on the date used in the input. This means the "next" key will refer to the next session after the session indicated in `date` and the previous session will be relative to the session indicated in `date`.

- **symbol** `string`

  Consult whether the market was open or closed on the specified date. Accepted timestamp inputs: ISO 8601, unix, spreadsheet, relative date strings.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Will always be `ok` when the request is successful.

- **status** `object`

  Contains detailed information about the current market status.

  - **activeSession** `string`

    Indicates the current active trading session. Possible values include `primary`, `preTrading`, `postTrading`, or `null` if the market is closed.

  - **status** `string`

    The overall status of the market. Possible values include `open`, `closed`, or `upcoming`.

  - **reason** `string`

    Provides a reason for the current market status, such as `Core Trading Session` or `Market Holiday`.

  - **primary** `boolean`

    Indicates if the primary trading session is active.

  - **preTrading** `boolean`

    Indicates if the pre-trading session is active.

  - **postTrading** `boolean`

    Indicates if the post-trading session is active.

  - **exchangeName** `string`

    The name of the exchange, e.g., `New York Stock Exchange`.

  - **exchangeMic** `string`

    The Market Identifier Code (MIC) of the exchange, e.g., `XNYS`.

  - **exchangeTz** `string`

    The time zone of the exchange, e.g., `America/New_York`.

  - **exchangeTime** `string`

    The current time at the exchange .

- **current** `object`

  Contains information about the current trading day.

  - **date** `string`

    The current date .

  - **primary** `object`

    Details about the primary trading session.

    - **name** `string`

      The name of the session, e.g., `Core Trading Session`.

    - **type** `string`

      The type of the session, e.g., `Primary Trading Session`.

    - **status** `string`

      The status of the session, e.g., `open`, `closed`, or `upcoming`.

    - **start** `string`

      The start time of the session .

    - **end** `string`

      The end time of the session .

    - **notes** `string`

      Additional notes about the session.

  - **preTrading** `object`

    Details about the pre-trading session.

    - **name** `string`

      The name of the session, e.g., `Early Trading Session`.

    - **type** `string`

      The type of the session, e.g., `Pre-Trading Session`.

    - **status** `string`

      The status of the session, e.g., `open`, `closed`, or `upcoming`.

    - **start** `string`

      The start time of the session .

    - **end** `string`

      The end time of the session .

    - **notes** `string`

      Additional notes about the session.

  - **postTrading** `object`

    Details about the post-trading session.

    - **name** `string`

      The name of the session, e.g., `Late Trading Session`.

    - **type** `string`

      The type of the session, e.g., `Post-Trading Session`.

    - **status** `string`

      The status of the session, e.g., `open`, `closed`, or `upcoming`.

    - **start** `string`

      The start time of the session .

    - **end** `string`

      The end time of the session .

    - **notes** `string`

      Additional notes about the session.

- **previous** `object`

  Contains information about the previous trading day.

  - **date** `string`

    The previous date .

  - **primary** `object`

    Details about the primary trading session.

    - **name** `string`

      The name of the session, e.g., `Core Trading Session`.

    - **type** `string`

      The type of the session, e.g., `Primary Trading Session`.

    - **status** `string`

      The status of the session, e.g., `open`, `closed`, or `upcoming`.

    - **start** `string`

      The start time of the session .

    - **end** `string`

      The end time of the session .

    - **notes** `string`

      Additional notes about the session.

  - **preTrading** `object`

    Details about the pre-trading session.

    - **name** `string`

      The name of the session, e.g., `Early Trading Session`.

    - **type** `string`

      The type of the session, e.g., `Pre-Trading Session`.

    - **status** `string`

      The status of the session, e.g., `open`, `closed`, or `upcoming`.

    - **start** `string`

      The start time of the session .

    - **end** `string`

      The end time of the session .

    - **notes** `string`

      Additional notes about the session.

  - **postTrading** `object`

    Details about the post-trading session.

    - **name** `string`

      The name of the session, e.g., `Late Trading Session`.

    - **type** `string`

      The type of the session, e.g., `Post-Trading Session`.

    - **status** `string`

      The status of the session, e.g., `open`, `closed`, or `upcoming`.

    - **start** `string`

      The start time of the session .

    - **end** `string`

      The end time of the session .

    - **notes** `string`

      Additional notes about the session.

- **next** `object`

  Contains information about the next trading day.

  - **date** `string`

    The next date .

  - **primary** `object`

    Details about the primary trading session.

    - **name** `string`

      The name of the session, e.g., `Core Trading Session`.

    - **type** `string`

      The type of the session, e.g., `Primary Trading Session`.

    - **status** `string`

      The status of the session, e.g., `open`, `closed`, or `upcoming`.

    - **start** `string`

      The start time of the session .

    - **end** `string`

      The end time of the session .

    - **notes** `string`

      Additional notes about the session.

  - **preTrading** `object`

    Details about the pre-trading session.

    - **name** `string`

      The name of the session, e.g., `Early Trading Session`.

    - **type** `string`

      The type of the session, e.g., `Pre-Trading Session`.

    - **status** `string`

      The status of the session, e.g., `open`, `closed`, or `upcoming`.

    - **start** `string`

      The start time of the session .

    - **end** `string`

      The end time of the session .

    - **notes** `string`

      Additional notes about the session.

  - **postTrading** `object`

    Details about the post-trading session.

    - **name** `string`

      The name of the session, e.g., `Late Trading Session`.

    - **type** `string`

      The type of the session, e.g., `Post-Trading Session`.

    - **status** `string`

      The status of the session, e.g., `open`, `closed`, or `upcoming`.

    - **start** `string`

      The start time of the session .

    - **end** `string`

      The end time of the session .

    - **notes** `string`

      Additional notes about the session.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no data is found for the date or symbol requested.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\stocks\bulkcandles.mdx

---
title: Bulk Candles
sidebar_position: 2
---

Get bulk candle data for stocks. This endpoint returns bulk daily candle data for multiple stocks. Unlike the standard candles endpoint, this endpoint returns a single daily for each symbol provided. The typical use-case for this endpoint is to get a complete market snapshot during trading hours, though it can also be used for bulk snapshots of historical daily candles.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/stocks/bulkcandles/{resolution}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/stocks/bulkcandles/D/?symbols=AAPL,META,MSFT](https://api.marketdata.app/v1/stocks/bulkcandles/D/?symbols=AAPL,META,MSFT)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch(
  "https://api.marketdata.app/v1/stocks/bulkcandles/D/?symbols=AAPL,META,MSFT"
)
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/stocks/bulkcandles/D/?symbols=AAPL,META,MSFT"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="bulkStockCandles.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleBulkStockCandlesRequest_get() {
	symbols := []string{"AAPL", "META", "MSFT"}
	candles, err := BulkStockCandles().Resolution("D").Symbols(symbols).Get()
	if err != nil {
		fmt.Print(err)
		return
	}
  
	for _, candle := range candles {
		fmt.Println(candle)
	}
}

```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "symbol": ["AAPL", "META", "MSFT"],
  "o": [196.16, 345.58, 371.49],
  "h": [196.95, 353.6, 373.26],
  "l": [195.89, 345.12, 369.84],
  "c": [196.94, 350.36, 373.26],
  "v": [40714051, 17729362, 20593658],
  "t": [1703048400,1703048400,1703048400]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **resolution** `string`
  The duration of each candle. Only daily candles are supported at this time.

  - Daily Resolutions: (`daily`, `D`, `1D`)

- **symbols** `string`
  The ticker symbols to return in the response, separated by commas. The symbols parameter may be omitted if the `snapshot` parameter is set to `true`.

</TabItem>
<TabItem value="Optional" label="Optional">

- **snapshot** `boolean`
  Returns candles for all available symbols for the date indicated. The `symbols` parameter can be omitted if `snapshot` is set to true.

- **date** `date`
  The date of the candles to be returned. If no date is specified, during market hours the candles returned will be from the current session. If the market is closed the candles will be from the most recent session. Accepted date inputs: `ISO 8601`, `unix`, `spreadsheet`.

- **adjustsplits** `boolean`
  Adjust historical data for for historical splits and reverse splits. Market Data uses the CRSP methodology for adjustment.
  Daily candles default: `true`.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Will always be `ok` when there is data for the candles requested.

- **symbol** `string`

  The ticker symbol of the stock.

- **o** `array[number]`

  Open price.

- **h** `array[number]`

  High price.

- **l** `array[number]`

  Low price.

- **c** `array[number]`

  Close price.

- **v** `array[number]`

  Volume.

- **t** `array[number]`

  Candle time (Unix timestamp, Exchange Timezone). Daily candles are returned at 00:00:00 without times.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no candles are found for the request.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`

  An error message.

</TabItem>
</Tabs>

## Notes

- The stocks/bulkcandles endpoint will consume one API credit for each symbol returned in the response.


# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\stocks\bulkquotes.mdx

---
title: Bulk Quotes
sidebar_position: 4
---

Get a real-time price quote for a multiple stocks in a single API request.

:::tip
The bulkquotes endpoint is designed to return hundreds of symbols at once or full market snapshots. Response times for less than 50 symbols will be quicker using the standard [quotes endpoint](/api/stocks/quotes/) and sending your requests in parallel.
:::

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/stocks/bulkquotes/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/stocks/bulkquotes/?symbols=AAPL,META,MSFT](https://api.marketdata.app/v1/stocks/bulkquotes/?symbols=AAPL,META,MSFT)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch("https://api.marketdata.app/v1/stocks/bulkquotes/?symbols=AAPL,META,MSFT")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/stocks/bulkquotes/?symbols=AAPL,META,MSFT"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="bulkStockQuotes.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleBulkStockQuotesRequest() {
	symbols := []string{"AAPL", "META", "MSFT"}
	quotes, err := BulkStockQuotes().Symbols(symbols).Get()
	if err != nil {
		fmt.Print(err)
		return
	}
  
	for _, quote := range quotes {
		fmt.Println(quote)
	}
}

```
</TabItem>
</Tabs>

## Response Example

```json
{
    "s": "ok",
    "symbol": ["AAPL", "META", "MSFT"],
    "ask": [187.67, 396.9, 407.0],
    "askSize": [1, 6, 1],
    "bid": [187.65, 396.8, 406.97],
    "bidSize": [1, 3, 3],
    "mid": [187.66, 396.85, 406.985],
    "last": [187.65, 396.85, 407.0],
    "change": [-4.079999999999984, -4.169999999999959, -2.7200000000000273],
    "changepct": [-0.021279924894382643, -0.010398483866141239, -0.006638680074197078],
    "volume": [55299411, 18344385, 29269513],
    "updated": [1706650085, 1706650085, 1706650085]
}
```

## Request Parameters

<Tabs>
<TabItem value="Required" label="Required" default>
- **symbols** `string`

  The ticker symbols to return in the response, separated by commas. The symbols parameter may be omitted if the `snapshot` parameter is set to true.
</TabItem>

<TabItem value="Optional" label="Optional">
- **snapshot** `boolean`

  Returns a full market snapshot with quotes for all symbols when set to `true`. The `symbols` parameter may be omitted if the `snapshot` parameter is set.

- **extended** `boolean`

  Control the inclusion of extended hours data in the quote output. Defaults to `true` if omitted. 

  - When set to `true`, the most recent quote is always returned, without regard to whether the market is open for primary trading or extended hours trading.
  - When set to `false`, only quotes from the primary trading session are returned. When the market is closed or in extended hours, a historical quote from the last closing bell of the primary trading session is returned instead of an extended hours quote. 

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Will always be `ok` when there is data for the symbol requested.

- **symbol** `array[string]`

  The symbol of the stock.

- **ask** `array[number]`

  The ask price of the stock.

- **askSize** `array[number]`

  The number of shares offered at the ask price.

- **bid** `array[number]`

  The bid price.

- **bidSize** `array[number]`

  The number of shares that may be sold at the bid price.

- **mid** `array[number]`

  The midpoint price between the ask and the bid.

- **last** `array[number]`

  The last price the stock traded at.

- **change** `array[number]`

  The difference in price in currency units compared to the closing price of the previous primary trading session.

- **changepct** `array[number]`

  The difference in price in percent, expressed as a decimal, compared to the closing price of the previous primary trading session. For example, a 3% change will be represented as 0.03. 

:::note
  - When the market is open for primary trading, **change** and **changepct** are always calculated using the last traded price and the last primary session close. When the market is closed or in extended hours, this criteria is also used as long as `extended` is omitted or set to `true`.
  - When `extended` is set to `false`, and the market is closed or in extended hours, quotes from extended hours are not considered. The values for **change** and **changepct** will be calculated using the last two closing prices instead.
:::

- **52weekHigh** `array[number]`

  The 52-week high for the stock. This parameter is omitted unless the optional 52week request parameter is set to true.

- **52weekLow** `array[number]`

  The 52-week low for the stock. This parameter is omitted unless the optional 52week request parameter is set to true.

- **volume** `array[number]`

  The number of shares traded during the current session.

- **updated** `array[date]`

  The date/time of the current stock quote.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no quote can be found for the symbol.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`

  An error message.

</TabItem>
</Tabs>

## Bulk Stock Quotes Endpoint Pricing

The cost of using the bulk stock quotes API endpoint depends on the type of data feed you choose and your usage pattern. Here's a breakdown of the pricing:

| Data Feed Type     | Cost Basis                | Credits Required per Unit |
|--------------------|---------------------------|---------------------------|
| Real-Time Feed     | Per stock symbol          | 1 credit                  |
| Cached Feed        | Per API call              | 1 credit                  |

### Examples

1. **Real-Time Feed Usage**
   - If you query quotes for 500 different stock symbols using the Real-Time Feed, it will cost you 500 credits.

2. **Cached Feed Usage**
   - A single API call to retrieve quotes for 500 different stock symbols using the Cached Feed will cost you 1 credit.


# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\stocks\candles.mdx

---
title: Candles tg h
sidebar_position: 1
tags:
  - "API: High Usage"
---

Get historical price candles for a stock.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/stocks/candles/{resolution}/{symbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/stocks/candles/D/AAPL?from=2020-01-01&to=2020-12-31](https://api.marketdata.app/v1/stocks/candles/D/AAPL?from=2020-01-01&to=2020-12-31)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch(
  "https://api.marketdata.app/v1/stocks/candles/D/AAPL?from=2020-01-01&to=2020-12-31"
)
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });

```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/stocks/candles/D/AAPL?from=2020-01-01&to=2020-12-31"

response = requests.request("GET", url)

print(response.text)
```
</TabItem>
<TabItem value="Go" label="Go">

```go title="stockCandles.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleStockCandlesRequest() {
	candles, err := StockCandles().Resolution("D").Symbol("AAPL").From("2020-01-01").To("2020-12-31").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, candle := range candles {
		fmt.Println(candle)
	}
}

```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "c": [217.68, 221.03, 219.89],
  "h": [222.49, 221.5, 220.94],
  "l": [217.19, 217.1402, 218.83],
  "o": [221.03, 218.55, 220],
  "t": [1569297600, 1569384000, 1569470400],
  "v": [33463820, 24018876, 20730608]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **resolution** `string`

  The duration of each candle.

  - Minutely Resolutions: (`minutely`, `1`, `3`, `5`, `15`, `30`, `45`, ...)
  - Hourly Resolutions: (`hourly`, `H`, `1H`, `2H`, ...)
  - Daily Resolutions: (`daily`, `D`, `1D`, `2D`, ...)
  - Weekly Resolutions: (`weekly`, `W`, `1W`, `2W`, ...)
  - Monthly Resolutions: (`monthly`, `M`, `1M`, `2M`, ...)
  - Yearly Resolutions:(`yearly`, `Y`, `1Y`, `2Y`, ...)

- **symbol** `string`

  The company's ticker symbol.

</TabItem>
<TabItem value="date" label="Dates">

All `date` parameters are optional. By default the most recent candle is returned if no date parameters are provided.

- **from** `date`

  The leftmost candle on a chart (inclusive). From and countback are mutually exclusive. If you use `countback`, `from` must be omitted. Accepted timestamp inputs: ISO 8601, unix, spreadsheet. 

- **to** `date`

  The rightmost candle on a chart (inclusive). Accepted timestamp inputs: ISO 8601, unix, spreadsheet.

- **countback** `number`

  Will fetch a specific number of candles before (to the left of) `to`. From and countback are mutually exclusive. If you use `from`, `countback` must be omitted.

:::note
There is no maximum date range limit on daily candles. When requesting intraday candles of any resolution, no more than 1 year of data can be requested in a single request.
:::

</TabItem>
<TabItem value="optional" label="Optional">

- **extended** `boolean`

  Include extended hours trading sessions when returning *intraday* candles. Daily resolutions _never_ return extended hours candles.

  - Daily candles default: `false`.
  - Intraday candles default: `false`.

- **adjustsplits** `boolean`

  Adjust historical data for stock splits. Market Data uses the CRSP methodology for adjustment.

  - Daily candles default: `true`.
  - Intraday candles default: `false`.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  ll always be `ok` when there is data for the candles requested.

- **o** `array[number]`

  Open price.

- **h** `array[number]`

  High price.

- **l** `array[number]`

  Low price.

- **c** `array[number]`

  Close price.

- **v** `array[number]`

  Volume.

- **t** `array[number]`
  Candle time (Unix timestamp, UTC). Daily, weekly, monthly, yearly candles are returned without times.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no candles are found for the request.

- **nextTime** `number` optional

  Unix time of the next quote if there is no data in the requested period, but there is data in a subsequent period.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\stocks\earnings.mdx

---
title: Earnings tg p
sidebar_position: 6
tags:
  - "API: Premium"
---

Get historical earnings per share data or a future earnings calendar for a stock.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/stocks/earnings/{symbol}/
```

#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/stocks/earnings/AAPL/](https://api.marketdata.app/v1/stocks/earnings/AAPL/)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch("https://api.marketdata.app/v1/stocks/earnings/AAPL/")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/stocks/earnings/AAPL/"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="stockEarnings.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleStockEarningsRequest() {
	earningsReports, err := StockEarnings().Symbol("AAPL").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, report := range earningsReports {
		fmt.Println(report)
	}
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "symbol": ["AAPL"],
  "fiscalYear": [2023],
  "fiscalQuarter": [1],
  "date": [1672462800],
  "reportDate": [1675314000],
  "reportTime": ["before market open"],
  "currency": ["USD"],
  "reportedEPS": [1.88],
  "estimatedEPS": [1.94],
  "surpriseEPS": [-0.06],
  "surpriseEPSpct": [-3.0928],
  "updated": [1701690000]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **symbol** `string`

  The company's ticker symbol.

</TabItem>
<TabItem value="Optional" label="Optional">

- **from** `date`

  The earliest earnings report to include in the output. If you use countback, `from` is not required. Accepted timestamp inputs: ISO 8601, unix, spreadsheet.

- **to** `date`

  The latest earnings report to include in the output. Accepted timestamp inputs: ISO 8601, unix, spreadsheet.

- **countback** `number`

  Countback will fetch a specific number of earnings reports before `to`. If you use `from`, countback is not required.

- **date** `date`

  Retrieve a specific earnings report by date. Accepted timestamp inputs: ISO 8601, unix, spreadsheet.

- **report** `datekey`

  Retrieve a specific earnings report by date and quarter. Example: `2023-Q4`. This allows you to retrieve a 4th quarter value without knowing the company's specific fiscal year.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Will always be `ok` when there is data for the symbol requested.

- **symbol** `array[string]`

  The symbol of the stock.

- **fiscalYear** `array[number]`

  The fiscal year of the earnings report. This may not always align with the calendar year.

- **fiscalQuarter** `array[number]`

  The fiscal quarter of the earnings report. This may not always align with the calendar quarter.

- **date** `array[date]`

  The last calendar day that corresponds to this earnings report.

- **reportDate** `array[date]`

  The date the earnings report was released or is projected to be released.

- **reportTime** `array[string]`

  The value will be either `before market open`, `after market close`, or `during market hours`.

- **currency** `array[string]`

  The currency of the earnings report.

- **reportedEPS** `array[number]`

  The earnings per share reported by the company. Earnings reported are typically non-GAAP unless the company does not report non-GAAP earnings.

  :::tip

  GAAP (Generally Accepted Accounting Principles) earnings per share (EPS) count all financial activities except for discontinued operations and major changes in accounting methods. Non-GAAP EPS, on the other hand, typically doesn't include losses or devaluation of assets, and often leaves out irregular expenses like significant restructuring costs, large tax or legal charges, especially for companies not in the financial sector.
  :::

- **estimatedEPS** `array[number]`

  The average consensus estimate by Wall Street analysts.

- **surpriseEPS** `array[number]`

  The difference (in earnings per share) between the estimated earnings per share and the reported earnings per share.

- **surpriseEPSpct** `array[number]`

  The difference in percentage terms between the estimated EPS and the reported EPS, expressed as a decimal. For example, if the estimated EPS is 1.00 and the reported EPS is 1.20, the surpriseEPSpct would be 0.20 (or 20%).

- **updated** `array[date]`

  The date/time the earnings data for this ticker was last updated.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no earnings data can be found for the symbol.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\stocks\index.mdx

---
title: Stocks
slug: /stocks
sidebar_position: 6
---

Stock endpoints include numerous fundamental, technical, and pricing data.

## Root Endpoint For Stocks
```
https://api.marketdata.app/v1/stocks/
```

## Stocks Endpoints

import DocCardList from "@theme/DocCardList";
import { useCurrentSidebarCategory } from "@docusaurus/theme-common";

<DocCardList items={useCurrentSidebarCategory().items} />



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\stocks\news.mdx

---
title: News tg b
sidebar_position: 7
tags:
  - "API: Beta"
---

:::warning Beta Endpoint
The News endpoint is still in beta and has not yet been optimized for performance. Use caution before adding this endpoint in a prodution environment.
:::

Get news for a stock.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/stocks/news/{symbol}/
```

#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/stocks/news/AAPL/](https://api.marketdata.app/v1/stocks/news/AAPL/)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch("https://api.marketdata.app/v1/stocks/news/AAPL/")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/stocks/news/AAPL/"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="stockNews.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleStockNewsRequest_get() {
	news, err := StockNews().Symbol("AAPL").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, article := range news {
		fmt.Println(article)
	}
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s":"ok",
  "symbol": "AAPL",
  "headline": "Whoa, There! Let Apple Stock Take a Breather Before Jumping in Headfirst.",
  "content": "Apple is a rock-solid company, but this doesn't mean prudent investors need to buy AAPL stock at any price.",
  "source": "https://investorplace.com/2023/12/whoa-there-let-apple-stock-take-a-breather-before-jumping-in-headfirst/",
  "updated": 1703041200
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **symbol** `string`

  The company's ticker symbol.

</TabItem>
<TabItem value="Optional" label="Optional">

- **from** `date`

  The earliest news to include in the output. If you use countback, `from` is not required. Accepted timestamp inputs: ISO 8601, unix, spreadsheet.

- **to** `date`

  The latest news to include in the output. Accepted timestamp inputs: ISO 8601, unix, spreadsheet.

- **countback** `number`

  Countback will fetch a specific number of news before `to`. If you use `from`, countback is not required.

- **date** `date`

  Retrieve news for a specific day. Accepted timestamp inputs: ISO 8601, unix, spreadsheet.

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Will always be `ok` when there is data for the symbol requested.

- **symbol** `array[string]`

  The symbol of the stock.

- **headline** `array[string]`

  The headline of the news article.

- **content** `array[string]`

  The content of the article, if available.

  :::tip
  Please be aware that this may or may not include the full content of the news article. Additionally, it may include captions of images, copyright notices, syndication information, and other elements that may not be suitable for reproduction without additional filtering.
  :::

- **source** `array[url]`

  The source URL where the news appeared.

- **publicationDate** `array[date]`

  The date the news was published on the source website.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no news can be found for the symbol.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\stocks\quotes.mdx

---
title: Quotes
sidebar_position: 3
---

Get a real-time price quote for a stock.

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Endpoint
```
https://api.marketdata.app/v1/stocks/quotes/{symbol}/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/v1/stocks/quotes/AAPL/](https://api.marketdata.app/v1/stocks/quotes/AAPL/)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="app.js"
fetch("https://api.marketdata.app/v1/stocks/quotes/AAPL/")
  .then((res) => {
    console.log(res);
  })
  .catch((err) => {
    console.log(err);
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="app.py"
import requests

url = "https://api.marketdata.app/v1/stocks/quotes/AAPL/"
response = requests.request("GET", url)

print(response.text)
```

</TabItem>
<TabItem value="Go" label="Go">

```go title="stockQuote.go"

import (
  "fmt"

  api "github.com/MarketDataApp/sdk-go"
)

func ExampleStockQuoteRequest() {
	quotes, err := StockQuote().Symbol("AAPL").Get()
	if err != nil {
		fmt.Print(err)
		return
	}

	for _, quote := range quotes {
		fmt.Println(quote)
	}
}
```
</TabItem>
</Tabs>

## Response Example

```json
{
  "s": "ok",
  "symbol": ["AAPL"],
  "ask": [149.08],
  "askSize": [200],
  "bid": [149.07],
  "bidSize": [600],
  "mid": [149.07],
  "last": [149.09],
  "volume": [66959442],
  "updated": [1663958092]
}
```

## Request Parameters

<Tabs>
<TabItem value="required" label="Required" default>

- **symbol** `string`

  The company's ticker symbol.

</TabItem>
<TabItem value="Optional" label="Optional">

- **52week** `boolean`

  Enable the output of 52-week high and 52-week low data in the quote output. By default this parameter is `false` if omitted.

- **extended** `boolean`

  Control the inclusion of extended hours data in the quote output. Defaults to `true` if omitted. 

  - When set to `true`, the most recent quote is always returned, without regard to whether the market is open for primary trading or extended hours trading.
  - When set to `false`, only quotes from the primary trading session are returned. When the market is closed or in extended hours, a historical quote from the last closing bell of the primary trading session is returned instead of an extended hours quote. 

</TabItem>
</Tabs>

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Will always be `ok` when there is data for the symbol requested.

- **symbol** `array[string]`

  The symbol of the stock.

- **ask** `array[number]`

  The ask price of the stock.

- **askSize** `array[number]`

  The number of shares offered at the ask price.

- **bid** `array[number]`

  The bid price.

- **bidSize** `array[number]`

  The number of shares that may be sold at the bid price.

- **mid** `array[number]`

  The midpoint price between the ask and the bid.

- **last** `array[number]`

  The last price the stock traded at.

- **change** `array[number]`

  The difference in price in currency units compared to the closing price of the previous primary trading session.

- **changepct** `array[number]`

  The difference in price in percent, expressed as a decimal, compared to the closing price of the previous day. For example, a 3% change will be represented as 0.3.

:::note
  - When the market is open for primary trading, **change** and **changepct** are always calculated using the last traded price and the last primary session close. When the market is closed or in extended hours, this criteria is also used as long as `extended` is omitted or set to `true`.
  - When `extended` is set to `false`, and the market is closed or in extended hours, quotes from extended hours are not considered. The values for **change** and **changepct** will be calculated using the last two closing prices instead.
:::

- **52weekHigh** `array[number]`

  The 52-week high for the stock. This parameter is omitted unless the optional 52week request parameter is set to true.

- **52weekLow** `array[number]`

  The 52-week low for the stock. This parameter is omitted unless the optional 52week request parameter is set to true.

- **volume** `array[number]`

  The number of shares traded during the current session.

- **updated** `array[date]`

  The date/time of the current stock quote.

</TabItem>
<TabItem value="NoData" label="No Data">

- **s** `string`

  Status will be `no_data` if no quote can be found for the symbol.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\troubleshooting\authentication.md

---
title: Authentication
sidebar_position: 1
---

Authentication issues usually arise due to incorrect headers, omission of the authorization header, or problems with URL parameters. If you encounter a 401 error, it's usually related to issues with your `Authorization` header. The most common issues are:

- Incorrect token
- Invalid characters to separate the query string from the path
- Invalid characters to separate query parameters from each other

Troubleshooting authentication issues is crucial for ensuring uninterrupted access to our API services. Most authentication issues are related to header-based authentication, but URL parameter authentication can also be troublesome to users who are getting started with Market Data as their first REST API. This guide aims to provide you with steps to resolve common problems. 

:::tip
Even though it is more complex to set-up, we encourage all users to take the extra time required to configure header-based authentication for our API, as this is the most secure method of authentication.
:::

### Troubleshooting URL Parameter Authentication

Usually URL parameter authentication goes wrong because customers use **invalid characters to separate the query string from the path**. The correct character to use is `?` and the correct character to use to separate query parameters is `&`. If you use the wrong characters, the API will not be able to parse the query string correctly and will be unable to authenticate your request. Learn more about the correct format of the URL parameters [here](/api/troubleshooting/url-parameters).

For example, suppose your token was `token1234` and you were also using the `dateformat` parameter to request a timestamp as the output format for the time. For a stocks/quotes request, the correct URL would be:

```http
https://api.marketdata.app/v1/stocks/quotes/SPY/?token=token1234&dateformat=timestamp
```

- Note how the token is separated from the path by a `?` and the dateformat parameter is separated from the token by a `&`. 

The ordering of the parameters is not important. You do not need to put `token` as the first parameter. It would also be perfectly valid to use the following URL:

```http
https://api.marketdata.app/v1/stocks/quotes/SPY/?dateformat=timestamp&token=token1234
```

No matter the order of the parameters, the API will be able to parse the query string and authenticate your request **as long as the correct characters are used to separate the query string from the path and the query parameters from each other.**

### Troubleshooting Header Authentication

The most common issues customers face with header-based authentication are:

- Omission of the header
- Incorrect header name
- Invalid header format
- Incorrect token

#### Steps for Troubleshooting 401 Errors

1. **Test the Token with URL Parameter Authentication**
   
   ```bash
   curl -X GET "https://api.marketdata.app/v1/stocks/quotes/SPY/?token=YOUR_TOKEN"
   ```

Use CURL to test your token using URL parameter authentication. If it works, you know that your token is valid. If you are using a token that is not valid, you will receive a 401 error. If you are using a token that is valid, you will receive a `200 OK` response along with a stock quote.

2. **Inspect Request Headers**

To inspect the headers your application is sending, especially the `Authorization` header, use our dedicated [headers endpoint](/api/utilities/headers). This will help you identify any discrepancies in the headers that might be causing authentication issues.

```bash
curl -X GET "https://api.marketdata.app/headers/" -H "Authorization: Token YOUR_TOKEN"
```

Make a request to https://api.marketdata.app/headers/ from your application and save the headers. This endpoint will return a JSON response of the headers your application is sending, with sensitive headers like `Authorization` partially redacted for security. Compare the headers from your application's request to the expected headers. 

If your application's `Authorization` header is different from what you expect, there may be an issue with how your application is setting headers. If the headers match your expectations, the issue may lie elsewhere, possibly with the token itself.

3. **Log Response Headers and Submit a Helpdesk Ticket**
   
   ```bash
   curl -X GET "https://api.marketdata.app/v1/stocks/quotes/SPY/" -H "Authorization: Token YOUR_TOKEN" -i
   ```

Finally, we'll now make a header-authentication request using your token. Make a request using the CURL command above. If you receive a 401 error, the issue is with your token. If you receive a `200 OK` response, the issue is with your application's code. 

:::tip
If the issue persists, include the log data and the Ray ID (listed in the CF-Ray header) when you submit a helpdesk ticket. This will help our support team locate your specific request in our server logs and assist you more effectively.
:::

## Opening a Support Ticket

### When to Open a Ticket

Open a ticket if you experience persistent issues or errors that cannot be resolved through this troubleshooting guide.

### What to Include

Include the log data and the Ray ID for faster resolution. By attaching this information to your support ticket, it becomes much easier for our staff to understand and solve your ticket.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\troubleshooting\http-status-codes.md

---
title: HTTP Status Codes
sidebar_position: 2
---

The Market Data API uses standard HTTP status codes to respond to each request. By preparing your application to utilize these status codes, you can often times solve common errors, or retry failed requests.

## Successful Requests (2xx)

These are requests that are answered successfully.

:::caution
Some libraries are not prepared to handle HTTP 203 response codes as successful requests. Ensure the library you are using can accept a 203 response code the same way as a 200 response code.
:::

- `200 OK` - Successfully answered the request.
- `203 NON-AUTHORITATIVE INFORMATION` - Successfully served the request from our caching server. Treat this result the same as STATUS 200.
- `204 NO CONTENT` - Indicates a successful request for explicitly requested cached data, but our cache server lacks cached data for the symbol requested. Resend the request using the live data feed.

## Client Errors (4xx)

Client errors occur when Market Data cannot respond to a request due to a problem with the request. The request will need to be modified in order to get a different response.

:::tip
If you believe your request is correct and you received a 4xx reply in error, please ensure you log our complete response to your request, including the full response headers along with the complete JSON error message we deliver in our reply. Open a ticket at our help desk and provide this information to our support staff and we will investigate further.
:::

- `400 BAD REQUEST` - The API endpoint is not being used properly, often due to a parameter that cannot be parsed correctly (e.g., sending a string instead of a number or vice versa).
- `401 UNAUTHORIZED` - The token supplied with the request is missing, invalid, or cannot be used.
- `402 PAYMENT REQUIRED` - The requested action cannot be performed with your current plan, such as attempting to access historical data with a free plan or very old historical data with a Starter plan.
- `404 NOT FOUND` - No data exists for the requested symbol or time period. Consider trying a different symbol or time frame.
- `413 PAYLOAD TOO LARGE` - The request payload is too large. This is often due to requesting a time frame longer than 1 year for candle data. Resubmit the request with a time frame of 1 year or less.
- `429 TOO MANY REQUESTS` - The daily request limit for your account has been exceeded. New requests will be allowed at 9:30 AM ET (opening bell).
- `429 TOO MANY REQUESTS` - Concurrent request limit reached. You've reached the limit of 50 requests running simultaneously on our server. Please wait until they are finished to make more.

## Server Errors (5xx)

Server errors are used to indicate problems with Market Data's service. They are requests that appear to be properly formed, but can't be responded to due to some kind of problem with our servers. 

### Permanent Failures

- `500 INTERNAL SERVER ERROR` - An unknown server issue prevents Market Data from responding to your request. Open a ticket with the helpdesk and include the Ray ID of the request.

### Temporary Failures

Most 5xx errors are temporary and resolve themselves on their own. Please retry requests that receive 5xx errors at a later time and they will probably be successful.

- `502 BAD GATEWAY` - Market Data's API server does not respond to the gateway, indicating the API is offline or unreachable.
- `503 SERVICE UNAVAILABLE` - Market Data's API server is accessible but cannot fulfill the request, usually due to server overload. Retry the request in a few minutes.
- `504 GATEWAY TIMEOUT` - Market Data's load balancer received no response from the API, suggesting the request is taking too long to resolve. Retry in 1-2 minutes and report to the helpdesk if the issue persists.
- `509 API ENDPOINT OVERLOADED` - The endpoint is currently overloaded. Retry in a few minutes and report to the helpdesk if the issue continues for more than 15 minutes.
- `521 API ENDPOINT OFFLINE` - The Market Data API endpoint expected to respond is offline. Report to the helpdesk if this persists for more than 15 minutes.
- `524 A TIMEOUT OCCURRED` - The Market Data API failed to provide an HTTP response before the default 100-second connection timeout, possibly due to server overload or resource struggles. Contact support if this continues for more than 15 minutes.
- `529 DATABASE OFFLINE` - The database is offline, overloaded, or not responding. Contact support@marketdata.app or submit a ticket if this error persists for more than 15 minutes.
- `530 DATABASE ERROR` - The request resulted in a database error. Contact support@marketdata.app or submit a ticket with your API request details.
- `598 API GATEWAY OFFLINE` - The gateway server is not responding or is unavailable. Report to the helpdesk if this issue continues for more than 15 minutes.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\troubleshooting\index.mdx

---
title: Troubleshooting
slug: /troubleshooting
sidebar_position: 12
---

import DocCardList from "@theme/DocCardList";
import { useCurrentSidebarCategory } from "@docusaurus/theme-common";

<DocCardList items={useCurrentSidebarCategory().items} />



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\troubleshooting\logging.mdx

---
title: Logging
sidebar_position: 3
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

## Why Logging is Important

Logging our API's responses is crucial for monitoring the behavior of your application and troubleshooting problems, either with our API or your usage of the API.

### What Should Be Logged

Market Data responds to successful requests with either a 200 or 203 status code. Therefore, we recommend you log any response that doesn't have a 2xx status code. Successful responses may be logged if you wish, but normally this is not necessary.

When logging errors, the log should include the exact request made, Market Data's response, and the CF-Ray header.

## Logging Examples

<Tabs>
<TabItem value="NodeJS" label="NodeJS">

```js title="logger.js"
const axios = require("axios");
const fs = require("fs");

// Make the API request
axios
  .get("https://api.marketdata.app/v1/your_endpoint_here")
  .then((response) => {
    // Do nothing for successful responses
  })
  .catch((error) => {
    if (error.response.status !== 200 && error.response.status !== 203) {
      const logData = {
        request: error.config.method.toUpperCase() + " " + error.config.url,
        response: error.response.data,
        cfRayHeader: error.response.headers["cf-ray"] || "Not available",
      };
      // Save to a logfile
      fs.appendFileSync("api_error_log.json", JSON.stringify(logData) + "\n");
    }
  });
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="logger.py"
import requests
import json

# Make the API request
response = requests.get("https://api.marketdata.app/v1/any_endpoint_here")

# Check if the response is not 200 or 203
if response.status_code not in [200, 203]:
    log_data = {
        "request": response.request.method + " " + response.request.url,
        "response": response.content.decode("utf-8"),
        "cf_ray_header": response.headers.get("CF-Ray", "Not available")
    }
    # Save to a logfile
    with open("api_error_log.json", "a") as logfile:
        logfile.write(json.dumps(log_data) + "\n")
```

</TabItem>
</Tabs>

## The CF-Ray Header

### What is the CF-Ray Header

The CF-Ray header (otherwise known as a Ray ID) is a hashed value that encodes information about the Cloudflare data center and the request. Every request that travels through the Cloudflare network is assigned a unique Ray ID for tracking.

### Why It's Important

Since Market Data operates on the Cloudflare network, we log each of our API responses with Cloudflare's Ray ID. This allows us to have a unique identifier for each and every API request made to our systems. Additionally, we can also trace all requests through the Cloudflare network from our servers to your application.

:::tip
When opening a ticket at the customer helpdesk, if a Ray ID is provided to our support staff, we'll be able to identify the exact request you made and find why it produced an error.
:::

## Opening a Support Ticket

### When to Open a Ticket

Open a ticket if you experience persistent issues or errors that cannot be resolved through logging. For example, if you are making properly formatted requests to our systems and you are getting INTERNAL SERVER ERROR messages.

### What to Include

Include the log data and the CF-Ray header value for faster resolution. By attaching your log data to your support ticket, it becomes much easier for our staff to understand and solve your ticket.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\troubleshooting\service-outages.mdx

---
title: Service Outages
sidebar_position: 5
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

Market Data, as stated in our [terms of service](https://www.marketdata.app/terms/), makes no representation as to the reliability, availability, or timeliness of our service. **This is not just a standard disclaimer.** We have not yet been able to achieve 99.9% reliability, which is a metric we consider a minimum level of reliability that is needed to operate without a backup provider.

**Market Data is a low cost provider** and we have determined that cost, rather than reliability, is our key driver. While we hope to achieve 99.9% reliability in the future, our focus will remain on keeping down costs and avoiding price increases for our users.

:::tip Recommendation
We highly encourage users with mission critical applications to have a backup provider or utilize Market Data as their secondary provider. 
:::

## How To Confirm Downtime

We utilize the service UptimeRobot to independently monitor our real-time and historical APIs and the results of this monitoring is made available to the public at our [status page](https://www.marketdata.app/status/).

- Status Page: [https://www.marketdata.app/status/](https://www.marketdata.app/status/)

### Confirm Downtime Programmatically

Use the [/utilities/status/ endpoint](/api/utilities/status) to confirm the status of all Market Data services, including our APIs. This endpoint will remain online during outages and will send a JSON response that includes the status of all Market Data services. 

:::tip
This endpoint is ideal to allow for automatic switching between Market Data and your backup provider.
:::

<Tabs>
<TabItem value="NodeJS" label="NodeJS">

```js title="status.js"
// Importing the required library
const axios = require('axios');

// URL to the new JSON data
const url = "https://api.marketdata.app/status/";

// Service names for Historical Data API and Real-time Data API
const historicalDataApiName = "Historical Data API";
const realTimeDataApiName = "Real-time Data API";

// Function to check the status of the given service name
async function checkApiStatus(serviceName) {
    try {
        const response = await axios.get(url);
        const jsonData = response.data;

        if (jsonData.service.includes(serviceName)) {
            const index = jsonData.service.indexOf(serviceName);
            return jsonData.online[index] ? "Online" : "Offline";
        } else {
            return "Service name not found";
        }
    } catch (error) {
        console.error("Error fetching API status:", error);
        return "Failed to fetch API status";
    }
}

// Checking the status of Historical Data API and Real-time Data API
async function checkStatuses() {
    const historicalStatus = await checkApiStatus(historicalDataApiName);
    const realTimeStatus = await checkApiStatus(realTimeDataApiName);

    console.log(`Historical Data API: ${historicalStatus}`);
    console.log(`Real-time Data API: ${realTimeStatus}`);
}

checkStatuses();
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="status.py"
# Importing the required library
import requests

# URL to the new JSON data
url = "https://api.marketdata.app/status/"
json_data = requests.get(url).json()

# Service names for Historical Data API and Real-time Data API
historical_data_api_name = "Historical Data API"
real_time_data_api_name = "Real-time Data API"

# Function to check the status of the given service name
def check_api_status(service_name):
    if service_name in json_data["service"]:
        index = json_data["service"].index(service_name)
        return "Online" if json_data["online"][index] else "Offline"
    else:
        return "Service name not found"

# Checking the status of Historical Data API and Real-time Data API
historical_status = check_api_status(historical_data_api_name)
real_time_status = check_api_status(real_time_data_api_name)

print(f"Historical Data API: {historical_status}")
print(f"Real-time Data API: {real_time_status}")
```

</TabItem>
</Tabs>

## What To Do During Downtime

It is not necessary to advise us of downtime or service outages. We monitor the status of our systems and we investigate and respond to all service outages. During Market Data service outages, we encourage you to switch your systems over to your back-up provider until our systems come back online.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\troubleshooting\url-parameters.mdx

---
title: URL Parameters
sidebar_position: 4
---

## Introduction to URL Parameters

URL parameters, also known as query strings, are a way to pass information to a server as part of a URL. They are often used to filter or customize the response from the server. Understanding how to correctly build URL parameters is crucial for interacting with Market Data's APIs effectively.

### Structure of URL Parameters

A URL with parameters has the following structure:

<pre>
https://<span class="url-host">api.marketdata.app</span>/<span class="url-path">v1/stocks/quotes/SPY/</span>?<span class="url-query">token=token1234&dateformat=timestamp</span>
</pre>

- **Protocol**: `https://`
- **Host**: <span class="url-host">`api.marketdata.app`</span>
- **Path (or Endpoint)**: <span class="url-path">`/v1/stocks/quotes/SPY/`</span>
- **Query String**: Begins with a `?` and includes <span class="url-query">`token=token1234&dateformat=timestamp`</span>
  - `token` and `dateformat` are the names of the parameters.
  - `token1234` and `timestamp` are the values assigned to those parameters.
  - `&` is used to separate multiple parameters.

### Common Uses of URL Parameters in Market Data's APIs

- **Filtering**: Retrieve a subset of data based on specific criteria.
- **Formatting**: Change the format of the data returned by the API.
- **Authentication**: Send credentials or tokens to access API data.

## How to Build URL Parameters

When building URL parameters, follow these guidelines to ensure they are structured correctly:

1. **Start with the Endpoint URL**: Identify the base URL of the API endpoint you are interacting with.
2. **Add a Question Mark**: Follow the base URL with a `?` to start the query string.
3. **Append Parameters**: Add parameters in the format `key=value`. Use `&` to separate multiple parameters.
4. **Encode Special Characters**: Use URL encoding to handle special characters in keys or values.

### Example

Suppose you want to request stock quotes for `SPY` with a specific date format and token authentication:

```
https://api.marketdata.app/v1/stocks/quotes/SPY/?token=token1234&dateformat=timestamp
```

### Troubleshooting Common Mistakes

- **Incorrect Character Usage**: Ensure you use `?` to start and `&` to separate parameters.
- **Unencoded Characters**: Encode special characters like spaces (`%20`), plus (`%2B`), etc, using URL encoding.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\universal-parameters\columns.md

---
title: Columns
sidebar_position: 6
---

The columns parameter is used to limit the results of any endpoint to only the columns you need.

## Parameter

## Use Example

```
https://api.marketdata.app/v1/stocks/quotes/AAPL/?columns=ask,bid
```

## Response Example

```json
{ "ask": [152.14], "bid": [152.12] }
```

## Values

### string

Use a list of columns names separated by commas to limit the response to just the columns requested.

:::caution

When using the columns parameter the `s` status output is suppressed from the response.

:::



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\universal-parameters\date-format.md

---
title: Date Format
sidebar_position: 3
---

The dateformat parameter allows you specify the format you wish to receive date and time information in.

## Parameter

    dateformat=\<timestamp\|unix\|spreadsheet\>

## Use Example

    /candles/daily/AAPL?dateformat=timestamp

    /candles/daily/AAPL?dateformat=unix

    /candles/daily/AAPL?dateformat=spreadsheet

## Values

### timestamp

Receive dates and times as a timestamp. Market Data will return time stamped data in the timezone of the exchange. For example, closing bell on Dec 30, 2020 for the NYSE would be: **2020-12-30 16:00:00 -05:00**.

### unix

Receive dates and times in unix format (seconds after the unix epoch). Market Data will return unix date and time data. For example, closing bell on Dec 30, 2020 for the NYSE would be: **1609362000**.

### spreadsheet

Receive dates and times in spreadsheet format (days after the Excel epoch). For example, closing bell on Dec 30, 2020 for the NYSE would be: **44195.66667**. Spreadsheet format does not support time zones. All times will be returned in the local timezone of the exchange.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\universal-parameters\feed.md

---
title: Data Feed tg p
sidebar_position: 9
---

The `feed` parameter allows the user to modify the data feed used for the API's response, forcing it to use cached data.

Our API offers two types of data feeds: `live` and `cached`. These options are designed to meet diverse user needs, balancing between the immediacy of data and cost efficiency. Below is a detailed overview of each feed type, including examples and use-cases to help you choose the best option for your requirements.

:::info Premium Parameter
This parameter can only be used with paid plans. Free plans and trial plans do not have the ability to control their data feed. Free plans will always recieve delayed data.
:::

## Live Feed

The `live` feed provides real-time data, delivering the most current market information available. This option is ideal for scenarios requiring the latest data for immediate decision-making.

### Pricing for Live Feed

- Quotes: **1 credit per symbol** included in the response that has quote data (bid/ask/mid/last price).
- Candles: **1 credit per 1,000 candles** included in the response.
- Bulk Candles: **1 credit per symbol*** included in the response.
- Other Endpoints: **1 credit per response**.

### Requesting Live Data

To request real-time data, append `feed=live` to your API call or do nothing at all. If you omit the feed query parameter the live feed is used by default. Here's an example:

```http
GET https://api.marketdata.app/v1/options/chain/SPY/?feed=live
GET https://api.marketdata.app/v1/options/chain/SPY/
```

Both of these requests are equally valid and return the latest data for the specified symbol, ensuring you have up-to-the-second information.

## Cached Feed

The `cached` feed provides data that could be a few seconds to a few days old, offering a cost-effective solution for accessing large volumes of quote data. When you use cached data, there is no guarantee of how fresh the data will be. Tickers that are popular with Market Data customers are refreshed more often.

### Pricing for Cached Feed

- Quotes: **1 credit per request**, regardless of the number of symbols. This makes it an economical choice for bulk data retrieval using endpoints like [Option Chain](/api/options/chain) and [Bulk Stock Quotes](/api/stocks/bulkquotes).
- Historical Quotes: Unavailable
- Candles: Unavailable
- Bulk Candles: Unavailable
- Other Endpoints: Unavailable

### Use-Case for Cached Feed

The `cached` feed is perfect for users who need to access recent quote data across multiple symbols without the need for immediate pricing. It allows for significant cost savings, particularly when retrieving data for multiple symbols in a single request.

### Requesting Cached Data

To access the cached data, include `feed=cached` in your API request. For example:

```http
GET https://api.marketdata.app/v1/options/chain/SPY/?feed=cached
```

This query retrieves data from our cache, offering an affordable way to gather extensive data with a single credit.

### Cached Feed Response Codes

When the `feed=cached` parameter is added, the API's response codes are modified slightly. You will no longer get `200 OK` responses, but instead 203 and 204 responses:

- `203 NON-AUTHORITATIVE INFORMATION` - This response indicates the response was successful and served from our cache server. You can treat this the same as a 200 response.
- `204 NO CONTENT` - This response indicates that the request was correct and would ordinarly return a success response, but our caching server does not have any cache data for the symbol requested. Make a live request to fetch real-time data for this symbol.

## Feed Comparison

| Feature         | Live Feed                       | Cached Feed                    |
|-----------------|---------------------------------|--------------------------------|
| **Data Timeliness** | Real-time, up-to-the-second data | Data could be seconds to days old |
| **Pricing**         | 1 credit per symbol with quote data | 1 credit per request, regardless of symbol count |
| **Ideal Use-Case** | Time-sensitive decisions requiring the latest data | Large volumes of data at lower cost |
| **Default Option** | Yes (if `feed` parameter is omitted) | No (must specify `feed=cached`) |

- **Opt for the `live` feed** when you require the most current data for each symbol, and the immediate freshness of the data justifies the additional credits.
- **Select the `cached` feed** for bulk data retrieval or when working with a larger set of symbols, to capitalize on the cost efficiency of retrieving extensive data at a lower price.


# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\universal-parameters\format.md

---
title: Format
sidebar_position: 2
---

The format parameter is used to specify the format for your data. We support JSON and CSV formats. The default format is JSON.

## Parameter

    format=\<json\|csv\>

## Use Example

    /candles/daily/AAPL?format=json

    /candles/daily/AAPL?format=csv

## Values

### json (default)

Use JSON to format the data in Javascript Object Notation (JSON) format. This format is ideal for programmatic use of the data.

### csv

Use CSV to format the data in lightweight comma separated value (CSV) format. This format is ideal for importing the data into spreadsheets.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\universal-parameters\headers.md

---
title: Headers
sidebar_position: 7
---

The headers parameter is used to turn off headers when using CSV output.

## Parameter

    headers=\<true\|false\>

## Use Example

    /candles/daily/AAPL?headers=false&format=csv

## Values

### true (default)

If the headers argument is not used, by default headers are turned on.

### false

Turns headers off and returns just the data points.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\universal-parameters\human-readable.md

---
title: Human Readable
sidebar_position: 8
---

The human parameter will use human-readable attribute names in the JSON or CSV output instead of the standard camelCase attribute names. Use of this parameter will result in API output that can be loaded directly into a table or viewer and presented to an end-user with no further transformation required on the front-end.

## Parameter

    human=\<true\|false\>

## Use Example

    https://api.marketdata.app/v1/stocks/quotes/AAPL/?human=true

## Response Example

```json
{
  "Symbol": ["AAPL"],
  "Ask": [152.63],
  "Ask Size": [400],
  "Bid": [152.61],
  "Bid Size": [600],
  "Mid": [152.62],
  "Last": [152.63],
  "Volume": [35021819],
  "Date": [1668531422]
}
```

## Values

### True

The API will output human-readable attribute names instead of the standard camelCase attribute names. The output will be capitalized as a title, with the first letter of each major word capitalized. The `s` status response is also surpressed.

### False (default)

Output of attribute names will be according to API specifications using camelCase. If the `human` attribute is omitted, the default behavior is `false`.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\universal-parameters\limit.md

---
title: Limit
sidebar_position: 4
---

The `limit` parameter allows you to limit the number of results for a particular API call or override an endpoint’s default limits to get more data.

- Default Limit: 10,000
- Maximum Limit: 50,000

In the example below, the daily candle endpoint by default returns the last 252 daily bars. By using limit you could modify the behavior return the last two weeks or 10 years of data.

## Parameter

    limit=\<number\>

## Use Example

    /candles/daily/AAPL?limit=10

    /candles/daily/AAPL?limit=2520

## Values

### integer (required)

The limit parameter accepts any positive integer as an input.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\universal-parameters\offset.md

---
title: Offset
sidebar_position: 5
---

The offset parameter is used together with limit to allow you to implement pagination in your application. Offset will allow you to return values starting at a certain value.

## Parameter

    offset=\<number\>

## Use Example

    /candles/daily/AAPL?limit=10&offset=10

## Values

### integer (required)

The limit parameter accepts any positive integer as an input.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\universal-parameters\token.md

---
title: Token
sidebar_position: 1
---

The token parameter allows you to submit a read-only access token as a parameter. If your access token is write-enabled (authorized for trading), you may not use the token as a parameter, and must submit it in a header.

:::danger Security Warning
When submitting your token in a URL, your token is exposed in server logs, cached in your browser, or otherwise made available. We do not recommend using your token as a parameter. This should only be used as a last resort in when you are unable to submit your token in a header.
:::

## Parameter

    token=\<token\>

## Use Example

    https://api.marketdata.app/v1/stocks/quotes/SPY/?token=put-your-token-here

## Values

### token

Submit your read-only access token as a value.



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\utilities\headers.mdx

---
title: Headers
sidebar_position: 2
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

This endpoint allows users to retrieve a JSON response of the headers their application is sending, aiding in troubleshooting authentication issues, particularly with the Authorization header. 

:::tip
The values in sensitive headers such as `Authorization` are partially redacted in the response for security purposes.
:::

## Endpoint

```
https://api.marketdata.app/headers/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/headers/](https://api.marketdata.app/headers/)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="headersCheck.js"
fetch("https://api.marketdata.app/headers/")
  .then((res) => res.json())
  .then((json) => console.log(json))
  .catch((err) => console.log(err));
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="headersCheck.py"
import requests

url = "https://api.marketdata.app/headers/"
response = requests.get(url)

print(response.text)
```

</TabItem>
</Tabs>

## Response Example

```json
{
    "accept": "*/*",
    "accept-encoding": "gzip",
    "authorization": "Bearer *******************************************************YKT0",
    "cache-control": "no-cache",
    "cf-connecting-ip": "132.43.100.7",
    "cf-ipcountry": "US",
    "cf-ray": "85bc0c2bef389lo9",
    "cf-visitor": "{\"scheme\":\"https\"}",
    "connection": "Keep-Alive",
    "host": "api.marketdata.app",
    "postman-token": "09efc901-97q5-46h0-930a-7618d910b9f8",
    "user-agent": "PostmanRuntime/7.36.3",
    "x-forwarded-proto": "https",
    "x-real-ip": "53.43.221.49"
}
```

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **Headers** `object`

  A JSON object representing the headers received from the user's request. This object includes standard and custom headers along with their respective values.
</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>

This endpoint is particularly useful for debugging issues related to authentication by allowing users to see exactly what headers are being sent to the API.


# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\utilities\index.mdx

---
title: Utilities
slug: /utilities
sidebar_position: 10
---

These endpoints are designed to assist with API-related service issues, including checking the online status and uptime.

## Root Endpoint For Utilities
```
https://api.marketdata.app/
```

## Utilities Endpoints

import DocCardList from "@theme/DocCardList";
import { useCurrentSidebarCategory } from "@docusaurus/theme-common";

<DocCardList items={useCurrentSidebarCategory().items} />



# File: C:\Users\Iliya\Documents\GitHub\marketdataapp\documentation\api\utilities\status.mdx

---
title: API Status tg n
sidebar_position: 1
---

import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";

Check the current status of Market Data services and historical uptime. The status of the Market Data API is updated every 5 minutes. Historical uptime is available for the last 30 and 90 days.

:::tip
This endpoint will continue to respond with the current status of the Market Data API, even if the API is offline. This endpoint is public and does not require a token.
:::

## Endpoint

```
https://api.marketdata.app/status/
```
#### Method
```
GET
```
## Request Example

<Tabs>
<TabItem value="HTTP" label="HTTP" default>

**GET** [https://api.marketdata.app/status/](https://api.marketdata.app/status/)

</TabItem>
<TabItem value="NodeJS" label="NodeJS">

```js title="statusCheck.js"
fetch("https://api.marketdata.app/status/")
  .then((res) => res.json())
  .then((json) => console.log(json))
  .catch((err) => console.log(err));
```

</TabItem>
<TabItem value="Python" label="Python">

```python title="statusCheck.py"
import requests

url = "https://api.marketdata.app/status/"
response = requests.get(url)

print(response.text)
```

</TabItem>

</Tabs>

## Response Example

```json
{
  "s": "ok",
  "service": ["Customer Dashboard", "Historical Data API", "Real-time Data API", "Website"],
  "status": ["online", "online", "online", "online"],
  "online": [true, true, true, true],
  "uptimePct30d": [1, 0.99769, 0.99804, 1],
  "uptimePct90d": [1, 0.99866, 0.99919, 1],
  "updated": [1708972840, 1708972840, 1708972840, 1708972840]
}
```

## Response Attributes

<Tabs>
<TabItem value="Success" label="Success" default>

- **s** `string`

  Will always be `ok` when the status information is successfully retrieved.

- **service** `array[string]`

  The list of services being monitored.

- **status** `array[string]`

  The current status of each service (`online` or `offline`).

- **online** `array[boolean]`

  Boolean indicators for the online status of each service.

- **uptimePct30d** `array[number]`

  The uptime percentage of each service over the last 30 days.

- **uptimePct90d** `array[number]`

  The uptime percentage of each service over the last 90 days.

- **updated** `array[date]`

  The timestamp of the last update for each service's status.

</TabItem>
<TabItem value="Error" label="Error">

- **s** `string`

  Status will be `error` if the request produces an error response.

- **errmsg** `string`
  An error message.

</TabItem>
</Tabs>

For more details on the API's status, visit the [Market Data API Status Page](https://www.marketdata.app/status/).

