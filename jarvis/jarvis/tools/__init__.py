from .registry import Context, Registry, Tool, ToolError  # noqa: F401


def build_registry() -> Registry:
    from . import android, core, crm, files, video, web, youtube

    reg = Registry()
    for module in (core, files, video, youtube, crm, web, android):
        module.register(reg)
    return reg
