"""Agent Script Manager - Central management for agent scripts and workflows."""

from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import json
import yaml
from datetime import datetime
import logging

from .templates import TemplateManager
from .prompts import PromptManager

logger = logging.getLogger(__name__)


class ScriptManager:
    """Central manager for all agent scripts, templates, and prompts."""

    def __init__(self, base_dir: str = "src/agentscripts"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Initialize sub-managers
        self.template_manager = TemplateManager(self.base_dir / "templates")
        self.prompt_manager = PromptManager(self.base_dir / "prompts")

        # Script registry
        self.scripts: Dict[str, Dict[str, Any]] = {}
        self._load_all_scripts()

    def _load_all_scripts(self):
        """Load all registered scripts."""
        scripts_file = self.base_dir / "scripts.json"

        if scripts_file.exists():
            try:
                with open(scripts_file, 'r', encoding='utf-8') as f:
                    self.scripts = json.load(f)
                logger.info(f"Loaded {len(self.scripts)} agent scripts")
            except Exception as e:
                logger.error(f"Failed to load scripts registry: {e}")
                self.scripts = {}

        # Auto-discover scripts in subdirectories
        self._discover_scripts()

    def _discover_scripts(self):
        """Auto-discover scripts from subdirectories."""
        for agent_dir in self.base_dir.iterdir():
            if agent_dir.is_dir() and agent_dir.name not in ["templates", "prompts", "workflows"]:
                for script_file in agent_dir.glob("*.json"):
                    try:
                        with open(script_file, 'r', encoding='utf-8') as f:
                            script_data = json.load(f)

                        script_id = f"{agent_dir.name}/{script_file.stem}"
                        script_data.update({
                            "id": script_id,
                            "agent_type": agent_dir.name,
                            "file_path": str(script_file)
                        })

                        self.scripts[script_id] = script_data
                        logger.debug(f"Discovered script: {script_id}")

                    except Exception as e:
                        logger.warning(f"Failed to load script {script_file}: {e}")

    def register_script(
        self,
        script_id: str,
        agent_type: str,
        name: str,
        description: str,
        template_id: Optional[str] = None,
        prompt_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Register a new agent script."""
        try:
            script_data = {
                "id": script_id,
                "agent_type": agent_type,
                "name": name,
                "description": description,
                "template_id": template_id,
                "prompt_id": prompt_id,
                "config": config or {},
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "version": "1.0.0"
            }

            self.scripts[script_id] = script_data
            self._save_scripts_registry()

            logger.info(f"Registered script: {script_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to register script {script_id}: {e}")
            return False

    def get_script(self, script_id: str) -> Optional[Dict[str, Any]]:
        """Get script by ID."""
        return self.scripts.get(script_id)

    def list_scripts_by_agent(self, agent_type: str) -> List[Dict[str, Any]]:
        """List all scripts for a specific agent type."""
        return [
            script for script in self.scripts.values()
            if script.get("agent_type") == agent_type
        ]

    def list_all_scripts(self) -> List[Dict[str, Any]]:
        """List all registered scripts."""
        return list(self.scripts.values())

    def execute_script(
        self,
        script_id: str,
        context: Dict[str, Any],
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a script with given context and variables."""
        script = self.get_script(script_id)
        if not script:
            raise ValueError(f"Script not found: {script_id}")

        try:
            # Get template if specified
            template_content = None
            if script.get("template_id"):
                template_content = self.template_manager.get_template(
                    script["template_id"]
                )

            # Get prompt if specified
            prompt_content = None
            if script.get("prompt_id"):
                prompt_content = self.prompt_manager.get_prompt(
                    script["prompt_id"], variables or {}
                )

            # Combine all components
            execution_context = {
                "script": script,
                "template": template_content,
                "prompt": prompt_content,
                "context": context,
                "variables": variables or {},
                "config": script.get("config", {})
            }

            # Process based on agent type
            result = self._process_script_by_agent_type(
                script["agent_type"], execution_context
            )

            return {
                "success": True,
                "script_id": script_id,
                "result": result,
                "execution_time": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to execute script {script_id}: {e}")
            return {
                "success": False,
                "script_id": script_id,
                "error": str(e),
                "execution_time": datetime.now().isoformat()
            }

    def _process_script_by_agent_type(
        self,
        agent_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process script based on agent type."""
        script = context["script"]
        config = script.get("config", {})

        if agent_type == "analyzer":
            return self._process_analyzer_script(context)
        elif agent_type == "script":
            return self._process_script_agent_script(context)
        elif agent_type == "audio":
            return self._process_audio_script(context)
        elif agent_type == "visual":
            return self._process_visual_script(context)
        elif agent_type == "camera":
            return self._process_camera_script(context)
        elif agent_type == "merge":
            return self._process_merge_script(context)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

    def _process_analyzer_script(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process analyzer agent script."""
        prompt = context.get("prompt", context["context"].get("prompt", ""))

        # Use custom prompt or template
        if context["prompt"]:
            analysis_prompt = context["prompt"]
        elif context["template"]:
            analysis_prompt = context["template"].format(**context["variables"])
        else:
            analysis_prompt = f"Analyze this prompt for video generation: {prompt}"

        return {
            "type": "analysis",
            "prompt": analysis_prompt,
            "config": context["config"],
            "expected_output": context["script"].get("metadata", {}).get("expected_output", {})
        }

    def _process_script_agent_script(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process script agent script."""
        analysis_result = context["context"].get("analysis_result", {})

        if context["prompt"]:
            script_prompt = context["prompt"]
        elif context["template"]:
            script_prompt = context["template"].format(
                analysis=analysis_result, **context["variables"]
            )
        else:
            script_prompt = f"Generate a script based on this analysis: {analysis_result}"

        return {
            "type": "script_generation",
            "prompt": script_prompt,
            "config": context["config"],
            "analysis": analysis_result
        }

    def _process_audio_script(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process audio agent script."""
        narration = context["context"].get("narration", "")
        storyboard = context["context"].get("storyboard", [])

        return {
            "type": "audio_generation",
            "narration": narration,
            "storyboard": storyboard,
            "config": context["config"],
            "voice_settings": context["config"].get("voice_settings", {})
        }

    def _process_visual_script(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process visual agent script."""
        storyboard = context["context"].get("storyboard", [])
        analysis = context["context"].get("analysis_result", {})

        return {
            "type": "image_generation",
            "storyboard": storyboard,
            "analysis": analysis,
            "config": context["config"],
            "style_settings": context["config"].get("style_settings", {})
        }

    def _process_camera_script(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process camera agent script."""
        storyboard = context["context"].get("storyboard", [])

        return {
            "type": "animation_generation",
            "storyboard": storyboard,
            "config": context["config"],
            "animation_settings": context["config"].get("animation_settings", {})
        }

    def _process_merge_script(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process merge agent script."""
        audio_result = context["context"].get("audio_result", {})
        visual_result = context["context"].get("visual_result", {})
        camera_result = context["context"].get("camera_result", {})
        storyboard = context["context"].get("storyboard", [])

        return {
            "type": "video_merging",
            "audio_result": audio_result,
            "visual_result": visual_result,
            "camera_result": camera_result,
            "storyboard": storyboard,
            "config": context["config"]
        }

    def _save_scripts_registry(self):
        """Save scripts registry to file."""
        scripts_file = self.base_dir / "scripts.json"

        try:
            with open(scripts_file, 'w', encoding='utf-8') as f:
                json.dump(self.scripts, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save scripts registry: {e}")

    def update_script(self, script_id: str, updates: Dict[str, Any]) -> bool:
        """Update an existing script."""
        if script_id not in self.scripts:
            return False

        try:
            self.scripts[script_id].update(updates)
            self.scripts[script_id]["updated_at"] = datetime.now().isoformat()
            self._save_scripts_registry()

            logger.info(f"Updated script: {script_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update script {script_id}: {e}")
            return False

    def delete_script(self, script_id: str) -> bool:
        """Delete a script."""
        if script_id not in self.scripts:
            return False

        try:
            del self.scripts[script_id]
            self._save_scripts_registry()

            logger.info(f"Deleted script: {script_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete script {script_id}: {e}")
            return False

    def create_workflow_script(
        self,
        workflow_name: str,
        agent_sequence: List[str],
        global_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Create a workflow script that coordinates multiple agents."""
        workflow_id = f"workflow_{workflow_name.lower().replace(' ', '_')}"

        script_data = {
            "id": workflow_id,
            "agent_type": "workflow",
            "name": workflow_name,
            "description": f"Workflow: {' → '.join(agent_sequence)}",
            "agent_sequence": agent_sequence,
            "global_config": global_config or {},
            "metadata": {
                "type": "workflow",
                "agents": agent_sequence,
                "created_for": "multi_agent_coordination"
            }
        }

        return self.register_script(**script_data)

    def get_workflow_execution_plan(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get execution plan for a workflow."""
        script = self.get_script(workflow_id)
        if not script or script.get("agent_type") != "workflow":
            return None

        agent_sequence = script.get("agent_sequence", [])
        execution_plan = []

        for i, agent_id in enumerate(agent_sequence):
            agent_script_id = next(
                (sid for sid, s in self.scripts.items()
                 if s.get("agent_type") == agent_id and s.get("is_primary", False)),
                None
            )

            if agent_script_id:
                execution_plan.append({
                    "step": i + 1,
                    "agent_type": agent_id,
                    "script_id": agent_script_id,
                    "dependencies": agent_sequence[:i]  # Previous agents
                })

        return {
            "workflow_id": workflow_id,
            "workflow_name": script.get("name"),
            "execution_plan": execution_plan,
            "total_steps": len(execution_plan),
            "estimated_time": sum(
                self.scripts[step["script_id"]].get("metadata", {}).get("estimated_time", 30)
                for step in execution_plan
            )
        }


# Global script manager instance
script_manager = ScriptManager()