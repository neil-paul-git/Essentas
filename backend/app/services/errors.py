class NotFoundError(Exception):
    """A resource doesn't exist, or belongs to another user. The API maps this to 404."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found")
        self.resource = resource


class InvalidInputError(Exception):
    """The request is well-formed but can't be acted on. The API maps this to 422."""


class ServiceUnavailableError(Exception):
    """An upstream service we depend on can't answer right now. The API maps this to 503."""
