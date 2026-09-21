class TrackerError(Exception):
    """Expected Tracker or validation error."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        self.code = code
        super().__init__(message)
