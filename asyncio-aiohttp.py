import asyncio, aiohttp


#for single request
async def main():
    async with aiohttp.ClientSession() as ssn:
        async with ssn.get('https://example.com') as response:
            html = await response.text()
            print(html)

sem = asyncio.Semaphore(10)
#for multiple requests at once
async def fetch(session, url):
    async with sem:
        async with session.get(url) as response:
            print(f"Fetching {url}...")
            return await response.text()

async def another_main():
    urls = [f"https://example.com/page/{i}" for i in range(100)]
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*(fetch(session, u) for u in urls))
        await session.close()
    print(results)

#asyncio.run(main())
asyncio.run(another_main())


#ClientSession - Reusable http client
#await resp.text() wait for the response
#asyncio.gather - run many API calls together [Main guy]
#asyncio.Semaphore - limit how many API calls run at once
#* just unpacks them



