"""
User Activity Tracker Service
=============================

Tracks active users and their real-time activities for admin monitoring.

Features:
- Track active user sessions
- Record user activities (diagram generation, node palette, etc.)
- Clean up stale sessions automatically
- Thread-safe operations

Author: lycosa9527
Made by: MindSpring Team
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from collections import defaultdict
import threading

# Beijing timezone (UTC+8)
BEIJING_TIMEZONE = timezone(timedelta(hours=8))

def get_beijing_now() -> datetime:
    """Get current datetime in Beijing timezone (UTC+8)"""
    return datetime.now(BEIJING_TIMEZONE)

logger = logging.getLogger(__name__)


class UserActivityTracker:
    """
    Tracks active users and their activities in real-time.
    
    Thread-safe singleton for tracking user sessions and activities.
    Uses RLock (reentrant lock) to allow nested lock acquisition.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(UserActivityTracker, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Use RLock (reentrant lock) to allow nested calls like record_activity -> start_session
        self._lock = threading.RLock()
        self._active_sessions: Dict[str, Dict] = {}  # session_id -> session data
        self._user_sessions: Dict[int, Set[str]] = defaultdict(set)  # user_id -> set of session_ids
        self._activity_history: List[Dict] = []  # Recent activity log
        self._max_history = 1000  # Keep last 1000 activities
        self._session_timeout = timedelta(minutes=30)  # Session expires after 30 min inactivity
        
        # Activity type mappings
        self._activity_types = {
            'diagram_generation': 'Generating Diagram',
            'node_palette': 'Using Node Palette',
            'autocomplete': 'Auto-complete',
            'voice_conversation': 'Voice Conversation',
            'ai_assistant': 'AI Assistant',
            'export_png': 'Exporting PNG',
            'export_dingtalk': 'Exporting DingTalk',
            'login': 'Login',
            'logout': 'Logout',
            'page_view': 'Viewing Page',
        }
        
        self._initialized = True
        logger.info("UserActivityTracker initialized")
    
    def start_session(
        self,
        user_id: int,
        user_phone: str,
        user_name: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        reuse_existing: bool = True
    ) -> str:
        """
        Start tracking a new user session.
        
        Args:
            user_id: User ID
            user_phone: User phone number
            user_name: Optional user name
            session_id: Optional custom session ID (generated if not provided)
            ip_address: Optional IP address
            reuse_existing: If True, reuse existing active session for this user
        
        Returns:
            Session ID
        """
        import uuid
        
        with self._lock:
            # If reuse_existing and no session_id provided, try to find existing session
            if reuse_existing and session_id is None:
                existing_session = self._find_user_session(user_id)
                if existing_session:
                    # Update existing session info if provided
                    if user_name or ip_address:
                        session = self._active_sessions[existing_session]
                        if user_name:
                            session['user_name'] = user_name
                        if ip_address:
                            session['ip_address'] = ip_address
                        session['last_activity'] = get_beijing_now()
                    logger.debug(f"Reusing existing session {existing_session[:8]} for user {user_id}")
                    return existing_session
            
            # Create new session
            if session_id is None:
                session_id = f"session_{uuid.uuid4().hex[:12]}"
            
            now = get_beijing_now()
            self._active_sessions[session_id] = {
                'session_id': session_id,
                'user_id': user_id,
                'user_phone': user_phone,
                'user_name': user_name,
                'ip_address': ip_address,
                'created_at': now,
                'last_activity': now,
                'current_activity': None,
                'activity_count': 0,
                'activities': []
            }
            
            self._user_sessions[user_id].add(session_id)
            
            # Log activity only for new sessions
            self._log_activity(user_id, user_phone, 'login', session_id=session_id)
        
        logger.debug(f"Started session {session_id[:8]} for user {user_id} ({user_phone})")
        return session_id
    
    def end_session(self, session_id: Optional[str] = None, user_id: Optional[int] = None):
        """
        End a user session.
        
        Args:
            session_id: Session ID to end (if provided, ends specific session)
            user_id: User ID to end all sessions for (if session_id not provided)
        """
        with self._lock:
            if session_id:
                # End specific session
                if session_id not in self._active_sessions:
                    return
                
                session = self._active_sessions[session_id]
                user_id = session['user_id']
                user_phone = session['user_phone']
                
                # Log logout activity
                self._log_activity(user_id, user_phone, 'logout', session_id=session_id)
                
                # Remove from active sessions
                del self._active_sessions[session_id]
                
                # Remove from user sessions
                if user_id in self._user_sessions:
                    self._user_sessions[user_id].discard(session_id)
                    if not self._user_sessions[user_id]:
                        del self._user_sessions[user_id]
                
                logger.debug(f"Ended session {session_id[:8]}")
            elif user_id:
                # End all sessions for user
                if user_id not in self._user_sessions:
                    return
                
                sessions_to_end = list(self._user_sessions[user_id])
                for sid in sessions_to_end:
                    if sid in self._active_sessions:
                        session = self._active_sessions[sid]
                        user_phone = session['user_phone']
                        self._log_activity(user_id, user_phone, 'logout', session_id=sid)
                        del self._active_sessions[sid]
                
                del self._user_sessions[user_id]
                logger.debug(f"Ended all {len(sessions_to_end)} session(s) for user {user_id}")
    
    def record_activity(
        self,
        user_id: int,
        user_phone: str,
        activity_type: str,
        details: Optional[Dict] = None,
        session_id: Optional[str] = None
    ):
        """
        Record a user activity.
        
        Args:
            user_id: User ID
            user_phone: User phone number
            activity_type: Type of activity (see _activity_types)
            details: Optional activity details
            session_id: Optional session ID (will find or create if not provided)
        """
        with self._lock:
            now = get_beijing_now()
            
            # Find or create session
            if session_id is None:
                # Find existing session for user
                session_id = self._find_user_session(user_id)
                if session_id is None:
                    session_id = self.start_session(user_id, user_phone)
            
            # Update session
            if session_id in self._active_sessions:
                session = self._active_sessions[session_id]
                session['last_activity'] = now
                session['current_activity'] = activity_type
                session['activity_count'] += 1
                
                # Add to activity history
                activity_entry = {
                    'type': activity_type,
                    'details': details or {},
                    'timestamp': now
                }
                session['activities'].append(activity_entry)
                
                # Keep only last 50 activities per session
                if len(session['activities']) > 50:
                    session['activities'] = session['activities'][-50:]
            
            # Log activity
            self._log_activity(user_id, user_phone, activity_type, details, session_id)
    
    def _find_user_session(self, user_id: int) -> Optional[str]:
        """Find an active session for a user."""
        if user_id in self._user_sessions:
            sessions = self._user_sessions[user_id]
            # Filter to only active sessions (in case some were cleaned up)
            active_sessions = [sid for sid in sessions if sid in self._active_sessions]
            # Return most recent session
            if active_sessions:
                return max(active_sessions, key=lambda sid: self._active_sessions[sid].get('last_activity', datetime.min))
        return None
    
    def _log_activity(
        self,
        user_id: int,
        user_phone: str,
        activity_type: str,
        details: Optional[Dict] = None,
        session_id: Optional[str] = None
    ):
        """Log activity to history."""
        activity_label = self._activity_types.get(activity_type, activity_type)
        
        entry = {
            'timestamp': get_beijing_now(),
            'user_id': user_id,
            'user_phone': user_phone,
            'activity_type': activity_type,
            'activity_label': activity_label,
            'details': details or {},
            'session_id': session_id
        }
        
        self._activity_history.append(entry)
        
        # Keep only last N activities
        if len(self._activity_history) > self._max_history:
            self._activity_history = self._activity_history[-self._max_history:]
    
    def get_active_users(self) -> List[Dict]:
        """
        Get list of currently active users.
        
        Returns:
            List of active user sessions with activity info
        """
        with self._lock:
            self._cleanup_stale_sessions()
            
            active_users = []
            for session_id, session in self._active_sessions.items():
                user_data = {
                    'session_id': session_id,
                    'user_id': session['user_id'],
                    'user_phone': session['user_phone'],
                    'user_name': session.get('user_name'),
                    'ip_address': session.get('ip_address'),
                    'current_activity': session.get('current_activity'),
                    'current_activity_label': self._activity_types.get(
                        session.get('current_activity', ''),
                        session.get('current_activity', 'Unknown')
                    ),
                    'last_activity': session['last_activity'].isoformat(),
                    'activity_count': session['activity_count'],
                    'session_duration': str(get_beijing_now() - session['created_at']).split('.')[0]
                }
                active_users.append(user_data)
            
            # Sort by last activity (most recent first)
            active_users.sort(key=lambda x: x['last_activity'], reverse=True)
            
            return active_users
    
    def get_recent_activities(self, limit: int = 100) -> List[Dict]:
        """
        Get recent activity history.
        
        Args:
            limit: Maximum number of activities to return
        
        Returns:
            List of recent activities
        """
        with self._lock:
            activities = self._activity_history[-limit:]
            return [
                {
                    'timestamp': act['timestamp'].isoformat(),
                    'user_id': act['user_id'],
                    'user_phone': act['user_phone'],
                    'activity_type': act['activity_type'],
                    'activity_label': act['activity_label'],
                    'details': act['details'],
                    'session_id': act.get('session_id')
                }
                for act in reversed(activities)
            ]
    
    def get_stats(self) -> Dict:
        """
        Get overall statistics.
        
        Returns:
            Dict with stats: active_users_count, total_sessions, recent_activities_count
        """
        with self._lock:
            self._cleanup_stale_sessions()
            
            return {
                'active_users_count': len(self._active_sessions),
                'unique_users_count': len(self._user_sessions),
                'total_sessions': len(self._active_sessions),
                'recent_activities_count': len(self._activity_history),
                'timestamp': get_beijing_now().isoformat()
            }
    
    def _cleanup_stale_sessions(self):
        """Remove sessions that have been inactive for too long."""
            now = get_beijing_now()
        stale_sessions = []
        
        for session_id, session in self._active_sessions.items():
            if now - session['last_activity'] > self._session_timeout:
                stale_sessions.append(session_id)
        
        for session_id in stale_sessions:
            self.end_session(session_id)
    
    def get_user_sessions(self, user_id: int) -> List[Dict]:
        """
        Get all active sessions for a specific user.
        
        Args:
            user_id: User ID
        
        Returns:
            List of session data
        """
        with self._lock:
            if user_id not in self._user_sessions:
                return []
            
            sessions = []
            for session_id in self._user_sessions[user_id]:
                if session_id in self._active_sessions:
                    sessions.append(self._active_sessions[session_id])
            
            return sessions


# Global singleton instance
_tracker_instance: Optional[UserActivityTracker] = None
_tracker_lock = threading.Lock()


def get_activity_tracker() -> UserActivityTracker:
    """Get the global UserActivityTracker instance."""
    global _tracker_instance
    
    if _tracker_instance is None:
        with _tracker_lock:
            if _tracker_instance is None:
                _tracker_instance = UserActivityTracker()
    
    return _tracker_instance

