"""Prompt Manager for Agent Scripts."""

from typing import Dict, List, Any, Optional
from pathlib import Path
import json
import logging
from string import Template

logger = logging.getLogger(__name__)


class PromptManager:
    """Manages prompts for agent scripts."""

    def __init__(self, prompts_dir: Path):
        self.prompts_dir = Path(prompts_dir)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.prompts: Dict[str, Dict[str, Any]] = {}
        self._load_all_prompts()

    def _load_all_prompts(self):
        """Load all prompt files."""
        for prompt_file in self.prompts_dir.glob("*.json"):
            try:
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt_data = json.load(f)

                # Process each prompt in the file
                for prompt_id, prompt_info in prompt_data.items():
                    self.prompts[prompt_id] = prompt_info

                logger.debug(f"Loaded prompts from {prompt_file}")

            except Exception as e:
                logger.error(f"Failed to load prompts from {prompt_file}: {e}")

    def get_prompt(
        self,
        prompt_id: str,
        variables: Optional[Dict[str, Any]] = None,
        prompt_type: str = "base"
    ) -> Optional[str]:
        """Get formatted prompt by ID."""
        prompt_info = self.prompts.get(prompt_id)
        if not prompt_info:
            return None

        prompts = prompt_info.get("prompts", {})
        base_prompt = prompts.get(prompt_type, prompts.get("base", ""))

        if not base_prompt:
            return None

        # Format with variables
        try:
            template = Template(base_prompt)
            return template.safe_substitute(**(variables or {}))
        except Exception as e:
            logger.error(f"Failed to format prompt {prompt_id}: {e}")
            return base_prompt

    def get_prompt_info(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get complete prompt information."""
        return self.prompts.get(prompt_id)

    def get_system_prompt(self, prompt_id: str) -> Optional[str]:
        """Get system prompt for a prompt ID."""
        prompt_info = self.prompts.get(prompt_id)
        return prompt_info.get("system_prompt") if prompt_info else None

    def get_full_prompt(
        self,
        prompt_id: str,
        variables: Optional[Dict[str, Any]] = None,
        prompt_type: str = "base"
    ) -> Optional[Dict[str, str]]:
        """Get both system and user prompts."""
        prompt_info = self.prompts.get(prompt_id)
        if not prompt_info:
            return None

        return {
            "system_prompt": prompt_info.get("system_prompt", ""),
            "user_prompt": self.get_prompt(prompt_id, variables, prompt_type) or ""
        }

    def list_prompts_by_agent(self, agent_type: str) -> List[Dict[str, Any]]:
        """List prompts for a specific agent type."""
        return [
            prompt for prompt in self.prompts.values()
            if prompt.get("agent_type") == agent_type
        ]

    def list_prompts_by_category(self, category: str) -> List[Dict[str, Any]]:
        """List prompts by category."""
        return [
            prompt for prompt in self.prompts.values()
            if prompt.get("category") == category
        ]

    def list_prompts_by_language(self, language: str) -> List[Dict[str, Any]]:
        """List prompts by language."""
        return [
            prompt for prompt in self.prompts.values()
            if prompt.get("language") == language
        ]

    def create_prompt(
        self,
        prompt_id: str,
        name: str,
        description: str,
        system_prompt: str,
        user_prompts: Dict[str, str],
        agent_type: str,
        category: str,
        language: str = "en",
        variables: Optional[List[str]] = None
    ) -> bool:
        """Create a new prompt."""
        try:
            prompt_info = {
                "id": prompt_id,
                "name": name,
                "description": description,
                "language": language,
                "system_prompt": system_prompt,
                "prompts": user_prompts,
                "variables": variables or [],
                "category": category,
                "agent_type": agent_type,
                "created_at": "2024-12-22T13:00:00Z",
                "version": "1.0.0"
            }

            self.prompts[prompt_id] = prompt_info

            # Save to file based on agent type
            self._save_prompt_to_file(prompt_info, agent_type)

            logger.info(f"Created prompt: {prompt_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create prompt {prompt_id}: {e}")
            return False

    def _save_prompt_to_file(self, prompt_info: Dict[str, Any], agent_type: str):
        """Save prompt to appropriate file."""
        filename = f"{agent_type}_prompts.json"
        filepath = self.prompts_dir / filename

        # Load existing prompts from file
        existing_prompts = {}
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_prompts = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load existing prompts: {e}")

        # Add new prompt
        existing_prompts[prompt_info["id"]] = prompt_info

        # Save back to file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(existing_prompts, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save prompt file: {e}")

    def get_prompt_types(self, prompt_id: str) -> List[str]:
        """Get available prompt types for a prompt ID."""
        prompt_info = self.prompts.get(prompt_id)
        if not prompt_info:
            return []

        return list(prompt_info.get("prompts", {}).keys())

    def validate_prompt_variables(
        self,
        prompt_id: str,
        variables: Dict[str, Any],
        prompt_type: str = "base"
    ) -> List[str]:
        """Validate that all required variables are provided."""
        prompt_info = self.prompts.get(prompt_id)
        if not prompt_info:
            return ["Prompt not found"]

        required_vars = set(prompt_info.get("variables", []))
        provided_vars = set(variables.keys())
        missing_vars = required_vars - provided_vars

        return list(missing_vars)

    def extract_variables_from_prompt(self, prompt_content: str) -> List[str]:
        """Extract variables from prompt content."""
        try:
            import re
            # Find {variable} patterns
            variables = re.findall(r'\{(\w+)\}', prompt_content)
            return list(set(variables))
        except Exception as e:
            logger.error(f"Failed to extract variables: {e}")
            return []

    def search_prompts(self, query: str) -> List[Dict[str, Any]]:
        """Search prompts by name, description, or content."""
        query_lower = query.lower()
        results = []

        for prompt_id, prompt_info in self.prompts.items():
            if (query_lower in prompt_info.get("name", "").lower() or
                query_lower in prompt_info.get("description", "").lower() or
                query_lower in prompt_info.get("system_prompt", "").lower() or
                any(query_lower in content.lower()
                    for content in prompt_info.get("prompts", {}).values())):
                results.append(prompt_info)

        return results

    def combine_prompts(
        self,
        prompt_ids: List[str],
        variables: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, str]]:
        """Combine multiple prompts into one."""
        if not prompt_ids:
            return None

        combined_system = ""
        combined_user = ""

        for prompt_id in prompt_ids:
            full_prompt = self.get_full_prompt(prompt_id, variables)
            if full_prompt:
                if full_prompt["system_prompt"]:
                    combined_system += full_prompt["system_prompt"] + "\n\n"
                if full_prompt["user_prompt"]:
                    combined_user += full_prompt["user_prompt"] + "\n\n"

        return {
            "system_prompt": combined_system.strip(),
            "user_prompt": combined_user.strip()
        }

    def get_prompt_usage_stats(self, prompt_id: str) -> Dict[str, Any]:
        """Get usage statistics for a prompt."""
        prompt_info = self.prompts.get(prompt_id)
        if not prompt_info:
            return {}

        return {
            "prompt_id": prompt_id,
            "agent_type": prompt_info.get("agent_type"),
            "category": prompt_info.get("category"),
            "language": prompt_info.get("language"),
            "variable_count": len(prompt_info.get("variables", [])),
            "prompt_types": list(prompt_info.get("prompts", {}).keys()),
            "estimated_usage": 0  # Would track actual usage
        }