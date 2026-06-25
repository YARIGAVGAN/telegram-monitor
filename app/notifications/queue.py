import asyncio

notification_queue = asyncio.Queue(maxsize=1000)

async def push(item):
    await notification_queue.put(item)

async def pop():
    return await notification_queue.get()