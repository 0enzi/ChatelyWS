import os
from jose import JWTError, jwt

ACCESS_TOKEN_EXPIRE_MINUTES = 3000  # 30 minutes
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days
ALGORITHM = "HS256"

JWT_SECRET_KEY = os.environ['JWT_SECRET_KEY']     # should be kept secret
JWT_REFRESH_SECRET_KEY = os.environ['JWT_REFRESH_SECRET_KEY']      # should be kept secret

async def get_current_user(token: str = Depends(oauth2_scheme),  db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    # user = get_user(fake_users_db, username=token_data.username)
    user = db.query(UserModel).filter(UserModel.email ==token_data.username).first()
    if user is None:
        raise credentials_exception
    return user
