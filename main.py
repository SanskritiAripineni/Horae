"""
LLM Scheduler Agent - Interactive Entry Point
"""

# Python 3.9 compatibility fix - must be before other imports
import sys
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

if sys.version_info < (3, 10):
    import importlib.metadata
    if not hasattr(importlib.metadata, 'packages_distributions'):
        importlib.metadata.packages_distributions = lambda: {}

import logging
import argparse
import json
from datetime import datetime
from agent import LLMSchedulerAgent

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logging.getLogger('chromadb').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('google').setLevel(logging.WARNING)


def format_analysis(results: dict) -> str:
    """Format the analysis section with clean, readable output."""
    lines = []
    
    lines.append("\n" + "=" * 70)
    lines.append("  MENTAL HEALTH ANALYSIS")
    lines.append("=" * 70)
    
    # Journal info
    if results.get('journal_count'):
        lines.append(f"\n  Recent {results['journal_count']} Journals Analyzed")
    
    # Summary
    if results.get('journal_summary'):
        lines.append(f"\n  SUMMARY")
        lines.append(f"  {'-' * 50}")
        # Wrap long text
        summary = results['journal_summary']
        words = summary.split()
        current_line = "  "
        for word in words:
            if len(current_line) + len(word) > 75:
                lines.append(current_line)
                current_line = "  " + word + " "
            else:
                current_line += word + " "
        if current_line.strip():
            lines.append(current_line)
    
    # Mental health assessment
    mh = results.get('mental_health', {})
    if mh:
        lines.append(f"\n  ASSESSMENT")
        lines.append(f"  {'-' * 50}")
        risk = mh.get('risk_level', 'unknown').upper()
        phq4 = mh.get('estimated_phq4', '?')
        lines.append(f"  Risk Level: {risk}  |  PHQ-4 Estimate: {phq4}/12")
        
        if mh.get('key_concerns'):
            lines.append(f"\n  Concerns:")
            for c in mh['key_concerns'][:3]:
                # Truncate long concerns
                if len(c) > 80:
                    c = c[:77] + "..."
                lines.append(f"    - {c}")
        
        if mh.get('positive_indicators'):
            lines.append(f"\n  Positives:")
            for p in mh['positive_indicators'][:3]:
                if len(p) > 80:
                    p = p[:77] + "..."
                lines.append(f"    + {p}")
    
    # Calendar summary
    cal = results.get('calendar_summary', {})
    if cal:
        lines.append(f"\n  SCHEDULE (Next 7 days)")
        lines.append(f"  {'-' * 50}")
        lines.append(f"  Events: {cal.get('event_count', 0)}  |  Tasks: {cal.get('task_count', 0)}  |  Hours: {cal.get('total_hours', 0)}")
        
        if cal.get('events'):
            lines.append(f"\n  Upcoming Events:")
            for e in cal['events'][:8]:
                lines.append(f"    [{e['start']}] {e['title']}")
        
        if cal.get('tasks'):
            lines.append(f"\n  Pending Tasks:")
            for t in cal['tasks'][:5]:
                due = f" (due: {t['due']})" if t['due'] != 'No due date' else ""
                lines.append(f"    [ ] {t['title']}{due}")
    
    # Recommendations
    recs = results.get('recommendations', [])
    if recs:
        lines.append(f"\n  RECOMMENDATIONS")
        lines.append(f"  {'-' * 50}")
        for i, rec in enumerate(recs, 1):
            cat = rec.get('category', 'General')
            action = rec.get('action', 'N/A')
            when = rec.get('when', '')
            source = rec.get('source', '')
            
            lines.append(f"\n  {i}. [{cat}]")
            # Wrap action text
            words = action.split()
            current_line = "     "
            for word in words:
                if len(current_line) + len(word) > 75:
                    lines.append(current_line)
                    current_line = "     " + word + " "
                else:
                    current_line += word + " "
            if current_line.strip():
                lines.append(current_line)
            
            if when:
                lines.append(f"     When: {when}")
            if source:
                # Truncate source name
                if len(source) > 60:
                    source = source[:57] + "..."
                lines.append(f"     Source: {source}")
    
    if results.get('errors'):
        lines.append(f"\n  Warnings: {', '.join(results['errors'])}")
    
    lines.append("\n" + "=" * 70)
    
    return "\n".join(lines)


def format_proposed_changes(changes: list) -> str:
    """Format proposed calendar changes."""
    if not changes:
        return "\n  No calendar changes to propose.\n"
    
    lines = []
    lines.append("\n" + "=" * 70)
    lines.append("  PROPOSED CALENDAR CHANGES")
    lines.append("=" * 70)
    
    for i, change in enumerate(changes, 1):
        title = change.get('title', 'Event')
        time = change.get('start_time', 'TBD')
        desc = change.get('description', '')
        reason = change.get('reason', '')
        
        lines.append(f"\n  {i}. {title}")
        lines.append(f"     Time: {time}")
        if desc:
            lines.append(f"     {desc}")
        if reason:
            lines.append(f"     Reason: {reason}")
    
    lines.append("\n" + "-" * 70)
    
    return "\n".join(lines)


