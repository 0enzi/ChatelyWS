import ast
import os
from fastapi import HTTPException
from jose import JWTError, jwt
from fastapi import status

ACCESS_TOKEN_EXPIRE_MINUTES = 3000  # 30 minutes
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days
ALGORITHM = "HS256"

JWT_SECRET_KEY = os.environ['JWT_SECRET_KEY']     # should be kept secret
JWT_REFRESH_SECRET_KEY = os.environ['JWT_REFRESH_SECRET_KEY']      # should be kept secret

def get_current_user(token: str):

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user = ast.literal_eval(payload.get("sub"))
        username: str = user['username']
        if username is None or user is None:
            return False
        return user
    except JWTError:
        return False
        
    
