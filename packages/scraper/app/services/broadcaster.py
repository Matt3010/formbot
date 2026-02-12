import pusher
from app.config import settings


class Broadcaster:
    """Broadcast events directly to Soketi (Pusher-compatible) from Python."""

    _instance = None

    def __init__(self):
        self.client = pusher.Pusher(
            app_id=settings.pusher_app_id,
            key=settings.pusher_app_key,
            secret=settings.pusher_app_secret,
            host=settings.pusher_host,
            port=settings.pusher_port,
            ssl=False,
        )

    @classmethod
    def get_instance(cls) -> "Broadcaster":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def trigger(self, channel: str, event: str, data: dict):
        """Send an event to a Soketi channel."""
        try:
            self.client.trigger(channel, event, data)
        except Exception as e:
            print(f"[Broadcaster] Failed to trigger {event} on {channel}: {e}")

    def trigger_execution(self, user_id: int, execution_id: str, event: str, data: dict):
        """Broadcast an execution event to both the user channel and execution channel."""
        data["execution_id"] = str(execution_id)
        self.trigger(f"private-tasks.{user_id}", event, data)
        self.trigger(f"private-execution.{execution_id}", event, data)

    def trigger_analysis(self, analysis_id: str, event: str, data: dict):
        """Broadcast an AI analysis event (private channel)."""
        data["analysis_id"] = str(analysis_id)
        self.trigger(f"private-analysis.{analysis_id}", event, data)