def format_applied_changes(results: dict) -> str:
    """Format the results of applied changes."""
    lines = []
    lines.append("\n" + "=" * 70)
    lines.append("  CALENDAR UPDATED")
    lines.append("=" * 70)
    
    if results.get('applied'):
        lines.append("\n  Applied:")
        for change in results['applied']:
            lines.append(f"    [OK] {change.get('action', 'done')}: {change.get('title', change.get('event_id', 'event'))}")
    
    if results.get('failed'):
        lines.append("\n  Failed:")
        for change in results['failed']:
            lines.append(f"    [X] {change.get('title', 'Unknown')}")
    
    lines.append("\n" + "=" * 70)
    lines.append("  Check your Google Calendar to see the changes.")
    lines.append("=" * 70 + "\n")
    
    return "\n".join(lines)


def interactive_mode(agent: LLMSchedulerAgent, results: dict):
    """Run interactive optimization flow."""
    changes = results.get('proposed_changes', [])
    user_preferences = []  # Track preferences for this session
    
    if not changes:
        print("\n  No calendar optimizations to propose based on your current state.")
        return
    
    print(format_proposed_changes(changes))
    
    while True:
        print("\n  Would you like to optimize your schedule based on the above?")
        choice = input("  Enter [y]es / [n]o / [c]omments: ").strip().lower()
        
        if choice in ['n', 'no']:
            print("\n  No changes made.\n")
            return
        
        elif choice in ['c', 'comments']:
            print("\n  Share your thoughts or preferences:")
            raw_comments = input("  > ").strip()
            
            if raw_comments:
                # Parse feedback with LLM
                print("\n  Analyzing feedback...")
                parsed = agent.llm_client.parse_user_feedback(raw_comments)
                
                if parsed.get('should_save', True):
                    preference = parsed.get('preference', raw_comments)
                    user_preferences.append(preference)
                    
                    # Save to memory
                    agent.memory.storage.save('user_feedback', f'cli_{datetime.now().strftime("%Y%m%d_%H%M%S")}', {
                        'preference': preference,
                        'dislikes': parsed.get('dislikes', []),
                        'prefers': parsed.get('prefers', []),
                        'timestamp': results.get('timestamp', '')
                    })
                    print(f"\n  Saved to memory: \"{preference}\"")
                    
                    # Regenerate proposals with user preferences
                    print("\n  Regenerating proposals based on your preferences...")
                    changes = agent.llm_client.generate_calendar_changes(
                        results.get('recommendations', []),
                        results.get('calendar_summary', {}),
                        results.get('mental_health', {}),
                        user_preferences=user_preferences
                    )
                    
                    # Show updated proposals
                    print(format_proposed_changes(changes))
                else:
                    print("\n  Noted. Proceeding with current proposals.")
            
            continue
        
        elif choice in ['y', 'yes']:
            print("\n" + "-" * 70)
            print("  CONFIRM CHANGES")
            print("-" * 70)
            print("\n  The following will be added to your calendar:\n")
            
            for i, change in enumerate(changes, 1):
                print(f"    {i}. {change.get('title', 'Event')} at {change.get('start_time', 'TBD')}")
            
            confirm = input("\n  Confirm and apply? [y/n]: ").strip().lower()
            
            if confirm in ['y', 'yes']:
                print("\n  Applying changes...")
                apply_results = agent.apply_calendar_changes(changes)
                print(format_applied_changes(apply_results))
                return
            else:
                print("\n  Cancelled. No changes made.\n")
                return
        else:
            print("\n  Invalid option. Please try again.\n")


def main():
    parser = argparse.ArgumentParser(description="LLM Scheduler Agent")
    parser.add_argument('--quick', action='store_true', help='Quick mode (no interactive)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--no-calendar', action='store_true', help='Skip calendar')
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("  LLM SCHEDULER AGENT")
    print("=" * 70)
    
    agent = LLMSchedulerAgent()
    mode = "quick" if args.quick else "daily"
    
    print("\n  Analyzing journals and schedule...\n")
    results = agent.run(mode=mode)
    
    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return
    
    print(format_analysis(results))
    print(f"  Duration: {results.get('duration_seconds', 0):.1f}s\n")
    
    if not args.quick and not args.no_calendar and results.get('status') == 'completed':
        interactive_mode(agent, results)


if __name__ == "__main__":
    main()
