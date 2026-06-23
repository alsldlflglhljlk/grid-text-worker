import asyncio
from inference_worker.ws_client import StreamingWorker
asyncio.run(StreamingWorker().run())
