from typing import Callable, Dict, List, Any
from app.core.cache import cache_delete, CacheKeys
import asyncio

_handlers: Dict[str, List[Callable]] = {}


def register(event: str, handler: Callable):
    if event not in _handlers:
        _handlers[event] = []
    
    _handlers[event].append(handler)



async def publish(event: str, payload: dict):
    handlers = _handlers.get(event, [])

    for handler in handlers:
        if asyncio.iscoroutinefunction(handler):
            await handler(payload)
        else:
            handler(payload)



async def send_notification(payload: dict):
    print(f"[Notification] New appointment: {payload}")



async def update_region_stats(payload: dict) -> None:
    print(f"[H3] +1 appointment in region {payload.get('h3_index')}")
    await cache_delete(CacheKeys.ANALYTICS_DEMAND)
    await cache_delete(CacheKeys.ANALYTICS_DOCTORS)
    print("[CACHE] Analytics cache cleared")

async def send_cancellation_notice(payload: dict):
    print(f"[CANCEL] Appointment cancelled: {payload}")



def setup():
    register("appointment_created", send_notification)
    register("appointment_created", update_region_stats)

    register("appointment_cancelled", send_cancellation_notice)
    
        