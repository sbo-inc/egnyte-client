import json
import os
from typing import Any, cast

from egnyte_client.client import EgnyteClient

# =============================================================================
# CLASS: ClientContext
# =============================================================================


class ClientContext:
    """
    Lazy client holder attached to the Click context object.
    """

    def __init__(self) -> None:
        self._client: EgnyteClient | None = None

    @property
    def client(self) -> EgnyteClient:
        """
        Construct the underlying client on first access.

        The domain and tokens are sourced from the standard `EGNYTE_*`
        environment variables the client itself reads. Extra request headers
        may be supplied as a JSON object in `EGNYTE_API_HEADERS`.
        `EGNYTE_API_TIMEOUT` (seconds) and `EGNYTE_API_RETRIES`
        (connection-retry count) override the client defaults for unattended
        runs.
        """
        if self._client is None:
            raw = os.environ.get("EGNYTE_API_HEADERS")
            headers: dict[str, str] = (
                cast(dict[str, Any], json.loads(raw)) if raw else {}
            )

            kwargs: dict[str, Any] = {}
            timeout = os.environ.get("EGNYTE_API_TIMEOUT")
            if timeout:
                kwargs["timeout"] = float(timeout)
            retries = os.environ.get("EGNYTE_API_RETRIES")
            if retries:
                kwargs["retries"] = int(retries)

            self._client = EgnyteClient(headers=headers, **kwargs)
        return self._client
