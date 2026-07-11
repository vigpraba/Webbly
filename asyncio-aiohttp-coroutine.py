import asyncio, aiohttp


#Example 1
async def test(number):
    await asyncio.sleep(number)
    return "test"


async def main():
    sleep_time = 2
    result = await test(sleep_time)
    print(result)


async def fetch(session, url):
    async with session.get(url) as response:
        return await response.text()

async def another_main():
    urls = [f"https://example.com/page/{i}" for i in range(100)]
    async with aiohttp.ClientSession() as session:
        # All 100 requests in flight at once
        results = await asyncio.gather(*(fetch(session, u) for u in urls))
    print(results)


#Example 2
async def fetch_data(delay: int, system_id: str):
    print(f"System {system_id}: Fetching data...")
    # Simulated non-blocking network I/O
    await asyncio.sleep(delay) 
    print(f"System {system_id}: Data received!")
    return {"id": system_id, "status": "success"}

async def main1():
    # Directly awaiting a coroutine executes it sequentially
    result = await fetch_data(2, "A")
    print(f"Result: {result}")

# Starts the event loop and executes the main coroutine
asyncio.run(main1())
