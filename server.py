
import os, uuid, json
from composio import Composio
from composio_openai import OpenAIProvider
from datetime import datetime
from openai import OpenAI
from fastapi import FastAPI, Request, Depends, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated
from datetime import datetime
from dotenv import load_dotenv
from authFunctions import *

load_dotenv()
users = {}
API_KEY = os.getenv("API_KEY")
AUTH_CONFIG_ID = os.getenv("AUTH_CONFIG_ID")
OPEN_API_KEY = os.getenv("OPEN_API_KEY")
BACKEND_URL = os.getenv("BACKEND_URL")
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

@app.get("/auth/login")
async def authUser():
    global BACKEND_URL, users
    uId = uuid.uuid4().hex
    users[uId] = None
    connectionRequest = authComposio.connected_accounts.initiate(
        user_id=uId,
        auth_config_id=AUTH_CONFIG_ID,
        config={"auth_scheme": "OAUTH2"},
        callback_url=f"{BACKEND_URL}/auth/callback/{uId}"
    )
    redirectUrl = connectionRequest.redirect_url
    if redirectUrl:
        return {
            "statusCode": 200,
            "url": redirectUrl,
            "uId": uId
        }
    else:
        return {
            "statusCode": 500,
            "url": "Unable to generate URL"
        }

@app.get("/auth/callback/{tempId}")
async def callback(request: Request, tempId: str):
    global users
    headers = dict(request.headers)
    queryParams = dict(request.query_params)
    
    referer = headers.get("referer", None)
    uId = queryParams.get("connectedAccountId", None)
    if referer == "https://accounts.google.com/" and uId is not None:
        # To check if it is coming from google
        token = encodeJWT(tempId)
        users[tempId] = token

        response = JSONResponse(content={"message": "Redirect Successful. Please close this tab to continue"})
        return response

    else:
        return {
            "statusCode": 501,
            "message": "Unable to process request"
        }

@app.post("/auth/creds")
async def fetchCreds(uId: str):
    global users
    if uId in users:
        token = users[uId]
        response = JSONResponse(content={"statusCode": 200, "token": f"Bearer {token}"})
        del(users[uId])
        
    else:
        response = JSONResponse(content={"statusCode": 401, "message": "Auth Un-Successful"})

    return response

