import typer

app = typer.Typer(
    name="snapshot",
    help="TTS Snapshot CI — catch review-worthy changes in rendered speech.",
    invoke_without_command=True,
    no_args_is_help=True,
)


@app.callback()
def _main() -> None:
    """TTS Snapshot CI — catch review-worthy changes in rendered speech."""
