"""
Unified LLM client supporting multiple providers:
- Ollama (local/self-hosted, free)
- Groq (fast API, free tier)
- OpenAI (paid, fallback)
"""
from typing import Optional, Dict, List
import os
import json
import re
import requests
from openai import OpenAI as OpenAIClient


class LLMClient:
    """Unified client for different LLM providers."""
    
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "ollama").lower()
        self.client = None
        self.model = None
        
        if self.provider == "ollama":
            self._init_ollama()
        elif self.provider == "groq":
            self._init_groq()
        elif self.provider == "openai":
            self._init_openai()
        else:
            print(f"Unknown LLM provider: {self.provider}. Using Ollama as default.")
            self._init_ollama()
    
    def _init_ollama(self):
        """Initialize Ollama client (local, free)."""
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")  # Small, fast model
        print(f"Using Ollama at {self.base_url} with model {self.model}")
        print("To use Ollama: Install from https://ollama.ai and run: ollama pull llama3.2:3b")
    
    def _init_groq(self):
        """Initialize Groq client (fast API, free tier)."""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("GROQ_API_KEY not set. Get free API key from https://console.groq.com")
            self.client = None
            return
        try:
            # Groq uses OpenAI-compatible API
            self.client = OpenAIClient(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")  # Fast, free model
            print(f"Using Groq with model {self.model}")
        except Exception as e:
            print(f"Failed to initialize Groq: {e}")
            self.client = None
    
    def _init_openai(self):
        """Initialize OpenAI client (paid)."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("OPENAI_API_KEY not set")
            self.client = None
            return
        try:
            self.client = OpenAIClient(api_key=api_key)
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            print(f"Using OpenAI with model {self.model}")
        except Exception as e:
            print(f"Failed to initialize OpenAI: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if LLM is available."""
        if self.provider == "ollama":
            try:
                response = requests.get(f"{self.base_url}/api/tags", timeout=2)
                return response.status_code == 200
            except:
                return False
        return self.client is not None
    
    def chat_completion(self, messages: List[Dict], temperature: float = 0.1, 
                       response_format: Optional[Dict] = None, max_tokens: Optional[int] = None) -> Optional[str]:
        """
        Make a chat completion request.
        Returns the response text or None if failed.
        """
        if self.provider == "ollama":
            return self._ollama_chat(messages, temperature)
        elif self.provider == "groq" or self.provider == "openai":
            return self._openai_compatible_chat(messages, temperature, response_format, max_tokens)
        return None
    
    def _ollama_chat(self, messages: List[Dict], temperature: float) -> Optional[str]:
        """Make request to Ollama API."""
        try:
            # Convert messages format
            prompt = self._messages_to_prompt(messages)
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "format": "json"  # Request JSON format
                }
            }
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                print(f"Ollama API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Ollama request failed: {e}")
            return None
    
    def _openai_compatible_chat(self, messages: List[Dict], temperature: float,
                                response_format: Optional[Dict], max_tokens: Optional[int]) -> Optional[str]:
        """Make request to OpenAI-compatible API (Groq or OpenAI)."""
        if not self.client:
            return None
        
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            
            if response_format:
                kwargs["response_format"] = response_format
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
            
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            print(f"{self.provider.capitalize()} API error: {e}")
            return None
    
    def _messages_to_prompt(self, messages: List[Dict]) -> str:
        """Convert messages to a single prompt for Ollama."""
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}\n")
            elif role == "user":
                prompt_parts.append(f"User: {content}\n")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}\n")
        
        return "\n".join(prompt_parts)


# Initialize global LLM client
_llm_client = None

def get_llm_client() -> Optional[LLMClient]:
    """Get or create the global LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client if _llm_client.is_available() else None

