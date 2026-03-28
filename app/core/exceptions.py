from fastapi import HTTPException


class NotFoundException(HTTPException):
    def __init__(self, detail: str = "Not found"):
        super().__init__(status_code=404, detail=detail)



class ConflictException(HTTPException):
    def __init__(self, detail: str = "Already exists"):
        super().__init__(status_code=409, detail=detail)



class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "Access denied"):
        super().__init__(status_code=403, detail=detail)



class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(status_code=401, detail=detail)



class ValidationException(HTTPException):
    def __init__(self, detail: str = "Invalid input"):
        super().__init__(status_code=400, detail=detail)