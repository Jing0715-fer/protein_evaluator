"""
Template Manager - Handles DB <-> File sync for prompt templates.

Templates are stored in:
- Database: Primary storage for runtime use
- Files in templates/report/: GitHub versioning backup (report templates)
- Files in templates/prompt/: GitHub versioning backup (prompt templates)

Template types:
- 'report': Report templates (output format)
- 'prompt': Prompt templates (for generating statistical summaries)
"""

import os
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Template file directories
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def get_template_dir(template_type: str = 'report') -> Path:
    """Get template directory for a given template type."""
    return TEMPLATE_DIR / template_type


def ensure_template_dir(template_type: str = 'report') -> Path:
    """Ensure template directory exists."""
    template_dir = get_template_dir(template_type)
    template_dir.mkdir(parents=True, exist_ok=True)
    return template_dir


def export_template_to_file(template: Any, template_type: str = 'report') -> bool:
    """
    Export a single template to a markdown file.

    Args:
        template: PromptTemplate model instance
        template_type: Template type (report or prompt)

    Returns:
        True if successful, False otherwise
    """
    try:
        template_dir = ensure_template_dir(template_type)

        # Use template name (sanitized) as filename
        name_slug = ''.join(c if c.isalnum() or c in '-_' else '_' for c in (template.name or 'default'))
        filename = f"{name_slug}.md"
        filepath = template_dir / filename

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
        # Export report templates
        report_templates = session.query(PromptTemplate).filter(
            PromptTemplate.template_type == 'report'
        ).all()

        for template in report_templates:
            if export_template_to_file(template, 'report'):
                count += 1

        # Also export prompt templates
        prompt_templates = session.query(PromptTemplate).filter(
            PromptTemplate.template_type == 'prompt'
        ).all()

        for template in prompt_templates:
            if export_template_to_file(template, 'prompt'):
                count += 1

        logger.info(f"Exported {count} templates to files")
    except Exception as e:
        logger.error(f"Failed to export templates: {e}")
    finally:
        session.close()

    return count


def import_template_from_file(filename: str, template_type: str = 'report') -> Optional[Dict[str, Any]]:
    """
    Import a single template from a markdown file.

    Args:
        filename: Template filename
        template_type: Template type (report or prompt)

    Returns:
        Template data dict or None if file doesn't exist
    """
    template_dir = get_template_dir(template_type)
    filepath = template_dir / filename

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

        # Generate name from filename
        name = filename.replace('.md', '').replace('_', ' ').title()

        return {
            'name': name,
            'name_en': name,
            'content': chinese_content,
            'content_en': english_content,
            'description': f"Auto-imported {template_type} template from file",
            'description_en': f"Auto-imported {template_type} template from file",
            'template_type': template_type,
            'is_default': False
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
        for template_type in ['report', 'prompt']:
            template_dir = get_template_dir(template_type)
            if not template_dir.exists():
                continue

            for filepath in template_dir.glob('*.md'):
                filename = filepath.name

                # Check if template already exists
                existing = session.query(PromptTemplate).filter(
                    PromptTemplate.template_type == template_type,
                    PromptTemplate.name == filename.replace('.md', '').replace('_', ' ').title()
                ).first()

                if existing:
                    continue

                template_data = import_template_from_file(filename, template_type)
                if template_data:
                    template = create_prompt_template(
                        name=template_data['name'],
                        content=template_data['content'],
                        description=template_data['description'],
                        description_en=template_data['description_en'],
                        is_default=template_data['is_default'],
                        content_en=template_data.get('content_en', ''),
                        name_en=template_data.get('name_en', ''),
                        template_type=template_type
                    )
                    if template:
                        count += 1
                        logger.info(f"Imported {template_type} template {filename} from file")

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


def get_default_report_template(session=None) -> Optional[Any]:
    """
    Get the default report template.

    Args:
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
        template = _session.query(PromptTemplate).filter(
            PromptTemplate.template_type == 'report',
            PromptTemplate.is_default == True
        ).first()

        # Fall back to first report template
        if not template:
            template = _session.query(PromptTemplate).filter(
                PromptTemplate.template_type == 'report'
            ).first()

        return template

    finally:
        if should_close:
            _session.close()


def get_default_prompt_template(session=None) -> Optional[Any]:
    """
    Get the default prompt template (for generating statistical summaries).

    Args:
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
        template = _session.query(PromptTemplate).filter(
            PromptTemplate.template_type == 'prompt',
            PromptTemplate.is_default == True
        ).first()

        # Fall back to first prompt template
        if not template:
            template = _session.query(PromptTemplate).filter(
                PromptTemplate.template_type == 'prompt'
            ).first()

        return template

    finally:
        if should_close:
            _session.close()


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
    template_type: str = 'report'
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
        template_type=template_type
    )

    if template:
        export_template_to_file(template, template_type)

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
            export_template_to_file(template, template.template_type)

    return success
