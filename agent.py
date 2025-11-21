"""
The core Agent logic - The "Conductor"
Orchestrates the workflow between AutoLife data, I-HOPE model, vector DB, and calendar.
"""

import logging
from typing import Dict, Any, List

from tools.autolife_reader import AutoLifeReader
from tools.ihope_model import IHopeModel
from tools.vectordb_client import VectorDBClient
from tools.calendar_api import CalendarAPI

logger = logging.getLogger(__name__)


class Agent:
    """
    The Conductor Agent that orchestrates all tools and workflows.
    
    Workflow:
    1. Read AutoLife journals (tool 1)
    2. Run I-HOPE PHQ-4 prediction (tool 2)
    3. Fetch Top K concepts from vector DB (tool 3)
    4. Integrate with calendar for scheduling (tool 4)
    """
    
    def __init__(self):
        """Initialize the agent with all required tools."""
        logger.info("Initializing Agent (Conductor)")
        
        self.autolife_reader = AutoLifeReader()
        self.ihope_model = IHopeModel()
        self.vectordb_client = VectorDBClient()
        self.calendar_api = CalendarAPI()
        
        logger.info("Agent initialization complete")
    
    def run(self):
        """
        Main execution loop for the agent.
        Orchestrates the workflow between all tools.
        """
        logger.info("Starting agent workflow")
        
        # Step 1: Read AutoLife journals
        logger.info("Step 1: Reading AutoLife journals")
        journals = self.autolife_reader.read_journals()
        
        if not journals:
            logger.warning("No journals found. Skipping workflow.")
            return
        
        # Step 2: Run I-HOPE prediction
        logger.info("Step 2: Running I-HOPE PHQ-4 prediction")
        predictions = self.ihope_model.predict(journals)
        
        # Step 3: Fetch relevant concepts from vector DB
        logger.info("Step 3: Fetching Top K concepts from vector DB")
        concepts = self.vectordb_client.fetch_top_k_concepts(journals, k=5)
        
        # Step 4: Calendar integration
        logger.info("Step 4: Integrating with calendar")
        self.calendar_api.schedule_interventions(predictions, concepts)
        
        logger.info("Agent workflow complete")
    
    def process_single_journal(self, journal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single journal entry through the complete workflow.
        
        Args:
            journal_data: Dictionary containing journal entry data
            
        Returns:
            Dictionary containing results from all processing steps
        """
        results = {}
        
        # Predict mental health state
        prediction = self.ihope_model.predict([journal_data])
        results['prediction'] = prediction
        
        # Fetch relevant concepts
        concepts = self.vectordb_client.fetch_top_k_concepts([journal_data], k=5)
        results['concepts'] = concepts
        
        # Schedule any necessary interventions
        calendar_events = self.calendar_api.schedule_interventions(prediction, concepts)
        results['calendar_events'] = calendar_events
        
        return results
