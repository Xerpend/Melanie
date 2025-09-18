"""
Session management for Melanie CLI.

Handles session persistence, recovery, and state management
for long-running coding tasks and project context.
"""

import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from uuid import uuid4

try:
    from .config import CLIConfig
except ImportError:
    from config import CLIConfig


@dataclass
class SessionInfo:
    """Information about a CLI session."""
    id: str
    name: str
    project_dir: str
    created_at: str
    last_accessed: str
    status: str  # 'active', 'completed', 'failed', 'paused'
    tasks_completed: int = 0
    tasks_total: int = 0
    current_task: Optional[str] = None


class SessionManager:
    """
    Manages CLI sessions for persistence and recovery.
    
    Provides functionality to create, save, load, and manage
    coding sessions with full state preservation.
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize session manager.
        
        Args:
            config_dir: Custom config directory (uses default if None)
        """
        self.config = CLIConfig(config_dir)
        self.sessions_dir = self.config.get_session_dir()
        self.sessions_index_file = self.sessions_dir / "index.json"
        
        # Load sessions index
        self._sessions_index: Dict[str, SessionInfo] = {}
        self._load_sessions_index()
    
    def _load_sessions_index(self):
        """Load the sessions index from disk."""
        if self.sessions_index_file.exists():
            try:
                with open(self.sessions_index_file, 'r') as f:
                    index_data = json.load(f)
                    self._sessions_index = {
                        session_id: SessionInfo(**session_data)
                        for session_id, session_data in index_data.items()
                    }
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load sessions index: {e}")
                self._sessions_index = {}
    
    def _save_sessions_index(self):
        """Save the sessions index to disk."""
        try:
            index_data = {
                session_id: asdict(session_info)
                for session_id, session_info in self._sessions_index.items()
            }
            with open(self.sessions_index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save sessions index: {e}")
    
    async def create_session(self, name: str, project_dir: Path) -> Dict[str, Any]:
        """
        Create a new session.
        
        Args:
            name: Session name
            project_dir: Project directory path
            
        Returns:
            Session data dictionary
        """
        session_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Create session info
        session_info = SessionInfo(
            id=session_id,
            name=name,
            project_dir=str(project_dir),
            created_at=now,
            last_accessed=now,
            status='active'
        )
        
        # Create session data
        session_data = {
            'id': session_id,
            'name': name,
            'project_dir': str(project_dir),
            'created_at': now,
            'last_accessed': now,
            'status': 'active',
            'context': {
                'current_request': None,
                'execution_plan': None,
                'agent_results': [],
                'file_changes': [],
                'test_results': [],
                'user_preferences': {}
            },
            'history': []
        }
        
        # Save session
        await self._save_session_data(session_id, session_data)
        
        # Update index
        self._sessions_index[session_id] = session_info
        self._save_sessions_index()
        
        return session_data
    
    async def load_session(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Load a session by name.
        
        Args:
            name: Session name
            
        Returns:
            Session data dictionary or None if not found
        """
        # Find session by name
        session_id = None
        for sid, session_info in self._sessions_index.items():
            if session_info.name == name:
                session_id = sid
                break
        
        if not session_id:
            return None
        
        # Load session data
        session_data = await self._load_session_data(session_id)
        if session_data:
            # Update last accessed time
            now = datetime.now(timezone.utc).isoformat()
            session_data['last_accessed'] = now
            self._sessions_index[session_id].last_accessed = now
            
            await self._save_session_data(session_id, session_data)
            self._save_sessions_index()
        
        return session_data
    
    async def save_session(self, session_data: Dict[str, Any]):
        """
        Save session data.
        
        Args:
            session_data: Session data dictionary
        """
        session_id = session_data['id']
        
        # Update last accessed time
        now = datetime.now(timezone.utc).isoformat()
        session_data['last_accessed'] = now
        
        # Save session data
        await self._save_session_data(session_id, session_data)
        
        # Update index
        if session_id in self._sessions_index:
            self._sessions_index[session_id].last_accessed = now
            self._sessions_index[session_id].status = session_data.get('status', 'active')
            self._save_sessions_index()
    
    async def delete_session(self, name: str) -> bool:
        """
        Delete a session by name.
        
        Args:
            name: Session name
            
        Returns:
            True if session was deleted, False if not found
        """
        # Find session by name
        session_id = None
        for sid, session_info in self._sessions_index.items():
            if session_info.name == name:
                session_id = sid
                break
        
        if not session_id:
            return False
        
        # Delete session file
        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
        
        # Remove from index
        del self._sessions_index[session_id]
        self._save_sessions_index()
        
        return True
    
    async def list_sessions(self) -> List[str]:
        """
        List all available sessions.
        
        Returns:
            List of session names
        """
        return [session_info.name for session_info in self._sessions_index.values()]
    
    async def get_session_info(self, name: str) -> Optional[SessionInfo]:
        """
        Get session information by name.
        
        Args:
            name: Session name
            
        Returns:
            SessionInfo object or None if not found
        """
        for session_info in self._sessions_index.values():
            if session_info.name == name:
                return session_info
        return None
    
    async def cleanup_old_sessions(self, days: int = 30):
        """
        Clean up sessions older than specified days.
        
        Args:
            days: Number of days to keep sessions
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        sessions_to_delete = []
        
        for session_id, session_info in self._sessions_index.items():
            try:
                last_accessed = datetime.fromisoformat(session_info.last_accessed)
                if last_accessed < cutoff_date:
                    sessions_to_delete.append(session_id)
            except ValueError:
                # Invalid date format, mark for deletion
                sessions_to_delete.append(session_id)
        
        # Delete old sessions
        for session_id in sessions_to_delete:
            session_file = self.sessions_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
            del self._sessions_index[session_id]
        
        if sessions_to_delete:
            self._save_sessions_index()
    
    async def _save_session_data(self, session_id: str, session_data: Dict[str, Any]):
        """Save session data to file."""
        session_file = self.sessions_dir / f"{session_id}.json"
        try:
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save session data: {e}")
    
    async def _load_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session data from file."""
        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load session data: {e}")
            return None
    
    async def update_session_progress(
        self,
        session_data: Dict[str, Any],
        tasks_completed: int,
        tasks_total: int,
        current_task: Optional[str] = None
    ):
        """
        Update session progress information.
        
        Args:
            session_data: Session data dictionary
            tasks_completed: Number of completed tasks
            tasks_total: Total number of tasks
            current_task: Current task description
        """
        session_id = session_data['id']
        
        # Update session data
        session_data['context']['progress'] = {
            'tasks_completed': tasks_completed,
            'tasks_total': tasks_total,
            'current_task': current_task,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Update index
        if session_id in self._sessions_index:
            self._sessions_index[session_id].tasks_completed = tasks_completed
            self._sessions_index[session_id].tasks_total = tasks_total
            self._sessions_index[session_id].current_task = current_task
        
        # Save updates
        await self.save_session(session_data)
    
    async def add_execution_results(
        self,
        session_data: Dict[str, Any],
        results: Dict[str, Any]
    ):
        """
        Add execution results to session context.
        
        Args:
            session_data: Session data dictionary
            results: Compiled execution results
        """
        session_id = session_data['id']
        
        # Add results to session history
        if 'execution_history' not in session_data['context']:
            session_data['context']['execution_history'] = []
        
        execution_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'results': results,
            'summary': {
                'tasks_completed': results['summary']['completed_tasks'],
                'success_rate': results['summary']['success_rate'],
                'quality_score': results['summary']['quality_score'],
                'files_created': len(results['files']['created']),
                'files_modified': len(results['files']['modified'])
            }
        }
        
        session_data['context']['execution_history'].append(execution_entry)
        
        # Update session status based on results
        if results['summary']['success_rate'] >= 0.8:
            session_data['status'] = 'completed'
        elif results['errors']:
            session_data['status'] = 'failed'
        else:
            session_data['status'] = 'active'
        
        # Update index
        if session_id in self._sessions_index:
            self._sessions_index[session_id].status = session_data['status']
        
        await self.save_session(session_data)
    
    async def get_session_context_for_rag(self, session_data: Dict[str, Any]) -> str:
        """
        Generate RAG-friendly context from session data.
        
        Args:
            session_data: Session data dictionary
            
        Returns:
            Formatted context string for RAG ingestion
        """
        context_lines = [
            f"# Session Context: {session_data['name']}",
            f"Project: {session_data['project_dir']}",
            f"Created: {session_data['created_at']}",
            f"Status: {session_data['status']}",
            ""
        ]
        
        # Add current request if available
        if session_data['context'].get('current_request'):
            context_lines.extend([
                "## Current Request",
                session_data['context']['current_request'],
                ""
            ])
        
        # Add execution plan if available
        if session_data['context'].get('execution_plan'):
            plan = session_data['context']['execution_plan']
            context_lines.extend([
                "## Execution Plan",
                f"Tasks: {len(plan.get('tasks', []))}",
                f"Agents: {plan.get('agent_count', 'Unknown')}",
                f"Execution: {plan.get('execution_type', 'Unknown')}",
                ""
            ])
        
        # Add execution history
        if session_data['context'].get('execution_history'):
            context_lines.extend([
                "## Execution History",
                ""
            ])
            
            for i, entry in enumerate(session_data['context']['execution_history']):
                context_lines.extend([
                    f"### Execution {i + 1} ({entry['timestamp']})",
                    f"- Tasks completed: {entry['summary']['tasks_completed']}",
                    f"- Success rate: {entry['summary']['success_rate']:.1%}",
                    f"- Quality score: {entry['summary']['quality_score']:.1f}/100",
                    f"- Files created: {entry['summary']['files_created']}",
                    f"- Files modified: {entry['summary']['files_modified']}",
                    ""
                ])
        
        # Add user preferences
        if session_data['context'].get('user_preferences'):
            context_lines.extend([
                "## User Preferences",
                ""
            ])
            for key, value in session_data['context']['user_preferences'].items():
                context_lines.append(f"- {key}: {value}")
            context_lines.append("")
        
        return "\n".join(context_lines)
    
    async def recover_interrupted_session(self, session_name: str) -> Optional[Dict[str, Any]]:
        """
        Recover a session that was interrupted during execution.
        
        Args:
            session_name: Name of the session to recover
            
        Returns:
            Session data if recovery is possible, None otherwise
        """
        session_data = await self.load_session(session_name)
        
        if not session_data:
            return None
        
        # Check if session was interrupted
        progress = session_data['context'].get('progress', {})
        if not progress:
            return session_data  # No progress to recover
        
        tasks_completed = progress.get('tasks_completed', 0)
        tasks_total = progress.get('tasks_total', 0)
        current_task = progress.get('current_task')
        
        if tasks_completed < tasks_total and current_task:
            # Session was interrupted, prepare for recovery
            session_data['status'] = 'recovering'
            session_data['context']['recovery_info'] = {
                'interrupted_at': progress.get('updated_at'),
                'last_completed_task': tasks_completed,
                'next_task': current_task,
                'recovery_timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            await self.save_session(session_data)
        
        return session_data