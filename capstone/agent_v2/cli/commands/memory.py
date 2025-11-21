"""Memory management CLI commands (Story 4.3)."""

import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from capstone.agent_v2.memory.memory_manager import MemoryManager

console = Console()
memory_app = typer.Typer(help="Manage agent memory (learned skills)")


@memory_app.command("list")
def list_memories(
    work_dir: str = typer.Option("./agent_work", "--work-dir", "-w", help="Work directory containing memory"),
    min_success: int = typer.Option(0, "--min-success", "-s", help="Minimum success count filter"),
    tool: Optional[str] = typer.Option(None, "--tool", "-t", help="Filter by tool name")
):
    """List all stored memories (learned skills)."""
    
    try:
        memory_dir = f"{work_dir}/memory"
        memory_manager = MemoryManager(
            memory_dir=memory_dir,
            enable_memory=True,
            auto_prune=False
        )
        
        memories = asyncio.run(memory_manager.list_all_memories())
        
        # Apply filters
        if min_success > 0:
            memories = [m for m in memories if m.success_count >= min_success]
        
        if tool:
            memories = [m for m in memories if m.tool_name == tool]
        
        if not memories:
            console.print("[yellow]No memories found[/yellow]")
            return
        
        # Create table
        table = Table(title=f"Learned Skills ({len(memories)} total)")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Context", style="white")
        table.add_column("Lesson", style="green")
        table.add_column("Tool", style="magenta")
        table.add_column("Success Count", style="yellow", justify="right")
        table.add_column("Last Used", style="blue")
        
        for mem in memories:
            # Truncate long text
            context_short = mem.context[:50] + "..." if len(mem.context) > 50 else mem.context
            lesson_short = mem.lesson[:50] + "..." if len(mem.lesson) > 50 else mem.lesson
            tool_name = mem.tool_name or "-"
            
            # Format last used date
            from datetime import datetime
            try:
                last_used_dt = datetime.fromisoformat(mem.last_used)
                last_used_str = last_used_dt.strftime("%Y-%m-%d")
            except:
                last_used_str = mem.last_used[:10] if len(mem.last_used) >= 10 else mem.last_used
            
            table.add_row(
                mem.id[:8],
                context_short,
                lesson_short,
                tool_name,
                str(mem.success_count),
                last_used_str
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@memory_app.command("delete")
def delete_memory(
    memory_id: str = typer.Argument(..., help="Memory ID to delete (first 8 chars or full ID)"),
    work_dir: str = typer.Option("./agent_work", "--work-dir", "-w", help="Work directory containing memory"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Delete a specific memory by ID."""
    
    try:
        memory_dir = f"{work_dir}/memory"
        memory_manager = MemoryManager(
            memory_dir=memory_dir,
            enable_memory=True,
            auto_prune=False
        )
        
        # Get all memories to find matching ID
        memories = asyncio.run(memory_manager.list_all_memories())
        
        # Find memory by partial or full ID
        matching_memory = None
        for mem in memories:
            if mem.id == memory_id or mem.id.startswith(memory_id):
                matching_memory = mem
                break
        
        if not matching_memory:
            console.print(f"[red]Memory with ID '{memory_id}' not found[/red]")
            raise typer.Exit(code=1)
        
        # Show memory details
        console.print("\n[yellow]Memory to delete:[/yellow]")
        console.print(f"  ID: {matching_memory.id}")
        console.print(f"  Context: {matching_memory.context}")
        console.print(f"  Lesson: {matching_memory.lesson}")
        console.print(f"  Success Count: {matching_memory.success_count}\n")
        
        # Confirm deletion
        if not force:
            confirm = typer.confirm("Are you sure you want to delete this memory?")
            if not confirm:
                console.print("[yellow]Deletion cancelled[/yellow]")
                raise typer.Exit(code=0)
        
        # Delete memory
        result = asyncio.run(memory_manager.delete_memory(matching_memory.id))
        
        if result:
            console.print(f"[green]✓ Deleted memory {matching_memory.id[:8]}[/green]")
        else:
            console.print(f"[red]Failed to delete memory[/red]")
            raise typer.Exit(code=1)
            
    except Exception as e:
        if "not found" not in str(e).lower():
            console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@memory_app.command("stats")
def memory_stats(
    work_dir: str = typer.Option("./agent_work", "--work-dir", "-w", help="Work directory containing memory")
):
    """Show memory statistics."""
    
    try:
        memory_dir = f"{work_dir}/memory"
        memory_manager = MemoryManager(
            memory_dir=memory_dir,
            enable_memory=True,
            auto_prune=False
        )
        
        memories = asyncio.run(memory_manager.list_all_memories())
        
        if not memories:
            console.print("[yellow]No memories found[/yellow]")
            return
        
        # Calculate statistics
        total_memories = len(memories)
        total_success = sum(m.success_count for m in memories)
        avg_success = total_success / total_memories if total_memories > 0 else 0
        
        # Count by tool
        tool_counts = {}
        for mem in memories:
            tool = mem.tool_name or "No Tool"
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
        
        # Count by success
        unused_count = len([m for m in memories if m.success_count == 0])
        used_count = len([m for m in memories if m.success_count > 0])
        
        # Display stats
        console.print("\n[bold cyan]Memory Statistics[/bold cyan]\n")
        console.print(f"  Total Memories: {total_memories}")
        console.print(f"  Total Success Count: {total_success}")
        console.print(f"  Average Success Count: {avg_success:.2f}")
        console.print(f"  Used Memories: {used_count}")
        console.print(f"  Unused Memories: {unused_count}\n")
        
        # Create tool breakdown table
        tool_table = Table(title="Memories by Tool")
        tool_table.add_column("Tool", style="magenta")
        tool_table.add_column("Count", justify="right", style="yellow")
        
        for tool, count in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True):
            tool_table.add_row(tool, str(count))
        
        console.print(tool_table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@memory_app.command("prune")
def prune_stale_memories(
    work_dir: str = typer.Option("./agent_work", "--work-dir", "-w", help="Work directory containing memory"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Prune stale memories (unused for 90 days or unused after 30 days with success_count=0)."""
    
    try:
        memory_dir = f"{work_dir}/memory"
        memory_manager = MemoryManager(
            memory_dir=memory_dir,
            enable_memory=True,
            auto_prune=False
        )
        
        if not force:
            console.print("[yellow]This will remove memories that are:[/yellow]")
            console.print("  - Unused for 90+ days")
            console.print("  - Created 30+ days ago with success_count=0\n")
            
            confirm = typer.confirm("Continue with pruning?")
            if not confirm:
                console.print("[yellow]Pruning cancelled[/yellow]")
                raise typer.Exit(code=0)
        
        # Prune memories
        count = asyncio.run(memory_manager.prune_stale_memories())
        
        if count > 0:
            console.print(f"[green]✓ Pruned {count} stale memories[/green]")
        else:
            console.print("[cyan]No stale memories found[/cyan]")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)

