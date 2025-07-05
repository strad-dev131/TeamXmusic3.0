import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        logging.FileHandler("logs.txt"),  # Changed from log.txt to logs.txt
        logging.StreamHandler(),
    ],
)

logging.getLogger("httpx").setLevel(logging.CRITICAL) 
logging.getLogger("pyrogram").setLevel(logging.CRITICAL)
logging.getLogger("pytgcalls").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("async").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.CRITICAL)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
