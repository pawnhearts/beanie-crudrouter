from hashlib import sha256
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from fastapi import HTTPException, Response
from fastapi_sessions.backends.implementations import InMemoryBackend
from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi_sessions.session_verifier import SessionVerifier
from pydantic import BaseModel

from models import User, RoleEnum


class SessionData(BaseModel):
    email: str
    role: RoleEnum
    login: str


class UserAuth(BaseModel):
    """User register and login auth."""

    email: str
    password: str


cookie_params = CookieParameters()

# Uses UUID
cookie = SessionCookie(
    cookie_name="cookie",
    identifier="general_verifier",
    auto_error=True,
    secret_key="DONOTUSE",
    cookie_params=cookie_params,
)
backend = InMemoryBackend[UUID, SessionData]()


class BasicVerifier(SessionVerifier[UUID, SessionData]):
    def __init__(
            self,
            *,
            identifier: str,
            auto_error: bool,
            backend: InMemoryBackend[UUID, SessionData],
            auth_http_exception: HTTPException,
    ):
        self._identifier = identifier
        self._auto_error = auto_error
        self._backend = backend
        self._auth_http_exception = auth_http_exception

    @property
    def identifier(self):
        return self._identifier

    @property
    def backend(self):
        return self._backend

    @property
    def auto_error(self):
        return self._auto_error

    @property
    def auth_http_exception(self):
        return self._auth_http_exception

    def verify_session(self, model: SessionData) -> bool:
        """If the session exists, it is valid"""
        return True


verifier = BasicVerifier(
    identifier="general_verifier",
    auto_error=True,
    backend=backend,
    auth_http_exception=HTTPException(status_code=403, detail="invalid session"),
)

auth_router = APIRouter(tags=["Auth"])


def hash_password(password: str):
    return sha256(password.encode("utf8")).digest()


@auth_router.post("/login")
async def login(response: Response, user_auth: UserAuth) -> SessionData:
    session = uuid4()
    user = await User.find_one(
        User.email == user_auth.email, User.role != RoleEnum.client
    )
    if user is None or hash_password(user_auth.password) != user.stored_password:
        raise HTTPException(status_code=401, detail="Bad email or password")
    data = SessionData(email=user.email, role=user.role, login=user.login)
    await backend.create(session, data)
    cookie.attach_to_response(response, session)
    return data


def has_permission(model, action):
    def has_permissionfo(user: SessionData = Depends(verifier), obj=None):
        if not user:
            raise HTTPException(status_code=403, detail="Access Denied")
