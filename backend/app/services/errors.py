class NotFoundError(Exception):
    """A resource doesn't exist, or belongs to another user. The API maps this to 404."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found")
        self.resource = resource
