#!/usr/bin/env python3
"""
Production-Ready IDP Copilot Implementation
Vollständig erweitert mit Priority 1, 2 und 3 Features
"""

import json
import time
import os
import asyncio
import pickle
import structlog
import concurrent.futures
from typing import Dict, List, Optional, Any, Tuple, AsyncGenerator, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime
from pathlib import Path
from abc import ABC, abstractmethod
import hashlib
from collections import defaultdict
import re
from functools import partial

from capstone.prototype.agent import ReActAgent
from capstone.prototype.llm_provider import OpenAIProvider



# No built-in prompt imports; the caller must provide a system prompt

# External dependencies (requirements.txt)
# pip install pydantic langchain openai anthropic structlog prometheus-client circuitbreaker aiofiles

from pydantic import BaseModel, Field, validator
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from circuitbreaker import circuit
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Setup OpenTelemetry
provider = TracerProvider()
if os.getenv("IDP_ENABLE_OTEL_CONSOLE", "false").lower() in {"1", "true", "yes", "on"}:
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)


# ==================== MAIN EXECUTION ====================

async def main():
    """Main execution function"""
    
    # Start Prometheus metrics server
    start_http_server(8070)
    
    # Initialize LLM provider with fallback to mock if no API key
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if openai_key:
        llm_provider = OpenAIProvider(api_key=openai_key)
    else:
        raise ValueError("OPENAI_API_KEY is not set")
    
    # Initialize agent
    # Minimal, generic system prompt — callers should pass a mission-specific prompt
    generic_prompt = (
        "You are a generic ReAct agent. Use only provided tools, "
        "update the Todo List after each step, and ask the user on blocking errors."
    )
    agent = ReActAgent(
        system_prompt=generic_prompt,
        llm_provider=llm_provider,
        tools=[],
    )
    
    # Interactive chat loop
    print("=" * 80)
    print("🚀 Production IDP Copilot - Interactive CLI")
    print("Type 'exit' to quit.")
    print("=" * 80)
    
    session_id: Optional[str] = None
    while True:
        try:
            user_msg = input("You: ").strip()
        except EOFError:
            break
        if user_msg.lower() in ("exit", "quit", "q", ""):
            break
        async for update in agent.process_request(user_msg, session_id=session_id):
            print(update, end="", flush=True)
        # Keep session across turns
        session_id = agent.session_id
        # If agent requested user input, continue loop to capture it
        if agent.context.get("awaiting_user_input"):
            continue
        print("")
    
    # Print simple metrics snapshot on exit
    print("\n" + "=" * 80)
    print("📊 Workflow Metrics:")
    print("=" * 80)
    print("Prometheus metrics available at http://localhost:8070")

if __name__ == "__main__":
    asyncio.run(main())