class BusinessError(Exception):
    def __init__(self, code, message, details=None, status=422):
        self.code, self.message, self.details, self.status = code, message, details or [], status
