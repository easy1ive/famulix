# Connectors

famulix uses offline mock connectors for calendar, notes, mail, and files to
enable fully offline testing without external dependencies.

## Connector Architecture

Connectors implement a common interface:

```python
from famulix.connectors import Connector

class Connector:
    def gather(self, date_range: tuple[str, str]) -> list[Event]:
        """Gather events from the source."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Check connector health."""
        ...
```

## Built-in Connectors

### CalendarConnector

Generates synthetic calendar events:

```python
from famulix.connectors import CalendarConnector

connector = CalendarConnector(seed=42)
events = connector.gather(("2026-03-01", "2026-03-31"))
```

Generates meetings, appointments, and reminders with realistic patterns.

### NotesConnector

Generates synthetic note events:

```python
from famulix.connectors import NotesConnector

connector = NotesConnector(seed=42)
events = connector.gather(("2026-03-01", "2026-03-31"))
```

Generates personal notes, memos, and observations.

### MailConnector

Generates synthetic email events:

```python
from famulix.connectors import MailConnector

connector = MailConnector(seed=42)
events = connector.gather(("2026-03-01", "2026-03-31"))
```

Generates incoming/outgoing emails with realistic patterns.

### FilesConnector

Generates synthetic file access events:

```python
from famulix.connectors import FilesConnector

connector = FilesConnector(seed=42)
events = connector.gather(("2026-03-01", "2026-03-31"))
```

Generates file creation, modification, and access events.

## Connector Hub

The `ConnectorHub` manages multiple connectors:

```python
from famulix.connectors import ConnectorHub

hub = ConnectorHub(seed=42)
hub.register("calendar", CalendarConnector(seed=42))
hub.register("notes", NotesConnector(seed=42))
hub.register("mail", MailConnector(seed=42))
hub.register("files", FilesConnector(seed=42))

# Gather from all connectors
all_events = hub.gather_all(("2026-03-01", "2026-03-31"))
```

### Health Reports

Check all connector health:

```python
health = hub.health_report()
for name, status in health.items():
    print(f"{name}: {status['status']}")
```

## Determinism

All connectors are fully deterministic:
- Same seed → identical events
- Same date range → identical output
- No network calls or external dependencies

This enables reproducible testing and CI validation.

## Custom Connectors

Implement custom connectors for specific use cases:

```python
class CustomConnector(Connector):
    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def gather(self, date_range: tuple[str, str]) -> list[Event]:
        events = []
        # Generate custom events
        return events

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "connector": "custom"}
```

## CLI Usage

```bash
# List available connectors
famulix connectors list

# Check connector health
famulix connectors health

# Gather events from a connector
famulix connectors gather calendar --start 2026-03-01 --end 2026-03-31
```
