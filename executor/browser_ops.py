"""
Browser Operations for Voice Agent:
URL navigation, web search queries, default browser integration.
"""

import webbrowser
import urllib.parse
import logging
from brain.planner import ActionResult

logger = logging.getLogger("VoiceAgent.BrowserOps")


class BrowserOps:
    def open_url(self, url: str) -> ActionResult:
        """Open a website in the default system browser."""
        target = url.strip()
        if not target.startswith("http://") and not target.startswith("https://"):
            target = f"https://{target}"

        try:
            opened = webbrowser.open(target, new=2)
            if opened:
                return ActionResult(success=True, message=f"Opened browser at: {target}")
            else:
                return ActionResult(success=True, message=f"Dispatched URL to system browser: {target}")
        except Exception as e:
            logger.error(f"Failed to open URL '{target}': {e}")
            return ActionResult(success=False, message=f"Failed to open URL: {e}", error=str(e))

    def web_search(self, query: str) -> ActionResult:
        """Open browser with Google search query."""
        clean_query = query.strip()
        encoded = urllib.parse.quote_plus(clean_query)
        search_url = f"https://www.google.com/search?q={encoded}"
        try:
            webbrowser.open(search_url, new=2)
            return ActionResult(success=True, message=f"Searching Google for: '{clean_query}'")
        except Exception as e:
            logger.error(f"Failed to execute web search: {e}")
            return ActionResult(success=False, message=f"Failed to search: {e}", error=str(e))
