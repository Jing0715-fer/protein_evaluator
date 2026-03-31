"""
Template Manager - Handles DB <-> File sync for prompt templates.

Templates are stored in:
- Database: Primary storage for runtime use
- files in templates/single/: GitHub versioning backup

Supports method-specific auto-selection:
- X-ray crystallography -> xray template
- Cryo-EM -> cryoem template
- NMR -> nmr template
- AlphaFold / Model -> alphafold template
- Default (all methods) -> default template
"""

import os
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Template file directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "single"

# Method mapping: normalized method name -> template filename suffix
METHOD_MAPPING = {
    'x-ray': 'xray',
    'xray': 'xray',
    'x-ray crystallography': 'xray',
    'cryo-em': 'cryoem',
    'cryoem': 'cryoem',
    'electron cryomicroscopy': 'cryoem',
    'nmr': 'nmr',
    'nuclear magnetic resonance': 'nmr',
    'alphafold': 'alphafold',
    'alphafold2': 'alphafold',
    'af2': 'alphafold',
    'model': 'alphafold',
    ' homology': 'alphafold',  # AlphaFold Homology
}

# Reverse mapping for display
METHOD_DISPLAY_NAMES = {
    'xray': 'X-ray',
    'cryoem': 'Cryo-EM',
    'nmr': 'NMR',
    'alphafold': 'AlphaFold',
    'default': 'All Methods'
}


def normalize_method(method: str) -> str:
    """Normalize experimental method name to standard key."""
    if not method:
        return 'default'
    method_lower = method.lower().strip()
    return METHOD_MAPPING.get(method_lower, 'default')


def get_template_filename(method_key: str) -> str:
    """Get template filename for a method key."""
    return f"{method_key}.md"


def get_all_method_keys() -> List[str]:
    """Get all available method keys."""
    return ['default', 'xray', 'cryoem', 'nmr', 'alphafold']


def export_template_to_file(template: Any, method_key: str) -> bool:
    """
    Export a single template to a markdown file.

    Args:
        template: PromptTemplate model instance
        method_key: Method key (default, xray, cryoem, nmr, alphafold)

    Returns:
        True if successful, False otherwise
    """
    try:
        filename = get_template_filename(method_key)
        filepath = TEMPLATE_DIR / filename

        # Write content (Chinese version as primary)
        content = template.content or ''
        if template.content_en:
            content += "\n\n---\n\n## English Version\n\n" + template.content_en

        filepath.write_text(content, encoding='utf-8')
        logger.info(f"Exported template to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to export template to file: {e}")
        return False


def export_all_templates_to_files() -> int:
    """
    Export all templates from database to files.

    Returns:
        Number of templates exported
    """
    from src.database import get_session, PromptTemplate

    session = get_session()
    count = 0
    try:
        templates = session.query(PromptTemplate).filter(
            PromptTemplate.template_type == 'single'
        ).all()

        for template in templates:
            # Get method key from template's experimental_method field
            method_key = template.experimental_method if hasattr(template, 'experimental_method') and template.experimental_method else 'default'
            if export_template_to_file(template, method_key):
                count += 1

        # Also export default template as 'default.md' if it exists
        default_template = session.query(PromptTemplate).filter_by(is_default=True).first()
        if default_template and default_template.template_type == 'single':
            export_template_to_file(default_template, 'default')

        logger.info(f"Exported {count} templates to files")
    except Exception as e:
        logger.error(f"Failed to export templates: {e}")
    finally:
        session.close()

    return count


def import_template_from_file(method_key: str) -> Optional[Dict[str, Any]]:
    """
    Import a single template from a markdown file.

    Args:
        method_key: Method key (default, xray, cryoem, nmr, alphafold)

    Returns:
        Template data dict or None if file doesn't exist
    """
    filename = get_template_filename(method_key)
    filepath = TEMPLATE_DIR / filename

    if not filepath.exists():
        return None

    try:
        content = filepath.read_text(encoding='utf-8')

        # Split English version if present
        chinese_content = content
        english_content = ""
        if "\n\n---\n\n## English Version\n\n" in content:
            parts = content.split("\n\n---\n\n## English Version\n\n")
            chinese_content = parts[0]
            english_content = parts[1] if len(parts) > 1 else ""

        # Generate name from method
        display_name = METHOD_DISPLAY_NAMES.get(method_key, 'Default')
        name = f"{display_name} Analysis Template"

        return {
            'name': name,
            'name_en': f"{display_name} Analysis Template",
            'content': chinese_content,
            'content_en': english_content,
            'description': f"Auto-imported {display_name} template from file",
            'description_en': f"Auto-imported {display_name} template from file",
            'template_type': 'single',
            'experimental_method': method_key,
            'is_default': method_key == 'default'
        }
    except Exception as e:
        logger.error(f"Failed to import template from file {filepath}: {e}")
        return None


def import_templates_from_files() -> int:
    """
    Import all templates from files to database.
    Only imports if template doesn't already exist in DB.

    Returns:
        Number of templates imported
    """
    from src.database import get_session, PromptTemplate, create_prompt_template

    session = get_session()
    count = 0
    try:
        for method_key in get_all_method_keys():
            # Check if template already exists for this method
            existing = session.query(PromptTemplate).filter(
                PromptTemplate.template_type == 'single',
                PromptTemplate.experimental_method == method_key if hasattr(PromptTemplate, 'experimental_method') else False
            ).first()

            if existing:
                logger.info(f"Template for {method_key} already exists in DB, skipping import")
                continue

            template_data = import_template_from_file(method_key)
            if template_data:
                template = create_prompt_template(
                    name=template_data['name'],
                    content=template_data['content'],
                    description=template_data['description'],
                    description_en=template_data['description_en'],
                    is_default=template_data['is_default'],
                    content_en=template_data.get('content_en', ''),
                    name_en=template_data.get('name_en', ''),
                    experimental_method=method_key
                )
                if template:
                    count += 1
                    logger.info(f"Imported template for {method_key} from file")

    except Exception as e:
        logger.error(f"Failed to import templates from files: {e}")
    finally:
        session.close()

    return count


