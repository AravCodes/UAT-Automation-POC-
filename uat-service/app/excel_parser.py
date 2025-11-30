from typing import List, Dict, Optional
import openpyxl
from io import BytesIO
import re


def parse_excel_file(file_content: bytes) -> List[Dict]:
    """
    Parse an Excel file containing user stories.
    Expected format:
    - Row 1: Headers
    - Columns: Test ID, Title, As a, I want to, So that, Acceptance Criteria, Test IDs
    """
    stories = []
    
    try:
        workbook = openpyxl.load_workbook(BytesIO(file_content))
        sheet = workbook.active
        
        # Read headers (first row)
        headers = []
        for cell in sheet[1]:
            headers.append(cell.value.lower().strip() if cell.value else "")
        
        # Find column indices
        test_id_col = _find_column(headers, ["test id", "testid", "id"])
        title_col = _find_column(headers, ["title", "story title", "name"])
        as_a_col = _find_column(headers, ["as a", "as", "user role"])
        i_want_col = _find_column(headers, ["i want to", "i want", "want", "goal"])
        so_that_col = _find_column(headers, ["so that", "so", "benefit", "reason"])
        criteria_col = _find_column(headers, ["acceptance criteria", "criteria", "acceptance", "scenarios"])
        test_ids_col = _find_column(headers, ["test ids", "testids", "test id list", "selectors"])
        
        if not title_col:
            raise ValueError("Title column not found in Excel file")
        
        # Read data rows (skip header)
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=False), start=2):
            # Skip empty rows
            if not row[title_col].value or not str(row[title_col].value).strip():
                continue
            
            story = {
                "test_id": _get_cell_value(row, test_id_col, f"STORY-{row_idx-1:03d}"),
                "title": _get_cell_value(row, title_col, "").strip(),
                "description": "",
                "acceptance_criteria": [],
                "test_ids": []
            }
            
            # Build description from As a / I want to / So that
            as_a = _get_cell_value(row, as_a_col, "").strip()
            i_want = _get_cell_value(row, i_want_col, "").strip()
            so_that = _get_cell_value(row, so_that_col, "").strip()
            
            description_parts = []
            if as_a:
                description_parts.append(f"As a {as_a}")
            if i_want:
                description_parts.append(f"I want to {i_want}")
            if so_that:
                description_parts.append(f"So that {so_that}")
            
            if description_parts:
                story["description"] = " ".join(description_parts)
            
            # Parse acceptance criteria
            criteria_text = _get_cell_value(row, criteria_col, "").strip()
            if criteria_text:
                # Split by newlines and filter empty lines
                criteria_lines = [line.strip() for line in criteria_text.split("\n") if line.strip()]
                # Group into scenarios (separated by blank lines or "Given" keywords)
                current_scenario = []
                for line in criteria_lines:
                    if line.lower().startswith("given") and current_scenario:
                        # New scenario starting
                        story["acceptance_criteria"].append("\n".join(current_scenario))
                        current_scenario = [line]
                    else:
                        current_scenario.append(line)
                if current_scenario:
                    story["acceptance_criteria"].append("\n".join(current_scenario))
            
            # Parse test IDs
            test_ids_text = _get_cell_value(row, test_ids_col, "").strip()
            if test_ids_text:
                # Split by comma, semicolon, or newline
                test_ids = re.split(r'[,\n;]', test_ids_text)
                story["test_ids"] = [tid.strip() for tid in test_ids if tid.strip()]
            
            if story["title"]:
                stories.append(story)
        
        workbook.close()
        return stories
    
    except Exception as e:
        raise ValueError(f"Error parsing Excel file: {str(e)}")


def _find_column(headers: List[str], possible_names: List[str]) -> Optional[int]:
    """Find column index by header name."""
    for idx, header in enumerate(headers):
        if header and any(name in header.lower() for name in possible_names):
            return idx
    return None


def _get_cell_value(row, col_idx: Optional[int], default: str = "") -> str:
    """Get cell value safely."""
    if col_idx is None or col_idx >= len(row):
        return default
    value = row[col_idx].value
    return str(value) if value is not None else default

