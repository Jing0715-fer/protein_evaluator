"""
Protein interaction service.
Handles fetching and processing protein-protein interactions.
"""

import logging
from typing import Dict, List, Any, Optional

import requests
from utils.api_utils import http_session, retry_with_backoff

logger = logging.getLogger(__name__)


class InteractionService:
    """Service for protein interaction data."""

    def __init__(self):
        self.session = http_session

    def fetch_interactions(self, uniprot_ids: List[str]) -> Dict[str, Any]:
        """
        Fetch protein interactions for given UniProt IDs.

        Args:
            uniprot_ids: List of UniProt IDs

        Returns:
            Interaction data dictionary
        """
        interactions = []

        try:
            # Try STRING database API
            string_interactions = self._fetch_string_interactions(uniprot_ids)
            if string_interactions:
                interactions.extend(string_interactions)

        except Exception as e:
            logger.warning(f"STRING interaction fetch failed: {e}")

        # If no interactions found, return empty but valid result
        if not interactions:
            logger.info("No interaction data found, will rely on AI analysis")

        return {
            'interactions': interactions,
            'source': 'string_db' if interactions else 'none',
            'protein_count': len(uniprot_ids)
        }

    def _fetch_string_interactions(self, uniprot_ids: List[str]) -> List[Dict]:
        """Fetch interactions from STRING database."""
        interactions = []

        # STRING API requires species ID (e.g., 9606 for human)
        # For now, we'll skip actual API calls and return empty
        # In a full implementation, this would query the STRING API

        logger.debug(f"STRING interaction lookup skipped for {len(uniprot_ids)} proteins")

        return interactions

    def predict_interactions_from_ai(
        self,
        uniprot_ids: List[str],
        protein_data: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """
        Predict interactions based on protein data using AI.

        Args:
            uniprot_ids: List of UniProt IDs
            protein_data: Dictionary of protein data by UniProt ID

        Returns:
            Predicted interaction data
        """
        # This is a placeholder for AI-based interaction prediction
        # In a full implementation, this would use an AI model to predict
        # interactions based on protein features

        return {
            'interactions': [],
            'source': 'ai_prediction',
            'protein_count': len(uniprot_ids)
        }


def fetch_protein_interactions(uniprot_ids: List[str]) -> Dict[str, Any]:
    """
    Convenience function to fetch protein interactions.

    Args:
        uniprot_ids: List of UniProt IDs

    Returns:
        Interaction data
    """
    service = InteractionService()
    return service.fetch_interactions(uniprot_ids)
