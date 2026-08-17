from bell_mcp_platform import mcp
from pathlib import Path

@mcp.tool()
async def read_md(tool_name: str) -> str:
    """
    Retrieve the detailed markdown documentation for a specific tool.
    
    Args:
        tool_name: The exact name of the tool (e.g., "fizzbuzz", "example_tool")
    
    Returns:
        Full markdown documentation content as a string
    
    Raises:
        FileNotFoundError: If no documentation exists for the specified tool
    """
    
    # Base tools directory (parent of this file)
    tools_dir = Path(__file__).parent
    
    # Search for {tool_name}.md files recursively
    md_files = list(tools_dir.rglob(f"{tool_name}.md"))
    
    if not md_files:
        # List available documentation
        available_tools = _list_available_docs(tools_dir)
        raise FileNotFoundError(
            f"No documentation found for '{tool_name}'.\n"
            f"Available tools with documentation: {', '.join(available_tools) if available_tools else 'None'}"
        )
    
    # Read the first matching file
    md_file = md_files[0]
    
    try:
        content = md_file.read_text(encoding='utf-8')
        return f"Documentation for '{tool_name}':\n\n{content}"
    except Exception as e:
        raise RuntimeError(f"Error reading documentation file {md_file.name}: {str(e)}")


def _list_available_docs(tools_dir: Path) -> list[str]:
    """Helper to list all available .md documentation files"""
    md_files = tools_dir.rglob("*.md")
    # Extract tool names (file stems), exclude README files
    tool_names = sorted(set(
        f.stem for f in md_files 
        if f.stem.lower() not in ["readme", "skill"]
    ))
    return tool_names