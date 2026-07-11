import asyncio

async def wait_and_print(str):
  await asyncio.sleep(1)
  print(str)

async def main():
  tasks = []

  for i in range(1, 10):
    tasks.append(asyncio.create_task(wait_and_print(i)))

  for task in tasks:
    await task

  #await asyncio.gather(*tasks)

asyncio.run(main())
