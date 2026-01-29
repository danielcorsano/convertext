"""CLI interface for convertext."""

import click
from pathlib import Path
from typing import Optional

from convertext import __version__
from convertext.config import Config
from convertext.core import ConversionEngine
from convertext.registry import get_registry
from convertext.converters.loader import load_converters


@click.command()
@click.argument('files', nargs=-1, type=click.Path(exists=True), required=False)
@click.option(
    '--format', '-f',
    'output_formats',
    help='Output format(s), comma-separated (e.g., epub,pdf,mobi)'
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
        formats = registry.list_supported_formats()
        if not formats:
            click.echo("No converters registered yet.")
            return
        click.echo("Supported format conversions:\n")
        for source, targets in sorted(formats.items()):
            click.echo(f"  {source.upper()} → {', '.join(t.upper() for t in sorted(set(targets)))}")
        return

    if not files:
        click.echo("Error: No input files specified")
        click.echo("Run 'convertext --help' for usage information")
        return

    if not output_formats:
        click.echo("Error: No output format specified (use --format)")
        return

    cfg = Config()
    if config:
        cfg.override(cfg._load_yaml(Path(config)))

    overrides = {}
    if output:
        overrides['output'] = {'directory': output}
    if overwrite:
        overrides['output'] = overrides.get('output', {})
        overrides['output']['overwrite'] = True

    if overrides:
        cfg.override(overrides)

    formats = [f.strip().lower() for f in output_formats.split(',')]
    engine = ConversionEngine(cfg, keep_intermediate=keep_intermediate)
    source_files = [Path(f) for f in files]
    success_count = 0
    fail_count = 0

    with click.progressbar(
        source_files,
        label='Converting files',
        show_pos=True
    ) as bar:
        for source in bar:
            for fmt in formats:
                result = engine.convert(source, fmt)
                if result.success:
                    success_count += 1
                    if verbose:
                        hop_info = ""
                        if result.hops > 1 and result.conversion_path:
                            path_str = " → ".join(f.upper() for f in result.conversion_path)
                            hop_info = f" ({path_str}, {result.hops} hops)"
                        click.echo(f"\n✓ {source.name} → {result.target_path.name}{hop_info}")
                else:
                    fail_count += 1
                    click.echo(f"\n✗ {source.name} → {fmt}: {result.error}")

    click.echo(f"\nCompleted: {success_count} successful, {fail_count} failed")


if __name__ == '__main__':
    main()
