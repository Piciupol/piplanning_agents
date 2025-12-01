"""Configuration settings for PI Planning application."""
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import os


class Config:
    """Application configuration loaded from config.yaml."""
    
    _config_data: dict = None
    _config_path: Path = None
    
    # Azure DevOps
    ADO_ORG_URL: Optional[str] = None
    ADO_PAT: Optional[str] = None
    ADO_PROJECT: str = "GN"
    
    # Azure OpenAI
    AZURE_OPENAI_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4"
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    
    # Default paths
    DEFAULT_OUTPUT_DIR: Path = Path("output")
    
    # Default values
    DEFAULT_ITERATIONS: int = 5
    DEFAULT_MAX_ROUNDS: int = 3
    CAPACITY_BUFFER: float = 0.20
    
    # Defaults (Phase 2 Refactoring)
    DEFAULT_SPRINTS_CONFIG: Dict[str, Any] = {}
    DEFAULT_TEAMS: List[Dict[str, Any]] = []
    DEFAULT_QUERIES: Dict[str, str] = {}
    OWNER_MAPPING: Dict[str, str] = {}
    
    # ADO Field Mapping (Phase 2 Refactoring)
    ADO_MAPPING: Dict[str, str] = {
        "title": "System.Title",
        "description": "System.Description",
        "state": "System.State",
        "assigned_to": "System.AssignedTo",
        "area_path": "System.AreaPath",
        "iteration_path": "System.IterationPath",
        "work_item_type": "System.WorkItemType",
        "effort": "Microsoft.VSTS.Scheduling.StoryPoints",
        "remaining_work": "Microsoft.VSTS.Scheduling.RemainingWork",
        "priority": "Microsoft.VSTS.Common.Priority",
        "business_value": "Microsoft.VSTS.Common.BusinessValue",
        "target_date": "System.TargetDate"
    }
    
    @classmethod
    def load_config(cls, config_path: Optional[Path] = None) -> None:
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to config file (default: config.yaml in project root)
        """
        if config_path is None:
            # Try to find config.yaml in project root
            current_dir = Path(__file__).parent.parent.parent
            config_path = current_dir / "config.yaml"
        
        cls._config_path = config_path
        
        if not config_path.exists():
            cls._create_default_config(config_path)
            print(f"Created default config file at {config_path}")
            return
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cls._config_data = yaml.safe_load(f) or {}
            
            # Load Azure DevOps settings
            ado_config = cls._config_data.get("ado", {})
            cls.ADO_ORG_URL = ado_config.get("org_url") or os.getenv("ADO_ORG_URL")
            cls.ADO_PAT = ado_config.get("pat") or os.getenv("ADO_PAT")
            cls.ADO_PROJECT = ado_config.get("project", "GN")
            
            # Load Azure OpenAI settings
            ai_config = cls._config_data.get("azure_openai", {})
            cls.AZURE_OPENAI_KEY = ai_config.get("key") or os.getenv("AZURE_OPENAI_KEY")
            cls.AZURE_OPENAI_ENDPOINT = ai_config.get("endpoint") or os.getenv("AZURE_OPENAI_ENDPOINT")
            cls.AZURE_OPENAI_DEPLOYMENT = ai_config.get("deployment", "gpt-4")
            cls.AZURE_OPENAI_API_VERSION = ai_config.get("api_version", "2024-02-15-preview")
            
            # Load application settings
            app_config = cls._config_data.get("app", {})
            if app_config.get("default_output_dir"):
                cls.DEFAULT_OUTPUT_DIR = Path(app_config["default_output_dir"])
            cls.DEFAULT_MAX_ROUNDS = app_config.get("default_max_rounds", 3)
            cls.CAPACITY_BUFFER = app_config.get("capacity_buffer", 0.20)
            
            # Load Defaults
            defaults = cls._config_data.get("defaults", {})
            cls.DEFAULT_SPRINTS_CONFIG = defaults.get("sprints", {})
            cls.DEFAULT_TEAMS = defaults.get("teams", [])
            cls.DEFAULT_QUERIES = defaults.get("queries", {})
            cls.OWNER_MAPPING = defaults.get("owner_mapping", {})
            cls.DEFAULT_ITERATIONS = cls.DEFAULT_SPRINTS_CONFIG.get("count", 5)
            
            # Load ADO Mapping
            if "ado_mapping" in cls._config_data:
                # Update default mapping with user overrides
                cls.ADO_MAPPING.update(cls._config_data["ado_mapping"])
            
        except Exception as e:
            print(f"Error loading config file {config_path}: {e}")
            print("Using default values and environment variables as fallback")
            cls._load_from_env()
    
    @classmethod
    def _create_default_config(cls, config_path: Path) -> None:
        """Create default config.yaml file."""
        # Minimal default config
        default_config = {
            "ado": {"org_url": "", "pat": ""},
            "ado_mapping": cls.ADO_MAPPING,
            "defaults": {
                "sprints": {"count": 5, "length_weeks": 2},
                "teams": [{"name": "Team A", "id": "team_a", "default_capacity": 40}]
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
    
    @classmethod
    def _load_from_env(cls) -> None:
        """Fallback: load from environment variables."""
        cls.ADO_ORG_URL = os.getenv("ADO_ORG_URL")
        cls.ADO_PAT = os.getenv("ADO_PAT")
        cls.AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
        cls.AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")

    @classmethod
    def get_default_team_names(cls) -> List[str]:
        """Get list of default team names."""
        return [t.get("name") for t in cls.DEFAULT_TEAMS]
    
    @classmethod
    def get_field(cls, key: str) -> str:
        """Get ADO field name for a given key."""
        return cls.ADO_MAPPING.get(key, key)

    @classmethod
    def validate_ado_config(cls) -> Tuple[bool, Optional[str]]:
        """Validate ADO configuration."""
        if not cls.ADO_ORG_URL:
            return False, "ADO_ORG_URL is not set"
        if not cls.ADO_PAT:
            return False, "ADO_PAT is not set"
        return True, None

    @classmethod
    def validate_ai_config(cls) -> Tuple[bool, Optional[str]]:
        """Validate AI configuration."""
        if not cls.AZURE_OPENAI_KEY:
            return False, "AZURE_OPENAI_KEY is not set"
        if not cls.AZURE_OPENAI_ENDPOINT:
            return False, "AZURE_OPENAI_ENDPOINT is not set"
        return True, None
