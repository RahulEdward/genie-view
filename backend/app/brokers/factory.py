"""
Broker Factory
Runtime broker selection and instantiation
"""

from typing import Dict, Optional, Type

from app.brokers.base import BrokerAdapter
from app.brokers.angelone.adapter import AngelOneAdapter
from app.config import settings


# Registry of available brokers
BROKER_REGISTRY: Dict[str, Type[BrokerAdapter]] = {
    "angelone": AngelOneAdapter,
    # Add more brokers here:
    # "zerodha": ZerodhaAdapter,
    # "upstox": UpstoxAdapter,
}


def get_broker(
    broker_name: Optional[str] = None,
    api_key: Optional[str] = None
) -> BrokerAdapter:
    """
    Get broker adapter instance.
    
    Args:
        broker_name: Broker name (default from settings)
        api_key: API key for the broker
    
    Returns:
        BrokerAdapter instance
    
    Raises:
        ValueError: If broker not found in registry
    """
    name = broker_name or settings.default_broker
    name = name.lower()
    
    if name not in BROKER_REGISTRY:
        available = ", ".join(BROKER_REGISTRY.keys())
        raise ValueError(
            f"Broker '{name}' not found. Available brokers: {available}"
        )
    
    broker_class = BROKER_REGISTRY[name]
    
    # Get API key from parameter or settings
    broker_api_key = api_key
    if not broker_api_key:
        if name == "angelone":
            broker_api_key = settings.angelone_api_key
    
    if not broker_api_key:
        raise ValueError(f"API key required for broker '{name}'")
    
    return broker_class(api_key=broker_api_key)


def get_available_brokers() -> list:
    """Get list of available broker names"""
    return list(BROKER_REGISTRY.keys())


def register_broker(name: str, broker_class: Type[BrokerAdapter]) -> None:
    """
    Register a new broker adapter.
    
    Args:
        name: Broker name (lowercase)
        broker_class: BrokerAdapter subclass
    """
    BROKER_REGISTRY[name.lower()] = broker_class


def is_broker_available(name: str) -> bool:
    """Check if broker is available"""
    return name.lower() in BROKER_REGISTRY
