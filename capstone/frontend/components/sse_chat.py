import json
from typing import Generator

import requests
from sseclient import SSEClient


def stream_agent(base_url: str, session_id: str) -> Generator[str, None, None]:
    """Stream text chunks from the backend SSE endpoint.

    Parameters
    ----------
    base_url: str
        The FastAPI service base URL, e.g. http://localhost:8000
    session_id: str
        The session identifier to stream from

    Yields
    ------
    str
        Incremental text chunks suitable for direct UI rendering
    """
    url = f"{base_url.rstrip('/')}/sessions/{session_id}/stream"
    with requests.get(url, stream=True, timeout=300) as response:
        response.raise_for_status()
        client = SSEClient(response)
        for event in client.events():
            if not event.data:
                continue
            try:
                payload = json.loads(event.data)
            except Exception:
                payload = event.data
            yield str(payload)


