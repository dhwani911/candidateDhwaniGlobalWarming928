class DomainError(Exception):
    pass


class InvalidTransition(DomainError):
    pass


class FaultReferenceError(DomainError):
    pass


class NotFoundError(DomainError):
    pass