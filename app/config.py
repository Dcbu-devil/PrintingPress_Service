import os
import warnings
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_SECRET = "change-this-secret-key-later"


class Settings:
    SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
    )

    # Frontend URL for CORS (optional, for production)
    FRONTEND_URL = os.getenv("FRONTEND_URL", None)

    # Cookie security settings.
    # For localhost: COOKIE_SECURE=false, COOKIE_SAMESITE=lax
    # For production HTTPS: COOKIE_SECURE=true, COOKIE_SAMESITE=none
    COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")


settings = Settings()

if settings.SECRET_KEY == _DEFAULT_SECRET:
    warnings.warn(
        "SECRET_KEY is using the default value. "
        "Set a strong SECRET_KEY in your .env file for production!",
        stacklevel=2,
    )