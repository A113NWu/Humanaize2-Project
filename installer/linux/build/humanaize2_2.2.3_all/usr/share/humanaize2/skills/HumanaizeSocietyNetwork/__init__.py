"""
Humanaize Society Network Skill Package
"""

try:
    from .skill_handler import HumanaizeSocietyNetwork, execute_skill
    from .network_engine import NetworkEngine
    from .friend_manager import FriendManager
    from .thought_exchange import ThoughtExchange
    COMPONENTS_AVAILABLE = True
except ImportError:
    try:
        from skill_handler import HumanaizeSocietyNetwork, execute_skill
        from network_engine import NetworkEngine
        from friend_manager import FriendManager
        from thought_exchange import ThoughtExchange
        COMPONENTS_AVAILABLE = True
    except ImportError:
        COMPONENTS_AVAILABLE = False

__all__ = [
    'HumanaizeSocietyNetwork',
    'execute_skill',
    'NetworkEngine',
    'FriendManager',
    'ThoughtExchange'
]

__version__ = '1.0.0'
__author__ = 'Humanaize Team'