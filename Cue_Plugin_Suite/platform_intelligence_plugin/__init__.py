"""
Cue Platform Intelligence Plugin
=================================
Three platform rule modules + YouTube PSO + Instagram search intelligence.

Usage:
    from cue_platform_plugin import CuePlatformPlugin
    plugin = CuePlatformPlugin()
    result = plugin.check_facebook_post(text="...")
    result = plugin.write_youtube_title(topic="...", keywords=[...])
    result = plugin.analyze_youtube_keyword(keyword="...")
"""

from .plugin import CuePlatformPlugin

__all__ = ["CuePlatformPlugin"]
__version__ = "1.0.0"
