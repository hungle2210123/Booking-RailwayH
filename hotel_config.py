"""
HOTEL CONFIGURATION
Centralized hotel/accommodation management configuration
"""

# Hotel/Accommodation definitions
ACCOMMODATIONS = {
    '118 Hang Bac Hostel': {
        'name': '118 Hang Bac Hostel',
        'display_name': '118 Hang Bạc',
        'capacity': 4,
        'address': '118 Hang Bạc, Hà Nội',
        'color': '#28a745',  # Green
        'icon': '🏨',
        'is_default': True,
        'active': True
    },
    '18 Hang Be': {
        'name': '18 Hang Be',
        'display_name': '18 Hàng Bè',
        'capacity': 2,
        'address': '18 Hàng Bè, Hà Nội',
        'color': '#17a2b8',  # Blue
        'icon': '🏘️',
        'is_default': False,
        'active': True
    }
}

# Total system capacity
TOTAL_ROOMS = sum(acc['capacity'] for acc in ACCOMMODATIONS.values() if acc['active'])
MAX_ROOMS_PER_DAY = TOTAL_ROOMS  # For backward compatibility

# Helper functions
def get_active_accommodations():
    """Get list of active accommodations"""
    return {k: v for k, v in ACCOMMODATIONS.items() if v['active']}

def get_accommodation_choices():
    """Get accommodation choices for forms (value, display_name)"""
    return [(k, v['display_name']) for k, v in ACCOMMODATIONS.items() if v['active']]

def get_default_accommodation():
    """Get default accommodation name"""
    for k, v in ACCOMMODATIONS.items():
        if v.get('is_default'):
            return k
    return list(ACCOMMODATIONS.keys())[0]

def get_accommodation_capacity(accommodation_name):
    """Get capacity for a specific accommodation"""
    return ACCOMMODATIONS.get(accommodation_name, {}).get('capacity', 1)

def get_accommodation_color(accommodation_name):
    """Get color for a specific accommodation"""
    return ACCOMMODATIONS.get(accommodation_name, {}).get('color', '#6c757d')

def get_total_capacity():
    """Get total system capacity"""
    return TOTAL_ROOMS

# Export for easy import
__all__ = [
    'ACCOMMODATIONS',
    'TOTAL_ROOMS',
    'MAX_ROOMS_PER_DAY',
    'get_active_accommodations',
    'get_accommodation_choices',
    'get_default_accommodation',
    'get_accommodation_capacity',
    'get_accommodation_color',
    'get_total_capacity'
]
