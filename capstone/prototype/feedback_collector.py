# ==================== FEEDBACK COLLECTOR ====================

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
from typing import Dict

import structlog


class FeedbackCollector:
    """Collects and stores user feedback for continuous improvement"""
    
    def __init__(self, feedback_dir: str = "./feedback"):
        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(exist_ok=True)
        self.feedback_buffer = []
        self.logger = structlog.get_logger()
    
    async def collect_feedback(self, session_id: str, feedback_type: str, 
                              success: bool, details: Dict) -> None:
        """Collect feedback asynchronously"""
        feedback_entry = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'type': feedback_type,
            'success': success,
            'details': details
        }
        
        self.feedback_buffer.append(feedback_entry)
        
        # Flush buffer if it gets too large
        if len(self.feedback_buffer) >= 100:
            await self.flush_feedback()
    
    async def flush_feedback(self) -> None:
        """Write feedback buffer to disk"""
        if not self.feedback_buffer:
            return
        
        filename = f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.feedback_dir / filename
        
        try:
            import aiofiles
            async with aiofiles.open(filepath, 'w') as f:
                await f.write(json.dumps(self.feedback_buffer, indent=2))
            
            self.logger.info("feedback_flushed", count=len(self.feedback_buffer))
            self.feedback_buffer.clear()
            
        except Exception as e:
            self.logger.error("feedback_flush_failed", error=str(e))
    
    def analyze_feedback(self, days: int = 30) -> Dict:
        """Analyze recent feedback for patterns"""
        analysis = {
            'total_feedback': 0,
            'success_rate': 0,
            'common_failures': defaultdict(int),
            'tool_performance': defaultdict(lambda: {'success': 0, 'failure': 0})
        }
        
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        for feedback_file in self.feedback_dir.glob("*.json"):
            if feedback_file.stat().st_mtime < cutoff_date:
                continue
            
            with open(feedback_file) as f:
                feedback_data = json.load(f)
                
                for entry in feedback_data:
                    analysis['total_feedback'] += 1
                    
                    if entry['success']:
                        analysis['success_rate'] += 1
                    
                    if not entry['success'] and 'error' in entry['details']:
                        analysis['common_failures'][entry['details']['error']] += 1
                    
                    if 'tool_name' in entry['details']:
                        tool = entry['details']['tool_name']
                        if entry['success']:
                            analysis['tool_performance'][tool]['success'] += 1
                        else:
                            analysis['tool_performance'][tool]['failure'] += 1
        
        if analysis['total_feedback'] > 0:
            analysis['success_rate'] = analysis['success_rate'] / analysis['total_feedback']
        
        return analysis
