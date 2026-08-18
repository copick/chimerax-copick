"""Portable baseline for logic that does not require a ChimeraX process."""


def test_build_command_preserves_public_command_shape(tool_module):
    command = tool_module.build_command(
        "copick open run",
        "run-1",
        None,
        tomo_type="wbp",
        user_label="label with spaces",
        absent=None,
    )

    assert command == "copick open run run-1 tomo_type wbp user_label 'label with spaces'"
