"""CLI exit-code tests: usage errors must fail nonzero."""

from click.testing import CliRunner

from convertext.cli import main


def test_no_input_files_exits_nonzero():
    result = CliRunner().invoke(main, [])
    assert result.exit_code == 2
    assert "No input files specified" in result.output


def test_missing_output_format_exits_nonzero(tmp_path):
    source = tmp_path / "sample.txt"
    source.write_text("Hello")
    result = CliRunner().invoke(main, [str(source)])
    assert result.exit_code == 2
    assert "No output format specified" in result.output
