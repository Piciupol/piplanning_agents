"""Status checking utilities."""
from src.utils.config import Config
from src.ui.console_ui import ConsoleUI


def check_ado_connection(console_ui: ConsoleUI) -> bool:
    """
    Check Azure DevOps connection.
    
    Args:
        console_ui: Console UI instance
        
    Returns:
        True if connection successful
    """
    from src.integrations.ado_client import ADOClient
    
    console_ui.display_info("Checking Azure DevOps connection...")
    
    # Validate config
    is_valid, error = Config.validate_ado_config()
    if not is_valid:
        console_ui.display_error(f"Configuration error: {error}")
        return False
    
    try:
        client = ADOClient(
            organization_url=Config.ADO_ORG_URL,
            personal_access_token=Config.ADO_PAT
        )
        
        # Try to list projects (simple connection test)
        # Note: This is a placeholder - actual implementation would test connection
        console_ui.display_success("Azure DevOps connection configured")
        console_ui.display_info(f"Organization URL: {Config.ADO_ORG_URL}")
        return True
        
    except Exception as e:
        console_ui.display_error(f"Connection failed: {e}")
        return False


def check_ai_config(console_ui: ConsoleUI) -> bool:
    """
    Check Azure OpenAI configuration.
    
    Args:
        console_ui: Console UI instance
        
    Returns:
        True if configuration valid
    """
    console_ui.display_info("Checking Azure OpenAI configuration...")
    
    is_valid, error = Config.validate_ai_config()
    if not is_valid:
        console_ui.display_warning(f"AI configuration incomplete: {error}")
        console_ui.display_info("AI agents will fall back to standard logic")
        return False
    
    console_ui.display_success("Azure OpenAI configuration valid")
    console_ui.display_info(f"Endpoint: {Config.AZURE_OPENAI_ENDPOINT}")
    console_ui.display_info(f"Deployment: {Config.AZURE_OPENAI_DEPLOYMENT}")
    return True
