import streamlit as st
from typing import Dict, List, Any, Optional

class StateManager:
    """Manages Streamlit session state variables."""
    
    @staticmethod
    def init_state():
        """Initialize all session state variables with defaults."""
        defaults = {
            'planning_complete': False,
            'planning_result': None,
            'negotiation_messages': [],
            'negotiation_log': [],
            'features_data': None,
            'teams_data': None,
            'data_loaded': False,
            'planning_started': False,
            'negotiations_finished': False,
            'planning_status': {},
            'planning_progress': None,
            'config': {},
            'negotiation_processed_count': 0,
            'negotiation_accepted_count': 0,
            'negotiation_rejected_count': 0,
            'total_stories': 0
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """Get a value from session state safely."""
        return st.session_state.get(key, default)

    @staticmethod
    def set(key: str, value: Any):
        """Set a value in session state."""
        st.session_state[key] = value

    @staticmethod
    def update_negotiation_stats(processed: int, accepted: int, rejected: int):
        """Update negotiation statistics."""
        st.session_state.negotiation_processed_count = processed
        st.session_state.negotiation_accepted_count = accepted
        st.session_state.negotiation_rejected_count = rejected

    @staticmethod
    def add_log_entry(entry: Dict[str, Any]):
        """Add an entry to the negotiation log."""
        if 'negotiation_log' not in st.session_state:
            st.session_state.negotiation_log = []
        st.session_state.negotiation_log.append(entry)

    @staticmethod
    def reset_planning():
        """Reset planning state but keep loaded data if possible."""
        st.session_state.planning_complete = False
        st.session_state.negotiations_finished = False
        st.session_state.planning_result = None
        st.session_state.negotiation_messages = []
        st.session_state.negotiation_log = []
        st.session_state.planning_started = False
        st.session_state.planning_status = {}
        st.session_state.planning_progress = None
        st.session_state.negotiation_processed_count = 0
        st.session_state.negotiation_accepted_count = 0
        st.session_state.negotiation_rejected_count = 0

    @staticmethod
    def clear_all_data():
        """Clear all data and reset application state."""
        StateManager.reset_planning()
        st.session_state.data_loaded = False
        st.session_state.features_data = None
        st.session_state.teams_data = None

