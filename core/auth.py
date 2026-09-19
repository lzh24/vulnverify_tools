"""Bearer Token authentication middleware for tool services."""

from fastapi import Request, HTTPException


class AuthMiddleware:
    """Bearer token validation middleware."""

    def __init__(self, token: str):
        self.token = token

    async def __call__(self, request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authorization header"
            )

        provided_token = auth_header.split(" ")[1]
        if provided_token != self.token:
            raise HTTPException(
                status_code=403,
                detail="Invalid authentication token"
            )
