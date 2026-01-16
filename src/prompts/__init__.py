# Промпты для генерации тестов

from .qa_prompts import (
    SYSTEM_PROMPT,
    FEW_SHOT_EXAMPLE,
    TEST_DESIGN_TECHNIQUES,
    GENERATE_TESTS_PROMPT,
    TECHNIQUE_PROMPTS,
    CLI_AGENT_SYSTEM_PROMPT,
    CLI_AGENT_STATE_MANAGEMENT,
    CLI_AGENT_WORKFLOW,
    CLI_AGENT_TECHNIQUES_GUIDE,
    CLI_AGENT_OUTPUT_FORMAT,
    CLI_AGENT_FULL_PROMPT,
    get_full_techniques_prompt,
    get_selected_techniques_prompt,
    build_generation_prompt,
    get_cli_agent_prompt,
)

__all__ = [
    "SYSTEM_PROMPT",
    "FEW_SHOT_EXAMPLE",
    "TEST_DESIGN_TECHNIQUES",
    "GENERATE_TESTS_PROMPT",
    "TECHNIQUE_PROMPTS",
    "CLI_AGENT_SYSTEM_PROMPT",
    "CLI_AGENT_STATE_MANAGEMENT",
    "CLI_AGENT_WORKFLOW",
    "CLI_AGENT_TECHNIQUES_GUIDE",
    "CLI_AGENT_OUTPUT_FORMAT",
    "CLI_AGENT_FULL_PROMPT",
    "get_full_techniques_prompt",
    "get_selected_techniques_prompt",
    "build_generation_prompt",
    "get_cli_agent_prompt",
]
