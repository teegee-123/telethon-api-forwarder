import os
import asyncio 
from fastapi import FastAPI
from dotenv import load_dotenv
from forwarder import main, getCodeFromFile
from telethon.sync import TelegramClient, events

load_dotenv()
code_file = os.environ.get("CODE_FILE")
session = os.environ.get("SESSION")
api_id = os.environ.get("API_ID") 
api_hash = os.environ.get("API_HASH")


app = FastAPI()

client = TelegramClient(session, api_id, api_hash)
@app.get("/code/{code}")
def set_code(code: int):
     print(code_file)
     f = open(code_file, "w")
     f.write(str(code))
     f.close()
     return getCodeFromFile(0)

@app.get("/run")
def run():
     asyncio.run(main(client))
     return "Started"


@app.get("/ping")
def run():
     return "PING!"


@app.get("/stop")
async def run():
     await client.disconnect()
     return "Stopped"
