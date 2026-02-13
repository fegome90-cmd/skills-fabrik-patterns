"""
Fallback Policies Module

Defines and manages fallback behavior for hook failures.
Ensures predictable behavior when hooks fail or timeout.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

from logger import get_logger, LogLevel

# Module logger
logger = get_logger(__name__)


class FallbackAction(Enum):
    """Action to take when a hook fails."""
    LOG_ONLY = "log_only"
    CONTINUE = "continue"
    CONTINUE_WITH_WARNING = "continue_with_warning"
    CONTINUE_WITH_SUMMARY = "continue_with_summary"
    LOG_AND_WARN = "log_and_warn"
    RETRY_ONCE = "retry_once"
    CRITICAL = "critical"


@dataclass(frozen=True)
class FallbackPolicy:
    """Fallback policy configuration for a specific hook."""
    hook_name: str
    description: str
    on_failure: FallbackAction
    timeout_action: FallbackAction
    user_message: str
    max_retries: int = 0
    retry_delay_ms: int = 1000


class FallbackPolicyManager:
    """Manages fallback behavior for hook failures."""

    def __init__(self, config_path: Path):
        """
        Initialize policy manager from config file.

        Args:
            config_path: Path to fallback.yaml config file
        """
        import yaml
        from yaml import YAMLError

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except (YAMLError, OSError) as e:
            logger.error(f"Failed to load fallback policies from {config_path}: {e}", exc_info=True)
            # Use safe defaults if config fails to load
            self.policies = self._get_default_policies()
            return

        policies_config = config.get('policies', {})
        self.policies: dict[str, FallbackPolicy] = {}

        for hook_name, policy_config in policies_config.items():
            on_failure = self._parse_action(policy_config.get('on_failure', 'log_only'))
            timeout_action = self._parse_action(policy_config.get('timeout_action', 'continue'))

            self.policies[hook_name] = FallbackPolicy(
                hook_name=hook_name,
                description=policy_config.get('description', ''),
                on_failure=on_failure,
                timeout_action=timeout_action,
                user_message=policy_config.get('user_message', ''),
                max_retries=policy_config.get('max_retries', 0),
                retry_delay_ms=policy_config.get('retry_delay_ms', 1000)
            )

        logger.debug(f"Loaded {len(self.policies)} fallback policies", policy_count=len(self.policies))

    def _parse_action(self, action_str: str) -> FallbackAction:
        """Parse action string to FallbackAction enum."""
        action_map = {
            'log_only': FallbackAction.LOG_ONLY,
            'continue': FallbackAction.CONTINUE,
            'continue_with_warning': FallbackAction.CONTINUE_WITH_WARNING,
            'continue_with_summary': FallbackAction.CONTINUE_WITH_SUMMARY,
            'log_and_warn': FallbackAction.LOG_AND_WARN,
            'retry_once': FallbackAction.RETRY_ONCE,
            'critical': FallbackAction.CRITICAL,
        }
        return action_map.get(action_str, FallbackAction.LOG_ONLY)

    def _get_default_policies(self) -> dict[str, FallbackPolicy]:
        """Get safe default policies if config fails to load."""
        return {
            'SessionStart': FallbackPolicy(
                hook_name='SessionStart',
                description='Session start hook',
                on_failure=FallbackAction.LOG_ONLY,
                timeout_action=FallbackAction.CONTINUE,
                user_message='Session start hook failed, continuing anyway'
            ),
            'UserPromptSubmit': FallbackPolicy(
                hook_name='UserPromptSubmit',
                description='User prompt submit hook',
                on_failure=FallbackAction.LOG_ONLY,
                timeout_action=FallbackAction.CONTINUE,
                user_message='Context injection failed, prompt will be sent anyway'
            ),
            'Stop': FallbackPolicy(
                hook_name='Stop',
                description='Stop hook',
                on_failure=FallbackAction.LOG_ONLY,
                timeout_action=FallbackAction.CONTINUE,
                user_message='Quality gates check incomplete, session will end anyway'
            ),
            'PreCompact': FallbackPolicy(
                hook_name='PreCompact',
                description='Pre-compact hook',
                on_failure=FallbackAction.CRITICAL,
                timeout_action=FallbackAction.RETRY_ONCE,
                user_message='Backup creation failed - compaction blocked to prevent data loss',
                max_retries=1
            ),
            'PostToolUse': FallbackPolicy(
                hook_name='PostToolUse',
                description='Post tool use hook',
                on_failure=FallbackAction.LOG_ONLY,
                timeout_action=FallbackAction.CONTINUE,
                user_message='Auto-fix hook failed, continuing without it'
            ),
        }

    def get_policy(self, hook_name: str) -> FallbackPolicy:
        """
        Get fallback policy for a specific hook.

        Args:
            hook_name: Name of the hook (e.g., "Stop", "PreCompact")

        Returns:
            FallbackPolicy for the hook, or a safe default if not found
        """
        if hook_name in self.policies:
            return self.policies[hook_name]

        logger.warning(f"No fallback policy found for '{hook_name}', using LOG_ONLY")
        # Return safe default
        return FallbackPolicy(
            hook_name=hook_name,
            description='Unknown hook',
            on_failure=FallbackAction.LOG_ONLY,
            timeout_action=FallbackAction.CONTINUE,
            user_message=f'{hook_name} hook failed, continuing'
        )

    def handle_failure(
        self,
        hook_name: str,
        error: Exception,
        is_timeout: bool = False
    ) -> tuple[FallbackAction, str]:
        """
        Determine fallback action for a hook failure.

        Args:
            hook_name: Name of the hook that failed
            error: The exception that occurred
            is_timeout: Whether the failure was due to timeout

        Returns:
            Tuple of (action, user_message)
        """
        policy = self.get_policy(hook_name)

        # Use timeout_action if it was a timeout, otherwise on_failure
        action = policy.timeout_action if is_timeout else policy.on_failure

        # Log the failure
        failure_type = "timeout" if is_timeout else "failure"
        logger.warning(
            f"Hook {failure_type}: {hook_name}",
            hook_name=hook_name,
            failure_type=failure_type,
            error=str(error),
            action=action.value
        )

        return action, policy.user_message

    def should_exit_with_error(self, action: FallbackAction) -> bool:
        """
        Determine if hook should exit with error code.

        Args:
            action: The fallback action to evaluate

        Returns:
            True if should exit with error code (1), False otherwise (0)
        """
        return action == FallbackAction.CRITICAL

    def should_retry(self, hook_name: str) -> bool:
        """
        Check if hook should be retried on failure.

        Args:
            hook_name: Name of the hook

        Returns:
            True if retry is configured
        """
        policy = self.get_policy(hook_name)
        return (
            policy.on_failure == FallbackAction.RETRY_ONCE
            or policy.timeout_action == FallbackAction.RETRY_ONCE
        )

    def get_retry_delay_ms(self, hook_name: str) -> int:
        """
        Get retry delay for a hook.

        Args:
            hook_name: Name of the hook

        Returns:
            Delay in milliseconds before retry
        """
        policy = self.get_policy(hook_name)
        return policy.retry_delay_ms


def create_fallback_manager(plugin_root: Path) -> FallbackPolicyManager:
    """
    Convenience function to create fallback policy manager.

    Args:
        plugin_root: Root directory of the plugin

    Returns:
        Configured FallbackPolicyManager instance
    """
    config_path = plugin_root / "config" / "fallback.yaml"
    return FallbackPolicyManager(config_path)
