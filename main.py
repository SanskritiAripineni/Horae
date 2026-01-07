"""
LLM Scheduler Agent - Entry Point
"""

import logging
import argparse
from agent import LLMSchedulerAgent

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    
    agent = LLMSchedulerAgent()
    if args.quick:
        print("Running quick check...")
    else:
        result = agent.run()
        print(f"Result: {result}")

if __name__ == "__main__":
    main()
