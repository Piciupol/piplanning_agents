"""Output file management for PI Planning."""
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import json
import pandas as pd
import io

from src.core.models import ProgramBoard, Transcript
from src.ui.program_board_html import generate_html_program_board


class OutputManager:
    """Manages saving output files."""
    
    def __init__(self, output_dir: Path):
        """
        Initialize output manager.
        
        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def save_transcript(self, transcript: Transcript) -> Path:
        """
        Save transcript to JSON file.
        
        Args:
            transcript: Transcript to save
            
        Returns:
            Path to saved file
        """
        file_path = self.output_dir / f"transcript_{self.timestamp}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(transcript.model_dump(mode="json"), f, indent=2, default=str)
        return file_path
    
    def save_program_board(self, program_board: ProgramBoard) -> Path:
        """
        Save program board to JSON file.
        
        Args:
            program_board: Program board to save
            
        Returns:
            Path to saved file
        """
        file_path = self.output_dir / f"program_board_{self.timestamp}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(program_board.model_dump(mode="json"), f, indent=2, default=str)
        return file_path
    
    def save_html_board(self, program_board: ProgramBoard) -> Path:
        """
        Save HTML program board.
        
        Args:
            program_board: Program board to save
            
        Returns:
            Path to saved file
        """
        file_path = self.output_dir / f"program_board_{self.timestamp}.html"
        html_content = generate_html_program_board(program_board)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return file_path
    
    def save_all(self, program_board: ProgramBoard, transcript: Transcript) -> Dict[str, Path]:
        """
        Save all output files.
        
        Args:
            program_board: Program board to save
            transcript: Transcript to save
            
        Returns:
            Dictionary with file type -> path
        """
        return {
            "transcript": self.save_transcript(transcript),
            "program_board_json": self.save_program_board(program_board),
            "program_board_html": self.save_html_board(program_board),
        }

def generate_html_report(data: Dict[str, Any]) -> str:
    """
    Generate HTML report content from planning result data.
    This function is used by the UI component for download buttons.
    """
    try:
        # If data is already a ProgramBoard object
        if isinstance(data, ProgramBoard):
            return generate_html_program_board(data)
            
        # If data is a dict containing program_board
        if isinstance(data, dict):
            pb_data = data.get("program_board")
            if pb_data:
                if isinstance(pb_data, ProgramBoard):
                    return generate_html_program_board(pb_data)
                if isinstance(pb_data, dict):
                    # Try to reconstruct ProgramBoard
                    # Note: This might fail if pb_data structure doesn't perfectly match Pydantic model
                    # due to serialization (e.g. date strings vs datetime objects)
                    # Ideally, UI should pass the ProgramBoard object directly.
                    try:
                        return generate_html_program_board(ProgramBoard(**pb_data))
                    except Exception:
                        pass
                        
        return "<html><body><h1>Error</h1><p>Could not generate report from provided data.</p></body></html>"
    except Exception as e:
        return f"<html><body><h1>Error generating report</h1><p>{e}</p></body></html>"

def generate_excel_report(data: Dict[str, Any]) -> bytes:
    """
    Generate Excel report as bytes.
    """
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Extract assignments
            assignments = data.get("assignments", [])
            if assignments:
                # Handle objects vs dicts
                assign_list = [
                    a.model_dump() if hasattr(a, 'model_dump') else a 
                    for a in assignments
                ]
                df_assign = pd.DataFrame(assign_list)
                df_assign.to_excel(writer, sheet_name='Assignments', index=False)
                
            # Extract features
            features = data.get("features", [])
            if features:
                feat_list = [
                    f.model_dump() if hasattr(f, 'model_dump') else f 
                    for f in features
                ]
                df_features = pd.DataFrame(feat_list)
                # Simplify nested lists for Excel
                cols_to_drop = ['user_stories', 'milestones']
                df_features = df_features.drop(columns=[c for c in cols_to_drop if c in df_features.columns])
                df_features.to_excel(writer, sheet_name='Features', index=False)
                
            # Extract risks
            risks = data.get("risks", [])
            if risks:
                risk_list = [
                    r.model_dump() if hasattr(r, 'model_dump') else r 
                    for r in risks
                ]
                df_risks = pd.DataFrame(risk_list)
                df_risks.to_excel(writer, sheet_name='Risks', index=False)
                
            # Extract objectives
            objectives = data.get("objectives", [])
            if objectives:
                obj_list = [
                    o.model_dump() if hasattr(o, 'model_dump') else o 
                    for o in objectives
                ]
                df_obj = pd.DataFrame(obj_list)
                df_obj.to_excel(writer, sheet_name='Objectives', index=False)
                
    except Exception as e:
        print(f"Error generating Excel: {e}")
        
    return output.getvalue()
