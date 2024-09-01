import os
from fastapi import FastAPI
from dotenv import load_dotenv
from forwarder import main
load_dotenv()
code_file = os.environ.get("CODE_FILE")

app = FastAPI()


@app.get("/code/{code}")
async def set_code(code: int):
     print(code_file)
     f = open(code_file, "w")
     f.write(str(code))
     return code

@app.get("/run")
async def run():
     await main()


@app.get("/ping")
def run():
     return "PING!"

