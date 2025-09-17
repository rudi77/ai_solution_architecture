
# ==================== STATE MANAGEMENT ====================

from datetime import datetime
from pathlib import Path
import pickle
import time
from typing import Dict, Optional

import structlog


class StateManager:
    """Manages agent state persistence and recovery"""
    
    def __init__(self, state_dir: str = "./agent_states"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(exist_ok=True)
        self.logger = structlog.get_logger()
    
    async def save_state(self, session_id: str, state_data: Dict) -> bool:
        """Save agent state asynchronously"""
        try:
            state_file = self.state_dir / f"{session_id}.pkl"
            
            state_to_save = {
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'state_data': state_data
            }
            
            # Async file write
            import aiofiles
            async with aiofiles.open(state_file, 'wb') as f:
                await f.write(pickle.dumps(state_to_save))
            
            self.logger.info("state_saved", session_id=session_id)
            return True
            
        except Exception as e:
            self.logger.error("state_save_failed", session_id=session_id, error=str(e))
            return False
    
    async def load_state(self, session_id: str) -> Optional[Dict]:
        """Load agent state asynchronously"""
        try:
            state_file = self.state_dir / f"{session_id}.pkl"
            
            if not state_file.exists():
                return None
            
            import aiofiles
            async with aiofiles.open(state_file, 'rb') as f:
                content = await f.read()
                state = pickle.loads(content)
            
            self.logger.info("state_loaded", session_id=session_id)
            return state['state_data']
            
        except Exception as e:
            self.logger.error("state_load_failed", session_id=session_id, error=str(e))
            return None
    
    def cleanup_old_states(self, days: int = 7):
        """Remove states older than specified days"""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        for state_file in self.state_dir.glob("*.pkl"):
            if state_file.stat().st_mtime < cutoff_time:
                state_file.unlink()
                self.logger.info("old_state_removed", file=state_file.name)