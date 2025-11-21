"""
Main entry point for the multi-agent framework.
Runs the scheduler to orchestrate the agent workflow.
"""

import logging
from agent import Agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """
    Entry point to run the scheduler.
    Initializes and runs the agent conductor.
    """
    logger.info("Starting Framework Rishi")
    
    # Initialize the agent
    agent = Agent()
    
    # Run the agent workflow
    try:
        agent.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal. Shutting down...")
    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
    finally:
        logger.info("Framework Rishi shutdown complete")


if __name__ == "__main__":
    main()
