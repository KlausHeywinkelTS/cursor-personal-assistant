"""Ruft die heutigen Termine über einen Power-Automate-Flow ab.

Usage:
    py src/get_schedule_for_today.py
"""

import json
from typing import Any

import requests


FLOW_URL = (
    "https://default38e736cd1e0548a5adeb5ae85d3376.ae.environment.api.powerplatform.com:443/powerautomate/automations/direct/cu/01/workflows/cddc20a17fff4d87b40f72159722013a/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=2zsMVkwqbKEQkLZhk4D22xJN0SAZ7ReTceTnnRD1PHU"
)
PAYLOAD = {"name": "Klaus"}


def get_schedule_for_today() -> list[dict[str, Any]]:
    """Return the appointments delivered by the Power-Automate flow."""
    response = requests.post(FLOW_URL, json=PAYLOAD, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError("Unerwartetes Antwortformat des Termin-Workflows")
    return [appointment for appointment in data if isinstance(appointment, dict)]


def main() -> None:
    print(json.dumps(get_schedule_for_today(), ensure_ascii=False))


if __name__ == "__main__":
    main()
