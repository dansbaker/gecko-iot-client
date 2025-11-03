from enum import Enum
from typing import Optional, List, Dict, Any
from .abstract_zone import AbstractZone, ZoneType


class FlowZoneInitiator(Enum):
    """Enum for flow zone initiators"""
    # Add specific initiator values as needed
    pass


@AbstractZone.register_zone_type(ZoneType.FLOW_ZONE)
class FlowZone(AbstractZone):
    """State representation for flow zone v1 with validation"""
    
    def __init__(self, zone_id: str, config: Dict[str, Any]):
        """Initialize FlowZone with zone_id and config."""
        # Set default name if not provided
        if 'name' not in config or config['name'] is None:
            config['name'] = f"Pump {zone_id}"
            
        super().__init__(
            id=zone_id,
            zone_type=ZoneType.FLOW_ZONE,
            name=config.get('name'),
            **{k: v for k, v in config.items() if k not in ['name']}
        )
        
        # Initialize flow zone specific attributes with defaults
        self.active: Optional[bool] = getattr(self, 'active', None)
        self.speed: Optional[float] = getattr(self, 'speed', None)
        self.initiators_: Optional[List[FlowZoneInitiator]] = getattr(self, 'initiators_', None)
        
        # Validate speed if present
        if self.speed is not None:
            if not isinstance(self.speed, (int, float)):
                raise ValueError(f"Flow speed must be a number, got {type(self.speed).__name__}: {self.speed}")
            self._validate_speed(self.speed)
    
    def _validate_speed(self, speed: float) -> None:
        """Validate speed is within acceptable range."""
        if not (0.0 <= speed <= 100.0):
            raise ValueError(f"Flow speed {speed}% must be between 0.0 and 100.0")
    
    @property
    def initiators(self) -> Optional[List[FlowZoneInitiator]]:
        return self.initiators_
    
    def get_flow_state(self) -> Dict[str, Any]:
        """Get the current flow state as a simple dictionary."""
        return {
            'active': self.active,
            'speed': self.speed,
            'has_initiators': bool(self.initiators_)
        }
    
    def _get_runtime_state_fields(self) -> set:
        """Runtime state fields for flow zones."""
        return {'active', 'speed'}
    
    def _get_field_mappings(self) -> Dict[str, str]:
        """
        Flow zone specific field mappings.
        
        Returns:
            Dictionary mapping external field names to internal field names
        """
        return {
            'isActive': 'active',
            'flowSpeed': 'speed',
            'pumpSpeed': 'speed',
            'running': 'active',
            'enabled': 'active',
        }
    
    def set_speed(self, speed: float, active: Optional[bool] = True) -> None:
        """Set flow speed with validation and optional active state."""
        self._validate_speed(speed)
        self.speed = speed
        if active is not None:
            self.active = active
        self._publish_desired_state({'speed': speed, 'active': self.active})

    def activate(self) -> None:
        """Activate this zone."""
        self._publish_desired_state({'active': True})

    def deactivate(self) -> None:
        """Deactivate this zone."""
        self._publish_desired_state({'active': False})