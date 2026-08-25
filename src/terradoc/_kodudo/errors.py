"""Error types for the inlined kodudo rendering library."""


class KodudoError(Exception):
    pass


class ConfigError(KodudoError):
    pass


class DataError(KodudoError):
    pass


class RenderError(KodudoError):
    pass