def sync_templates() -> Dict[str, int]:
    """
    Sync templates between database and files.
    - Import new templates from files to DB
    - Export templates from DB to files

    Returns:
        Dict with 'imported' and 'exported' counts
    """
    imported = import_templates_from_files()
    exported = export_all_templates_to_files()
    return {'imported': imported, 'exported': exported}


def get_template_for_method(
    experimental_method: Optional[str] = None,
    pdb_data: Optional[Dict] = None,
    session: Optional[Any] = None
) -> Optional[Any]:
    """
    Get the appropriate template for an experimental method.

    Auto-selects template based on:
    1. If experimental_method is provided, use that method's template
    2. If pdb_data is provided, determine dominant method from PDB structures
    3. Otherwise use default template

    Args:
        experimental_method: Explicit method to use
        pdb_data: PDB data dict to analyze for dominant method
        session: Optional database session

    Returns:
        PromptTemplate instance or None
    """
    from src.database import get_session, PromptTemplate

    if session is None:
        _session = get_session()
        should_close = True
    else:
        _session = session
        should_close = False

    try:
        method_key = None

        # Priority 1: Explicit method
        if experimental_method:
            method_key = normalize_method(experimental_method)
        # Priority 2: Determine from PDB data
        elif pdb_data:
            method_key = _determine_dominant_method(pdb_data)
        # Priority 3: Use default
        else:
            method_key = 'default'

        # Try to find method-specific template first
        if method_key and method_key != 'default':
            template = _session.query(PromptTemplate).filter(
                PromptTemplate.template_type == 'single',
                PromptTemplate.experimental_method == method_key,
                PromptTemplate.is_default == True
            ).first()

            if template:
                return template

            # Fall back to any template with this method (not just default)
            template = _session.query(PromptTemplate).filter(
                PromptTemplate.template_type == 'single',
                PromptTemplate.experimental_method == method_key
            ).first()

            if template:
                return template

        # Fall back to default template
        template = _session.query(PromptTemplate).filter(
            PromptTemplate.template_type == 'single',
            PromptTemplate.is_default == True
        ).first()

        # Last resort: first single template
        if not template:
            template = _session.query(PromptTemplate).filter(
                PromptTemplate.template_type == 'single'
            ).first()

        return template

    finally:
        if should_close:
            _session.close()


def _determine_dominant_method(pdb_data: Dict) -> str:
    """
    Determine the dominant experimental method from PDB data.

    Args:
        pdb_data: PDB data dict with 'structures' list

    Returns:
        Method key (xray, cryoem, nmr, alphafold, default)
    """
    from collections import Counter

    structures = pdb_data.get('structures', [])
    if not structures:
        return 'default'

    methods = []
    for struct in structures:
        method = struct.get('experimental_method', '')
        if method:
            methods.append(normalize_method(method))

    if not methods:
        return 'default'

    # Count method occurrences and return most common
    method_counts = Counter(methods)

    # Priority order for ties: xray > cryoem > nmr > alphafold > default
    priority_order = ['xray', 'cryoem', 'nmr', 'alphafold', 'default']

    most_common = method_counts.most_common(1)[0][0] if method_counts else 'default'

    # If there's a tie, use priority order
    max_count = method_counts[most_common]
    tied_methods = [m for m, c in method_counts.items() if c == max_count]

    for p in priority_order:
        if p in tied_methods:
            return p

    return most_common


def initialize_templates_on_startup() -> None:
    """
    Called on application startup to ensure templates are in sync.
    1. Import any new templates from files
    2. Export existing templates to files
    """
    logger.info("Initializing templates on startup...")
    result = sync_templates()
    logger.info(f"Template sync complete: imported={result['imported']}, exported={result['exported']}")


# Convenience functions for route handlers

def create_template_with_export(
    name: str,
    content: str,
    description: str = '',
    description_en: str = '',
    is_default: bool = False,
    content_en: str = '',
    name_en: str = '',
    experimental_method: str = None
) -> Optional[Any]:
    """
    Create a template in DB and export to file.

    Returns:
        Created PromptTemplate or None
    """
    from src.database import create_prompt_template

    template = create_prompt_template(
        name=name,
        content=content,
        description=description,
        description_en=description_en,
        is_default=is_default,
        content_en=content_en,
        name_en=name_en,
        experimental_method=experimental_method
    )

    if template:
        method_key = experimental_method if experimental_method else 'default'
        export_template_to_file(template, method_key)

    return template


def update_template_with_export(
    template_id: int,
    updates: Dict[str, Any]
) -> bool:
    """
    Update a template in DB and export to file.

    Returns:
        True if successful
    """
    from src.database import update_prompt_template, get_prompt_template

    success = update_prompt_template(template_id, updates)

    if success:
        template = get_prompt_template(template_id)
        if template:
            method_key = template.experimental_method if hasattr(template, 'experimental_method') and template.experimental_method else 'default'
            export_template_to_file(template, method_key)

    return success
