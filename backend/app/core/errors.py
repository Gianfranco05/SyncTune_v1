class ExternalResponseError(Exception):
    """Spotify/YouTube answered 2xx but with a shape we don't recognize.

    Raised instead of letting a bare KeyError/TypeError surface as a raw 500
    — this is the failure mode when an external API changes (Spotify's
    Feb 2026 playlist migration renamed several fields). main.py maps it to
    a friendly 502.
    """
