"""
CAT Provider Auto-Update System

This module automatically fetches and updates AI provider information
from provider APIs and a central registry. It ensures CAT always has
the latest models and providers available.

Features:
- Auto-discovery of new models from provider APIs
- Periodic background updates
- Fallback to cached data when offline
- Support for custom provider endpoints
"""

import json
import os
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

_LOG = logging.getLogger("cct.auto_update")

# Configuration
UPDATE_INTERVAL_HOURS = 24  # Check for updates every 24 hours
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cct", "cache", "providers")
PROVIDERS_CACHE_FILE = os.path.join(CACHE_DIR, "providers_cache.json")
LAST_UPDATE_FILE = os.path.join(CACHE_DIR, "last_update.json")
CUSTOM_PROVIDERS_FILE = os.path.join(os.path.expanduser("~"), ".cct", "custom_providers.json")

# Central registry URL (could be a GitHub raw URL or custom server)
CENTRAL_REGISTRY_URL = "https://raw.githubusercontent.com/cct-ai/providers/main/providers.json"

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


class ProviderAutoUpdater:
    """Handles automatic updates of AI provider information."""
    
    def __init__(self):
        self._update_lock = threading.Lock()
        self._background_thread = None
        self._stop_event = threading.Event()
        self._providers_data = None
        self._last_update = None
        
    def start_background_updates(self):
        """Start background update thread."""
        if self._background_thread and self._background_thread.is_alive():
            return
            
        self._stop_event.clear()
        self._background_thread = threading.Thread(
            target=self._update_loop,
            daemon=True,
            name="cct-provider-updater"
        )
        self._background_thread.start()
        _LOG.info("Started background provider updater")
        
    def stop_background_updates(self):
        """Stop background update thread."""
        self._stop_event.set()
        if self._background_thread:
            self._background_thread.join(timeout=5)
        _LOG.info("Stopped background provider updater")
        
    def _update_loop(self):
        """Background loop that checks for updates periodically."""
        while not self._stop_event.is_set():
            try:
                self.check_and_update()
            except Exception as e:
                _LOG.error(f"Error in update loop: {e}")
            
            # Wait for next update interval or stop event
            self._stop_event.wait(UPDATE_INTERVAL_HOURS * 3600)
            
    def check_and_update(self, force: bool = False) -> bool:
        """Check for updates and apply if available.
        
        Args:
            force: Force update even if recently checked
            
        Returns:
            True if updates were applied, False otherwise
        """
        with self._update_lock:
            try:
                # Check if we need to update
                if not force and not self._needs_update():
                    _LOG.info("Provider data is up to date")
                    return False
                    
                _LOG.info("Checking for provider updates...")
                
                # Try to fetch from central registry
                new_data = self._fetch_central_registry()
                
                if new_data:
                    # Merge with local custom providers
                    custom_providers = self._load_custom_providers()
                    if custom_providers:
                        new_data = self._merge_providers(new_data, custom_providers)
                    
                    # Save to cache
                    self._save_to_cache(new_data)
                    
                    # Update in-memory data
                    self._providers_data = new_data
                    self._last_update = datetime.now()
                    
                    # Save last update timestamp
                    self._save_last_update()
                    
                    _LOG.info(f"Updated providers: {len(new_data.get('providers', []))} providers")
                    return True
                else:
                    _LOG.warning("Failed to fetch central registry, using cached data")
                    return False
                    
            except Exception as e:
                _LOG.error(f"Error checking for updates: {e}")
                return False
                
    def _needs_update(self) -> bool:
        """Check if we need to update based on last update time."""
        try:
            if os.path.exists(LAST_UPDATE_FILE):
                with open(LAST_UPDATE_FILE, "r") as f:
                    data = json.load(f)
                    last_str = data.get("last_update")
                    if last_str:
                        last_time = datetime.fromisoformat(last_str)
                        if datetime.now() - last_time < timedelta(hours=UPDATE_INTERVAL_HOURS):
                            return False
            return True
        except Exception:
            return True
            
    def _fetch_central_registry(self) -> Optional[Dict]:
        """Fetch provider data from central registry."""
        try:
            import requests
            
            # Try GitHub raw URL first
            resp = requests.get(CENTRAL_REGISTRY_URL, timeout=10)
            if resp.status_code == 200:
                return resp.json()
                
            # Fallback to other sources
            fallback_urls = [
                "https://raw.githubusercontent.com/cct-ai/providers/main/providers.json",
                "https://cdn.jsdelivr.net/gh/cct-ai/providers@main/providers.json",
            ]
            
            for url in fallback_urls:
                try:
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        return resp.json()
                except Exception:
                    continue
                    
            return None
            
        except Exception as e:
            _LOG.error(f"Error fetching central registry: {e}")
            return None
            
    def _load_custom_providers(self) -> List[Dict]:
        """Load custom providers from local file."""
        try:
            if os.path.exists(CUSTOM_PROVIDERS_FILE):
                with open(CUSTOM_PROVIDERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("providers", [])
        except Exception as e:
            _LOG.error(f"Error loading custom providers: {e}")
        return []
        
    def _merge_providers(self, central_data: Dict, custom_providers: List[Dict]) -> Dict:
        """Merge central registry data with custom providers."""
        providers = central_data.get("providers", [])
        existing_ids = {p.get("id") for p in providers}
        
        for custom in custom_providers:
            if custom.get("id") not in existing_ids:
                providers.append(custom)
                
        central_data["providers"] = providers
        return central_data
        
    def _save_to_cache(self, data: Dict):
        """Save provider data to cache file."""
        try:
            with open(PROVIDERS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            _LOG.error(f"Error saving to cache: {e}")
            
    def _save_last_update(self):
        """Save last update timestamp."""
        try:
            with open(LAST_UPDATE_FILE, "w") as f:
                json.dump({"last_update": datetime.now().isoformat()}, f)
        except Exception as e:
            _LOG.error(f"Error saving last update: {e}")
            
    def get_providers(self, force_refresh: bool = False) -> Dict:
        """Get provider data, loading from cache if needed.
        
        Args:
            force_refresh: Force refresh from cache/network
            
        Returns:
            Dictionary with providers data
        """
        if self._providers_data and not force_refresh:
            return self._providers_data
            
        # Try to load from cache first
        try:
            if os.path.exists(PROVIDERS_CACHE_FILE):
                with open(PROVIDERS_CACHE_FILE, "r", encoding="utf-8") as f:
                    self._providers_data = json.load(f)
                    return self._providers_data
        except Exception as e:
            _LOG.error(f"Error loading from cache: {e}")
            
        # Return empty data if nothing available
        return {"version": 1, "providers": []}
        
    def add_custom_provider(self, provider: Dict) -> bool:
        """Add a custom provider to the local configuration.
        
        Args:
            provider: Provider configuration dictionary
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            custom_providers = self._load_custom_providers()
            
            # Check if provider already exists
            existing_ids = {p.get("id") for p in custom_providers}
            if provider.get("id") in existing_ids:
                _LOG.warning(f"Provider {provider.get('id')} already exists")
                return False
                
            # Add timestamp
            provider["last_updated"] = datetime.now().isoformat()
            custom_providers.append(provider)
            
            # Save to file
            with open(CUSTOM_PROVIDERS_FILE, "w", encoding="utf-8") as f:
                json.dump({"providers": custom_providers}, f, indent=2, ensure_ascii=False)
                
            _LOG.info(f"Added custom provider: {provider.get('id')}")
            return True
            
        except Exception as e:
            _LOG.error(f"Error adding custom provider: {e}")
            return False
            
    def remove_custom_provider(self, provider_id: str) -> bool:
        """Remove a custom provider from the local configuration.
        
        Args:
            provider_id: ID of the provider to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        try:
            custom_providers = self._load_custom_providers()
            original_count = len(custom_providers)
            
            # Remove provider
            custom_providers = [p for p in custom_providers if p.get("id") != provider_id]
            
            if len(custom_providers) == original_count:
                _LOG.warning(f"Provider {provider_id} not found")
                return False
                
            # Save to file
            with open(CUSTOM_PROVIDERS_FILE, "w", encoding="utf-8") as f:
                json.dump({"providers": custom_providers}, f, indent=2, ensure_ascii=False)
                
            _LOG.info(f"Removed custom provider: {provider_id}")
            return True
            
        except Exception as e:
            _LOG.error(f"Error removing custom provider: {e}")
            return False
            
    def discover_provider_models(self, provider_id: str, base_url: str, 
                                  api_style: str = "openai") -> List[str]:
        """Discover available models from a provider's API.
        
        Args:
            provider_id: Provider identifier
            base_url: API base URL
            api_style: API style (openai, anthropic, gemini, ollama)
            
        Returns:
            List of available model names
        """
        try:
            import requests
            
            models = []
            
            if api_style == "ollama":
                # Ollama uses /api/tags
                resp = requests.get(f"{base_url}/api/tags", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    
            elif api_style == "openai":
                # OpenAI-compatible uses /v1/models
                resp = requests.get(f"{base_url}/v1/models", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    
            elif api_style == "anthropic":
                # Anthropic doesn't have a public models endpoint
                # Use known models list
                models = [
                    "claude-4-fable-5.1",
                    "claude-sonnet-4-20250514",
                    "claude-opus-4-20250514",
                    "claude-3-7-sonnet-20250219",
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-haiku-20241022",
                ]
                
            elif api_style == "gemini":
                # Gemini uses specific endpoint
                resp = requests.get(
                    f"{base_url}/models",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    
            _LOG.info(f"Discovered {len(models)} models for {provider_id}")
            return sorted(set(models))
            
        except Exception as e:
            _LOG.error(f"Error discovering models for {provider_id}: {e}")
            return []
            

# Global updater instance
_updater = None
_updater_lock = threading.Lock()


def get_updater() -> ProviderAutoUpdater:
    """Get the global provider auto-updater instance."""
    global _updater
    with _updater_lock:
        if _updater is None:
            _updater = ProviderAutoUpdater()
        return _updater


def start_auto_updates():
    """Start the auto-update system."""
    updater = get_updater()
    updater.start_background_updates()


def stop_auto_updates():
    """Stop the auto-update system."""
    updater = get_updater()
    updater.stop_background_updates()


def force_update() -> bool:
    """Force an immediate update check."""
    updater = get_updater()
    return updater.check_and_update(force=True)


def get_latest_providers() -> Dict:
    """Get the latest provider data."""
    updater = get_updater()
    return updater.get_providers(force_refresh=True)


def add_custom_provider(provider: Dict) -> bool:
    """Add a custom provider."""
    updater = get_updater()
    return updater.add_custom_provider(provider)


def remove_custom_provider(provider_id: str) -> bool:
    """Remove a custom provider."""
    updater = get_updater()
    return updater.remove_custom_provider(provider_id)


def discover_models(provider_id: str, base_url: str, 
                   api_style: str = "openai") -> List[str]:
    """Discover models from a provider."""
    updater = get_updater()
    return updater.discover_provider_models(provider_id, base_url, api_style)
