# ====================================================================
# auth.py - accounts and sign-in: passwords are stored as bcrypt hashes
# (never plain text) and sessions use signed JWT tokens.
# ====================================================================
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt  # Direct usage
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# SECRET
SECRET_KEY = "supersecretkey" # In prod, use env var
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# # Check a login password against the stored (scrambled) hash.
def verify_password(plain_password, hashed_password):
    # bcrypt.checkpw requires bytes
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    
    return bcrypt.checkpw(plain_password, hashed_password)

# # Scramble a password for storage - plain passwords are never saved.
def get_password_hash(password):
    if isinstance(password, str):
        password = password.encode('utf-8')
    # Generate salt and hash
    hashed = bcrypt.hashpw(password, bcrypt.gensalt())
    return hashed.decode('utf-8')

# # Issue a signed login token (JWT) that proves who you are until it expires.
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# # Read the token on each request and work out which user it belongs to.
def get_current_user_id(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return int(user_id)
    except JWTError:
        raise credentials_exception
