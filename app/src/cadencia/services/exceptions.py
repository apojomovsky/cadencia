class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, identifier: str) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} not found: {identifier}")


class AmbiguousError(Exception):
    """Raised when a name query matches more than one person."""

    def __init__(self, query: str, candidates: list[str]) -> None:
        self.query = query
        self.candidates = candidates
        super().__init__(
            f"Ambiguous query '{query}' matched {len(candidates)} people: "
            + ", ".join(candidates)
        )


class ConflictError(Exception):
    """Raised on constraint violations (e.g., duplicate names)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
