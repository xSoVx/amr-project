class RulesValidationError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


class FHIRValidationError(Exception):
    def __init__(self, detail: str, issues: list[dict] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.issues = issues or []

