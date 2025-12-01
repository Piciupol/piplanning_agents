"""Base class for AI-powered agents using Azure OpenAI."""
import os
from typing import Dict, Any, Optional
from openai import AzureOpenAI


class AIAgentBase:
    """Base class for agents that use Azure OpenAI."""
    
    def __init__(self):
        """Initialize AI agent with Azure OpenAI client."""
        from src.utils.config import Config
        self.azure_openai_key = Config.AZURE_OPENAI_KEY
        self.azure_openai_endpoint = Config.AZURE_OPENAI_ENDPOINT
        self.azure_openai_deployment = Config.AZURE_OPENAI_DEPLOYMENT
        self.api_version = Config.AZURE_OPENAI_API_VERSION
        
        self.client = None
        if self.azure_openai_key and self.azure_openai_endpoint:
            try:
                self.client = AzureOpenAI(
                    api_key=self.azure_openai_key,
                    api_version=self.api_version,
                    azure_endpoint=self.azure_openai_endpoint
                )
            except Exception as e:
                print(f"Warning: Could not initialize Azure OpenAI client: {e}")
    
    def call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 1.0,
        max_tokens: int = 25000
    ) -> Optional[str]:
        """
        Call Azure OpenAI LLM.
        
        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            temperature: Temperature (0-1)
            max_tokens: Max tokens
            
        Returns:
            LLM response or None if AI not available
        """
        if not self.client:
            print(f"DEBUG: AI client is None. Key: {bool(self.azure_openai_key)}, Endpoint: {bool(self.azure_openai_endpoint)}, Deployment: {self.azure_openai_deployment}")
            return None
        
        try:
            print(f"DEBUG: Calling LLM with deployment: {self.azure_openai_deployment}, temperature: {temperature}, max_tokens: {max_tokens}")
            # This model requires max_completion_tokens instead of max_tokens
            response = self.client.chat.completions.create(
                model=self.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_completion_tokens=max_tokens
            )
            choice = response.choices[0]
            result = choice.message.content
            finish_reason = choice.finish_reason if hasattr(choice, 'finish_reason') else 'unknown'
            
            print(f"DEBUG: LLM call successful, response length: {len(result) if result else 0}")
            print(f"DEBUG: Finish reason: {finish_reason}")
            print(f"DEBUG: Response content: {result[:500] if result else 'None or empty'}")
            
            if not result or len(result) == 0:
                print(f"DEBUG: WARNING - Empty response from LLM.")
                print(f"DEBUG: Finish reason: {finish_reason}")
                print(f"DEBUG: Response choices count: {len(response.choices) if response.choices else 0}")
                if finish_reason == 'content_filter':
                    print("DEBUG: Response was filtered by content filter - may need to adjust prompt")
                elif finish_reason == 'length':
                    print("DEBUG: Response was truncated due to length - increase max_tokens")
                elif finish_reason == 'stop':
                    print("DEBUG: Response stopped early - may indicate prompt issue")
            
            return result
        except Exception as e:
            print(f"DEBUG: Error calling Azure OpenAI: {e}")
            import traceback
            traceback.print_exc()
            return None
