"""Template Manager for Agent Scripts."""

from typing import Dict, List, Any, Optional
from pathlib import Path
import json
import logging
from string import Template

logger = logging.getLogger(__name__)


class TemplateManager:
    """Manages templates for agent scripts."""

    def __init__(self, templates_dir: Path):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.templates: Dict[str, Dict[str, Any]] = {}
        self._load_all_templates()

    def _load_all_templates(self):
        """Load all template files."""
        for template_file in self.templates_dir.glob("*.json"):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)

                # Process each template in the file
                for template_id, template_info in template_data.items():
                    self.templates[template_id] = template_info

                logger.debug(f"Loaded templates from {template_file}")

            except Exception as e:
                logger.error(f"Failed to load templates from {template_file}: {e}")

    def get_template(self, template_id: str) -> Optional[str]:
        """Get template content by ID."""
        template_info = self.templates.get(template_id)
        if not template_info:
            return None

        return template_info.get("template", "")

    def get_template_info(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get complete template information."""
        return self.templates.get(template_id)

    def format_template(self, template_id: str, variables: Dict[str, Any]) -> Optional[str]:
        """Format template with variables."""
        template_content = self.get_template(template_id)
        if not template_content:
            return None

        try:
            template = Template(template_content)
            return template.safe_substitute(**variables)
        except Exception as e:
            logger.error(f"Failed to format template {template_id}: {e}")
            return None

    def list_templates_by_agent(self, agent_type: str) -> List[Dict[str, Any]]:
        """List templates for a specific agent type."""
        return [
            template for template in self.templates.values()
            if template.get("agent_type") == agent_type
        ]

    def list_templates_by_category(self, category: str) -> List[Dict[str, Any]]:
        """List templates by category."""
        return [
            template for template in self.templates.values()
            if template.get("category") == category
        ]

    def list_templates_by_language(self, language: str) -> List[Dict[str, Any]]:
        """List templates by language."""
        return [
            template for template in self.templates.values()
            if template.get("language") == language
        ]

    def create_template(
        self,
        template_id: str,
        name: str,
        description: str,
        template_content: str,
        agent_type: str,
        category: str,
        language: str = "en",
        variables: Optional[List[str]] = None
    ) -> bool:
        """Create a new template."""
        try:
            template_info = {
                "id": template_id,
                "name": name,
                "description": description,
                "language": language,
                "template": template_content,
                "variables": variables or [],
                "category": category,
                "agent_type": agent_type,
                "created_at": "2024-12-22T13:00:00Z",
                "version": "1.0.0"
            }

            self.templates[template_id] = template_info

            # Save to file based on agent type
            self._save_template_to_file(template_info, agent_type)

            logger.info(f"Created template: {template_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create template {template_id}: {e}")
            return False

    def _save_template_to_file(self, template_info: Dict[str, Any], agent_type: str):
        """Save template to appropriate file."""
        filename = f"{agent_type}_templates.json"
        filepath = self.templates_dir / filename

        # Load existing templates from file
        existing_templates = {}
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_templates = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load existing templates: {e}")

        # Add new template
        existing_templates[template_info["id"]] = template_info

        # Save back to file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(existing_templates, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save template file: {e}")

    def validate_template(self, template_content: str, variables: List[str]) -> List[str]:
        """Validate template and return missing variables."""
        try:
            template = Template(template_content)
            template_content.format(**{var: "test" for var in variables})
            return []  # No missing variables
        except KeyError as e:
            return [str(e).strip("'")]
        except Exception as e:
            return [f"Template error: {str(e)}"]

    def get_variables_from_template(self, template_content: str) -> List[str]:
        """Extract variables from template content."""
        try:
            template = Template(template_content)
            return list(template.pattern.findall(template_content))
        except Exception as e:
            logger.error(f"Failed to extract variables: {e}")
            return []

    def search_templates(self, query: str) -> List[Dict[str, Any]]:
        """Search templates by name, description, or content."""
        query_lower = query.lower()
        results = []

        for template_id, template_info in self.templates.items():
            if (query_lower in template_info.get("name", "").lower() or
                query_lower in template_info.get("description", "").lower() or
                query_lower in template_info.get("template", "").lower()):
                results.append(template_info)

        return results

    def get_template_usage_stats(self, template_id: str) -> Dict[str, Any]:
        """Get usage statistics for a template."""
        template_info = self.templates.get(template_id)
        if not template_info:
            return {}

        # This would be enhanced with actual usage tracking
        return {
            "template_id": template_id,
            "agent_type": template_info.get("agent_type"),
            "category": template_info.get("category"),
            "language": template_info.get("language"),
            "variable_count": len(template_info.get("variables", [])),
            "estimated_usage": 0  # Would track actual usage
        }