@app.get("/chat")
async def chat(uId: Annotated[str, Depends(isAuthenticated)], query: str):
    if query.strip() == "":
        return {
            "statusCode": 200,
            "result": []
        }

    # Get current date
    now = datetime.utcnow()
    today = now.date()
    
    # Set default time range: September 2025 onwards
    time_min = datetime(2025, 9, 1, 0, 0, 0).isoformat() + 'Z'
    time_max = datetime(2025, 12, 31, 23, 59, 59).isoformat() + 'Z'
    
    tools = aiComposio.tools.get(
        user_id=uId,
        tools=["GOOGLECALENDAR_EVENTS_LIST"]
    )

    date_analysis = openai.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a date interpreter. Analyze the user's query and determine the date range they want.\n"
                    f"Today's date is: {today.isoformat()}\n\n"
                    "Return JSON with this exact structure:\n"
                    "{\n"
                    '  "timeMin": "YYYY-MM-DDTHH:MM:SSZ",\n'
                    '  "timeMax": "YYYY-MM-DDTHH:MM:SSZ",\n'
                    '  "interpretation": "brief explanation of date range"\n'
                    "}\n\n"
                    "Examples:\n"
                    "- 'tomorrow' -> tomorrow's start (00:00) to end (23:59)\n"
                    "- 'next week' -> start of next week to end of next week\n"
                    "- 'this month' -> start of current month to end of current month\n"
                    "- 'October' -> Oct 1st to Oct 31st of current year\n"
                    "- If no specific date mentioned, use September 1, 2025 to December 31, 2025\n"
                )
            },
            {
                "role": "user",
                "content": f"User query: {query}"
            }
        ]
    )
    
    try:
        date_info = json.loads(date_analysis.choices[0].message.content)
        time_min = date_info.get("timeMin", time_min)
        # time_max = date_info.get("timeMax", time_max)
        # print(f"Date interpretation: {date_info.get('interpretation', 'N/A')}")
        print(f"Fetching events from {time_min} to {time_max}")
    except Exception as e:
        print(f"Date parsing error: {e}, using default range")

    tool_result = openai.chat.completions.create(
        model="gpt-4o-mini",
        tools=tools,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Use the GOOGLECALENDAR_EVENTS_LIST tool to fetch calendar events.\n"
                    "ALWAYS include these parameters when calling the tool:\n"
                    f"- timeMin: {time_min}\n"
                    f"- timeMax: {time_max}\n"
                    "- maxResults: 50\n"
                    "- singleEvents: true\n"
                    "- orderBy: startTime"
                )
            },
            {
                "role": "user",
                "content": f"Fetch all calendar events between {time_min} and {time_max}. Context: {query}"
            }
        ]
    )

    tool_response = aiComposio.provider.handle_tool_calls(
        user_id=uId,
        response=tool_result
    )

    # print("Tool response:", tool_response)
    calendar_data_json = json.dumps(tool_response if tool_response else {})

    formatted_result = openai.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that formats calendar data into JSON.\n\n"
                    "Return a JSON object with a 'data' key containing an array.\n"
                    "Each array item must be either an 'event' object or a 'message' object.\n\n"
                    "Event object schema:\n"
                    "{\n"
                    '  "type": "event",\n'
                    '  "title": "string",\n'
                    '  "time": "ISO 8601 format (e.g., 2025-10-03T14:00:00Z)",\n'
                    '  "duration": number (in minutes),\n'
                    '  "attendees": ["email1", "email2"],\n'
                    '  "description": "string or null",\n'
                    '  "isCompleted": boolean\n'
                    "}\n\n"
                    "Message object schema:\n"
                    "{\n"
                    '  "type": "message",\n'
                    '  "message": "string"\n'
                    "}\n\n"
                    "Rules:\n"
                    f"- Today's date is {today.isoformat()}\n"
                    "- Calculate duration by finding difference between start and end times in minutes\n"
                    "- Extract attendee emails from the attendees array\n"
                    "- Set isCompleted to true if event end time is before today, false otherwise\n"
                    "- Use the 'summary' field as the title\n"
                    "- Use the 'description' field if available, otherwise set to null\n"
                    "- IMPORTANT: Determine if user wants a LIST of events or DETAILS about event(s):\n"
                    "  * If asking for a list (e.g., 'show meetings', 'what's tomorrow', 'list events'): return event objects with type='event'\n"
                    "  * If asking for details/info about specific event(s) (e.g., 'details of meeting', 'tell me about', 'what is'): return message object with type='message' containing the details\n"
                    "- If no events found, return: {\"data\": [{\"type\": \"message\", \"message\": \"No events found for the specified time period\"}]}\n"
                    "- Extract ONLY the events from the 'items' array in the calendar data\n"
                    "- Filter to only include events that match the user's query context"
                )
            },
            {
                "role": "user",
                "content": (
                    f"Calendar data: {calendar_data_json}\n\n"
                    f"User query context: {query}\n"
                    f"Date range: {time_min} to {time_max}\n\n"
                    "Extract and format all relevant events."
                )
            }
        ]
    )

    try:
        result_content = formatted_result.choices[0].message.content
        # print(f"GPT Response: {result_content}")
        
        result_content = result_content.strip()
        if result_content.startswith('```json'):
            result_content = result_content[7:]
        elif result_content.startswith('```'):
            result_content = result_content[3:]
        if result_content.endswith('```'):
            result_content = result_content[:-3]
        result_content = result_content.strip()
        
        parsed_result = json.loads(result_content)
        
        # Handle different response formats
        if isinstance(parsed_result, dict) and 'data' in parsed_result:
            result_data = parsed_result['data']
        elif isinstance(parsed_result, list):
            result_data = parsed_result
        else:
            result_data = [parsed_result]
        
        return {
            "statusCode": 200,
            "result": result_data
        }
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Raw content: {result_content}")
        return {
            "statusCode": 500,
            "result": [{"message": "Error parsing calendar data"}]
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "result": [{"message": f"Error: {str(e)}"}]
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

