import click
import yaml

from telliot_kadena.config.kelliot_config import KelliotConfig


@click.group()
def config() -> None:
    """Manage Telliot configuration."""
    pass


@config.command()
def init() -> None:
    """Create initial configuration files."""
    _ = KelliotConfig()


@config.command()
def show() -> None:
    """Show current configuration."""
    cfg = KelliotConfig()
    state = cfg.get_state()

    print(yaml.dump(state, sort_keys=False))
