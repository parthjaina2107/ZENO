"""
Shared Gemini API call wrapper with retry, backoff, and model fallback.
"""

import asyncio
import logging
from typing import Optional, Any
from config import config

logger = logging.getLogger("VoiceAgent.API")


async def call_gemini_with_fallback(
    client,
    contents,
    primary_model: Optional[str] = None,
    max_retries: int = 2,
    initial_backoff: float = 1.0,
) -> Optional[Any]:
    """
    Try primary model, then each fallback model, with retry and exponential backoff.
    Executes synchronous SDK generate_content calls via asyncio.to_thread
    so the asyncio event loop is never blocked.
    Returns the response object, or None if all models/retries fail.
    """
    if client is None:
        return None

    primary = primary_model or getattr(config, "GEMINI_MODEL", "gemini-3.8-flash")
    fallbacks = getattr(config, "GEMINI_FALLBACK_MODELS", ["gemini-2.5-flash", "gemini-2.0-flash"])
    
    # Maintain order without duplicates
    models_to_try = [primary]
    for fb in fallbacks:
        if fb not in models_to_try:
            models_to_try.append(fb)

    for model in models_to_try:
        for attempt in range(max_retries):
            try:
                # Run synchronous GenAI call in thread pool to prevent blocking event loop
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=contents,
                )
                if response:
                    return response
            except Exception as e:
                err_str = str(e)
                is_transient = any(
                    code in err_str
                    for code in ["503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "Deadline", "timeout"]
                )
                if is_transient and attempt < max_retries - 1:
                    wait = initial_backoff * (2 ** attempt)
                    logger.warning(
                        f"Transient error on model '{model}' (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait:.1f}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.warning(f"Model '{model}' failed (attempt {attempt + 1}/{max_retries}): {e}")
                    break  # Move to the next fallback model

    logger.error("All Gemini models in fallback chain failed.")
    return None
