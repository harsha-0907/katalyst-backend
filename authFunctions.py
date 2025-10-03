import jwt, os, time
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

# Replace with your actual secret key
SECRET_KEY = os.getenv("OPEN_API_KEY")
ALGORITHM = "HS256"

def encodeJWT(userName):
    userData = {
        "uId": userName,
        "timeStamp": int(time.time())
    }
    token = jwt.encode(userData, SECRET_KEY, algorithm=ALGORITHM)
    return token

def decodeJWT(token):
    try:
        decodedData = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decodedData
    except Exception as _e:
        return None

def isAuthenticated(authorization: Annotated[Optional[str], Header()] = None):
    if authorization is None:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    # Assuming token is passed as: "Bearer <token>"
    try:
        token = authorization.split(" ")[1]
    except IndexError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format"
        )

    decodedData = decodeJWT(token)
    if decodedData is not None:
        return decodedData.get("uId")
    else:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized access"
        )


