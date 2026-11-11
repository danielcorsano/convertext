"""CLI interface for convertext."""

import click
from pathlib import Path
from typing import Any, Dict, Optional

from convertext import __version__
from convertext.config import Config
from convertext.core import ConversionEngine
from convertext.registry import get_registry
from convertext.converters.loader import load_converters

BETA_OUTPUTS = {'azw3'}  # output formats not yet reliable on all devices


@click.command()
@click.argument('files', nargs=-1, type=click.Path(exists=True), required=False)
@click.option(
    '--format', '-f',
    'output_formats',
    help='Output format(s), comma-separated (e.g., epub,pdf,txt)'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='Output directory (default: same as source)'
)
@click.option(
    '--config', '-c',
    type=click.Path(exists=True),
    help='Path to custom config file'
)
@click.option(
    '--overwrite',
    is_flag=True,
    help='Overwrite existing files'
)
@click.option(
    '--list-formats',
    is_flag=True,
    help='List all supported formats'
)
@click.option(
    '--init-config',
    is_flag=True,
    help='Initialize user config file'
)
@click.option(
    '--version',
    is_flag=True,
    help='Show version'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Verbose output'
)
@click.option(
    '--keep-intermediate',
    is_flag=True,
    help='Keep intermediate files in multi-hop conversions'
)
def main(
    files: tuple,
    output_formats: Optional[str],
    output: Optional[str],
    config: Optional[str],
    overwrite: bool,
    list_formats: bool,
    init_config: bool,
    version: bool,
    verbose: bool,
    keep_intermediate: bool
):
    """ConvertExt - Lightweight universal text converter."""

    load_converters()

    if version:
        click.echo(f"convertext {__version__}")
        return

    if init_config:
        Config.init_user_config()
        click.echo("Initialized config file at ~/.convertext/config.yaml")
        return

    if list_formats:
        registry = get_registry()
        supported = registry.list_supported_formats()
        if not supported:
            click.echo("No converters registered yet.")
            return
        click.echo("Supported format conversions:\n")
        for source_fmt, targets in sorted(supported.items()):
            names = [t.upper() + (' (beta)' if t in BETA_OUTPUTS else '')
                     for t in sorted(set(targets))]
            click.echo(f"  {source_fmt.upper()} → {', '.join(names)}")
        if any(t in BETA_OUTPUTS for targets in supported.values() for t in targets):
            click.echo("\n  (beta) = not yet reliable on all devices")
        return

    if not files:
        click.echo("Error: No input files specified")
        click.echo("Run 'convertext --help' for usage information")
        raise SystemExit(2)

    if not output_formats:
        click.echo("Error: No output format specified (use --format)")
        raise SystemExit(2)

    cfg = Config()
    if config:
        cfg.override(cfg._load_yaml(Path(config)))

    overrides: Dict[str, Any] = {}
    if output:
        overrides['output'] = {'directory': output}
    if overwrite:
        overrides['output'] = overrides.get('output', {})
        overrides['output']['overwrite'] = True

    target_formats = [f.strip().lower() for f in output_formats.split(',')]
    engine = ConversionEngine(cfg, keep_intermediate=keep_intermediate, overrides=overrides)
    source_files = [Path(f) for f in files]
    success_count = 0
    fail_count = 0

    with click.progressbar(
        source_files,
        label='Converting files',
        show_pos=True
    ) as bar:
        for source in bar:
            for fmt in target_formats:
                result = engine.convert(source, fmt)
                if result.success:
                    success_count += 1
                    if verbose:
                        hop_info = ""
                        if result.hops > 1 and result.conversion_path:
                            path_str = " → ".join(f.upper() for f in result.conversion_path)
                            hop_info = f" ({path_str}, {result.hops} hops)"
                        target = result.target_path.name if result.target_path else fmt
                        click.echo(f"\n✓ {source.name} → {target}{hop_info}")
                else:
                    fail_count += 1
                    click.echo(f"\n✗ {source.name} → {fmt}: {result.error}")

    click.echo(f"\nCompleted: {success_count} successful, {fail_count} failed")


if __name__ == '__main__':
    main()
