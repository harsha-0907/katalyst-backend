
import os, uuid, json
from composio import Composio
from composio_openai import OpenAIProvider
from datetime import datetime
from openai import OpenAI
from fastapi import FastAPI, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated
from datetime import datetime
from dotenv import load_dotenv
from authFunctions import *

load_dotenv()
API_KEY = os.getenv("API_KEY")
AUTH_CONFIG_ID = os.getenv("AUTH_CONFIG_ID")
OPEN_API_KEY = os.getenv("OPEN_API_KEY")
users = {}
origins = ["*"]

authComposio = Composio(api_key=API_KEY)
aiComposio = Composio(provider=OpenAIProvider(), api_key=API_KEY)

openai = OpenAI(api_key=OPEN_API_KEY)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/auth/login")
async def authUser():
    uId = uuid.uuid4().hex
    connectionRequest = authComposio.connected_accounts.initiate(
        user_id=uId,
        auth_config_id=AUTH_CONFIG_ID,
        config={"auth_scheme": "OAUTH2"},
        callback_url=F"https://8000-firebase-assignment-katalyst-1759460792100.cluster-va5f6x3wzzh4stde63ddr3qgge.cloudworkstations.dev/auth/authenticated/{uId}"
    )
    redirectUrl = connectionRequest.redirect_url

    return {
        "statusCode": 200,
        "message": redirectUrl
    }

@app.get("/auth/authenticated/{tempId}")
async def callback(request: Request, tempId: str):
    headers = dict(request.headers)
    queryParams = dict(request.query_params)
    
    referer = headers.get("referer", None)
    uId = queryParams.get("connectedAccountId", None)

    if referer == "https://accounts.google.com/" and uId is not None:
        token = encodeJWT(tempId)

        return {
            "statusCode": 200,
            "token": token
        }

    else:
        return {
            "statusCode": 501,
            "message": "Unable to process request"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

