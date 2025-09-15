# ============================================
# EXAMPLE USAGE
# ============================================

import asyncio
import os
from capstone.agent_v2.hybrid_agent import HybridAgent


async def example_fastapi_project():
    """Example: Create a FastAPI project with full setup"""
    
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Please set OPENAI_API_KEY environment variable")
    
    # Create agent
    agent = HybridAgent(api_key=api_key, model="gpt-4.1-mini")
    
    # Define goal
    goal = """
    Create a production-ready FastAPI project called 'payment-api':
    1. Create the project directory structure
    2. Set up a FastAPI application with proper structure (routers, models, services)
    3. Add health check and basic CRUD endpoints
    4. Create requirements.txt with necessary dependencies
    5. Add a comprehensive README.md
    6. Initialize git repository
    7. Create GitHub repository (if gh CLI is available)
    8. Create initial commit
    9. Push the code to the GitHub repository
    """
    
    # Execute with planning (autonomous mode)
    print("Starting FastAPI project creation...")
    result = await agent.execute_with_planning(goal)
    
    # Print results
    print(f"\nExecution {'succeeded' if result['success'] else 'failed'}")
    print(f"Status: {result.get('status')}")
    print(f"Plan ID: {result.get('plan_id')}")
    print(f"Completed steps: {result.get('completed_steps')}/{result.get('total_steps')}")
    if result.get('plan_file'):
        print(f"Plan saved to: {result['plan_file']}")
    
    # Print statistics
    stats = agent.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total tool calls: {stats['total_calls']}")
    print(f"  Success rate: {stats['overall_success_rate']:.1f}%")
    
    return result

async def example_web_research():
    """Example: Research a topic using web tools"""
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Please set OPENAI_API_KEY environment variable")
    
    agent = HybridAgent(api_key=api_key)
    
    goal = """
    Research the latest developments in quantum computing:
    1. Search for recent news about quantum computing breakthroughs
    2. Find information about major companies working on quantum computers
    3. Create a summary report with the findings
    """
    
    result = await agent.execute_with_function_calling(goal)
    
    print(f"Research {'completed' if result['success'] else 'failed'}")
    return result

async def example_data_processing():
    """Example: Complex data processing with Python tool"""
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Please set OPENAI_API_KEY environment variable")
    
    agent = HybridAgent(api_key=api_key)
    
    goal = """
    Create a data analysis script:
    1. Generate sample sales data (100 records) with date, product, quantity, price
    2. Calculate total revenue by product
    3. Find the best-selling product
    4. Create a summary report
    5. Save the results to a JSON file
    """
    
    result = await agent.execute_with_function_calling(goal)
    
    print(f"Data processing {'completed' if result['success'] else 'failed'}")
    return result

# ============================================
# MAIN ENTRY POINT
# ============================================

def main():
    """Main entry point for testing"""
    import sys
    
    print("HybridAgent - Production Ready")
    print("=" * 50)
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: Please set OPENAI_API_KEY environment variable")
        print("export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)
    
    # Run example based on command line argument
    if len(sys.argv) > 1:
        example = sys.argv[1]
        
        if example == "fastapi":
            asyncio.run(example_fastapi_project())
        elif example == "research":
            asyncio.run(example_web_research())
        elif example == "data":
            asyncio.run(example_data_processing())
        else:
            print(f"Unknown example: {example}")
            print("Available examples: fastapi, research, data")
    else:
        # Run default example
        print("Running FastAPI project example...")
        print("(Use 'python hybrid_agent.py [fastapi|research|data]' for other examples)")
        asyncio.run(example_fastapi_project())

if __name__ == "__main__":
    main()