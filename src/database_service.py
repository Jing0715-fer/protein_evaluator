"""
Database service for protein evaluation operations.
Wraps database operations with proper error handling and logging.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.database import (
    create_protein_evaluation as _create_protein_evaluation,
    get_protein_evaluation as _get_protein_evaluation,
    get_protein_evaluation_by_uniprot as _get_protein_evaluation_by_uniprot,
    get_all_protein_evaluations as _get_all_protein_evaluations,
    update_protein_evaluation as _update_protein_evaluation,
    delete_protein_evaluation as _delete_protein_evaluation,
    search_protein_evaluations as _search_protein_evaluations,
    create_batch_evaluation as _create_batch_evaluation,
    get_batch_evaluation as _get_batch_evaluation,
    get_all_batch_evaluations as _get_all_batch_evaluations,
    update_batch_evaluation as _update_batch_evaluation,
    delete_batch_evaluation as _delete_batch_evaluation,
    create_protein_interaction as _create_protein_interaction,
    get_protein_interactions as _get_protein_interactions,
    delete_protein_interactions as _delete_protein_interactions,
    ProteinEvaluation,
    BatchEvaluation,
    ProteinInteraction,
)

from utils.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service class for database operations with error handling."""

    # ========== Protein Evaluation CRUD ==========

    @staticmethod
    def create_protein_evaluation(
        uniprot_id: str,
        gene_name: str = None,
        protein_name: str = None
    ) -> Optional[ProteinEvaluation]:
        """
        Create a new protein evaluation record.

        Args:
            uniprot_id: UniProt ID
            gene_name: Gene name (optional)
            protein_name: Protein name (optional)

        Returns:
            Created ProteinEvaluation or None on failure

        Raises:
            DatabaseError: On database operation failure
        """
        try:
            result = _create_protein_evaluation(uniprot_id, gene_name, protein_name)
            if result:
                logger.info(f"Created protein evaluation: ID={result.id}, UniProt={uniprot_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to create protein evaluation: {e}")
            raise DatabaseError(f"Failed to create protein evaluation: {e}")

    @staticmethod
    def get_protein_evaluation(evaluation_id: int) -> Optional[ProteinEvaluation]:
        """
        Get a protein evaluation by ID.

        Args:
            evaluation_id: Evaluation ID

        Returns:
            ProteinEvaluation or None if not found
        """
        try:
            return _get_protein_evaluation(evaluation_id)
        except Exception as e:
            logger.error(f"Failed to get protein evaluation {evaluation_id}: {e}")
            return None

    @staticmethod
    def get_protein_evaluation_by_uniprot(uniprot_id: str) -> Optional[ProteinEvaluation]:
        """
        Get a protein evaluation by UniProt ID.

        Args:
            uniprot_id: UniProt ID

        Returns:
            Most recent ProteinEvaluation or None
        """
        try:
            return _get_protein_evaluation_by_uniprot(uniprot_id)
        except Exception as e:
            logger.error(f"Failed to get protein evaluation by UniProt {uniprot_id}: {e}")
            return None

    @staticmethod
    def get_all_protein_evaluations(
        limit: int = 50,
        offset: int = 0
    ) -> List[ProteinEvaluation]:
        """
        Get all protein evaluations with pagination.

        Args:
            limit: Maximum number of records
            offset: Offset for pagination

        Returns:
            List of ProteinEvaluation objects
        """
        try:
            return _get_all_protein_evaluations(limit, offset)
        except Exception as e:
            logger.error(f"Failed to get protein evaluations: {e}")
            return []

    @staticmethod
    def update_protein_evaluation(
        evaluation_id: int,
        data: Dict[str, Any]
    ) -> bool:
        """
        Update a protein evaluation record.

        Args:
            evaluation_id: Evaluation ID
            data: Dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        try:
            return _update_protein_evaluation(evaluation_id, data)
        except Exception as e:
            logger.error(f"Failed to update protein evaluation {evaluation_id}: {e}")
            return False

    @staticmethod
    def delete_protein_evaluation(evaluation_id: int) -> bool:
        """
        Delete a protein evaluation.

        Args:
            evaluation_id: Evaluation ID

        Returns:
            True if successful, False otherwise
        """
        try:
            return _delete_protein_evaluation(evaluation_id)
        except Exception as e:
            logger.error(f"Failed to delete protein evaluation {evaluation_id}: {e}")
            return False

    @staticmethod
    def search_protein_evaluations(query: str) -> List[ProteinEvaluation]:
        """
        Search protein evaluations.

        Args:
            query: Search query string

        Returns:
            List of matching ProteinEvaluation objects
        """
        try:
            return _search_protein_evaluations(query)
        except Exception as e:
            logger.error(f"Failed to search protein evaluations: {e}")
            return []

    # ========== Batch Evaluation CRUD ==========

    @staticmethod
    def create_batch_evaluation(
        name: str,
        uniprot_ids: List[str],
        config: Dict[str, Any] = None
    ) -> Optional[BatchEvaluation]:
        """
        Create a batch evaluation record.

        Args:
            name: Batch name
            uniprot_ids: List of UniProt IDs
            config: Configuration dictionary

        Returns:
            Created BatchEvaluation or None on failure
        """
        try:
            result = _create_batch_evaluation(name, uniprot_ids, config)
            if result:
                logger.info(f"Created batch evaluation: ID={result.id}, name={name}")
            return result
        except Exception as e:
            logger.error(f"Failed to create batch evaluation: {e}")
            raise DatabaseError(f"Failed to create batch evaluation: {e}")

    @staticmethod
    def get_batch_evaluation(batch_id: int) -> Optional[BatchEvaluation]:
        """
        Get a batch evaluation by ID.

        Args:
            batch_id: Batch ID

        Returns:
            BatchEvaluation or None if not found
        """
        try:
            return _get_batch_evaluation(batch_id)
        except Exception as e:
            logger.error(f"Failed to get batch evaluation {batch_id}: {e}")
            return None

    @staticmethod
    def get_all_batch_evaluations(
        limit: int = 50,
        offset: int = 0
    ) -> List[BatchEvaluation]:
        """
        Get all batch evaluations with pagination.

        Args:
            limit: Maximum number of records
            offset: Offset for pagination

        Returns:
            List of BatchEvaluation objects
        """
        try:
            return _get_all_batch_evaluations(limit, offset)
        except Exception as e:
            logger.error(f"Failed to get batch evaluations: {e}")
            return []

    @staticmethod
    def update_batch_evaluation(
        batch_id: int,
        data: Dict[str, Any]
    ) -> bool:
        """
        Update a batch evaluation record.

        Args:
            batch_id: Batch ID
            data: Dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        try:
            return _update_batch_evaluation(batch_id, data)
        except Exception as e:
            logger.error(f"Failed to update batch evaluation {batch_id}: {e}")
            return False

    @staticmethod
    def delete_batch_evaluation(batch_id: int) -> bool:
        """
        Delete a batch evaluation.

        Args:
            batch_id: Batch ID

        Returns:
            True if successful, False otherwise
        """
        try:
            return _delete_batch_evaluation(batch_id)
        except Exception as e:
            logger.error(f"Failed to delete batch evaluation {batch_id}: {e}")
            return False

    # ========== Protein Interaction CRUD ==========

    @staticmethod
    def create_protein_interaction(
        uniprot_id_a: str,
        uniprot_id_b: str,
        interaction_type: str = None,
        score: float = None,
        source: str = None
    ) -> Optional[ProteinInteraction]:
        """
        Create a protein interaction record.

        Args:
            uniprot_id_a: First UniProt ID
            uniprot_id_b: Second UniProt ID
            interaction_type: Type of interaction
            score: Interaction score
            source: Data source

        Returns:
            Created ProteinInteraction or None on failure
        """
        try:
            return _create_protein_interaction(
                uniprot_id_a, uniprot_id_b, interaction_type, score, source
            )
        except Exception as e:
            logger.error(f"Failed to create protein interaction: {e}")
            return None

    @staticmethod
    def get_protein_interactions(uniprot_id: str) -> List[ProteinInteraction]:
        """
        Get interactions for a protein.

        Args:
            uniprot_id: UniProt ID

        Returns:
            List of ProteinInteraction objects
        """
        try:
            return _get_protein_interactions(uniprot_id)
        except Exception as e:
            logger.error(f"Failed to get protein interactions for {uniprot_id}: {e}")
            return []

    @staticmethod
    def delete_protein_interactions(uniprot_id: str) -> bool:
        """
        Delete all interactions for a protein.

        Args:
            uniprot_id: UniProt ID

        Returns:
            True if successful, False otherwise
        """
        try:
            return _delete_protein_interactions(uniprot_id)
        except Exception as e:
            logger.error(f"Failed to delete protein interactions for {uniprot_id}: {e}")
            return False

    # ========== Evaluation Logging ==========

    @staticmethod
    def add_log(evaluation_id: int, message: str, level: str = 'info') -> bool:
        """
        Add a log entry to an evaluation.

        Args:
            evaluation_id: Evaluation ID
            message: Log message
            level: Log level (info, warning, error)

        Returns:
            True if successful, False otherwise
        """
        try:
            evaluation = _get_protein_evaluation(evaluation_id)
            if evaluation:
                logs = evaluation.logs or []
                logs.append({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'level': level,
                    'message': message
                })
                return _update_protein_evaluation(evaluation_id, {'logs': logs})
            return False
        except Exception as e:
            logger.warning(f"Failed to add log to evaluation {evaluation_id}: {e}")
            return False

    @staticmethod
    def add_batch_log(batch_id: int, message: str, level: str = 'info') -> bool:
        """
        Add a log entry to a batch evaluation.

        Args:
            batch_id: Batch ID
            message: Log message
            level: Log level (info, warning, error)

        Returns:
            True if successful, False otherwise
        """
        try:
            batch = _get_batch_evaluation(batch_id)
            if batch:
                logs = batch.logs or []
                logs.append({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'level': level,
                    'message': message
                })
                return _update_batch_evaluation(batch_id, {'logs': logs})
            return False
        except Exception as e:
            logger.warning(f"Failed to add log to batch {batch_id}: {e}")
            return False


# Module-level functions for backward compatibility

def create_protein_evaluation(
    uniprot_id: str,
    gene_name: str = None,
    protein_name: str = None
) -> Optional[ProteinEvaluation]:
    """Create a new protein evaluation record."""
    return DatabaseService.create_protein_evaluation(uniprot_id, gene_name, protein_name)


def get_protein_evaluation(evaluation_id: int) -> Optional[ProteinEvaluation]:
    """Get a protein evaluation by ID."""
    return DatabaseService.get_protein_evaluation(evaluation_id)


def get_protein_evaluation_by_uniprot(uniprot_id: str) -> Optional[ProteinEvaluation]:
    """Get a protein evaluation by UniProt ID."""
    return DatabaseService.get_protein_evaluation_by_uniprot(uniprot_id)


def get_all_protein_evaluations(limit: int = 50, offset: int = 0) -> List[ProteinEvaluation]:
    """Get all protein evaluations."""
    return DatabaseService.get_all_protein_evaluations(limit, offset)


def update_protein_evaluation(evaluation_id: int, data: Dict[str, Any]) -> bool:
    """Update a protein evaluation."""
    return DatabaseService.update_protein_evaluation(evaluation_id, data)


def delete_protein_evaluation(evaluation_id: int) -> bool:
    """Delete a protein evaluation."""
    return DatabaseService.delete_protein_evaluation(evaluation_id)


def search_protein_evaluations(query: str) -> List[ProteinEvaluation]:
    """Search protein evaluations."""
    return DatabaseService.search_protein_evaluations(query)


def create_batch_evaluation(
    name: str,
    uniprot_ids: List[str],
    config: Dict[str, Any] = None
) -> Optional[BatchEvaluation]:
    """Create a batch evaluation."""
    return DatabaseService.create_batch_evaluation(name, uniprot_ids, config)


def get_batch_evaluation(batch_id: int) -> Optional[BatchEvaluation]:
    """Get a batch evaluation by ID."""
    return DatabaseService.get_batch_evaluation(batch_id)


def get_all_batch_evaluations(limit: int = 50, offset: int = 0) -> List[BatchEvaluation]:
    """Get all batch evaluations."""
    return DatabaseService.get_all_batch_evaluations(limit, offset)


def update_batch_evaluation(batch_id: int, data: Dict[str, Any]) -> bool:
    """Update a batch evaluation."""
    return DatabaseService.update_batch_evaluation(batch_id, data)


def delete_batch_evaluation(batch_id: int) -> bool:
    """Delete a batch evaluation."""
    return DatabaseService.delete_batch_evaluation(batch_id)


def create_protein_interaction(
    uniprot_id_a: str,
    uniprot_id_b: str,
    interaction_type: str = None,
    score: float = None,
    source: str = None
) -> Optional[ProteinInteraction]:
    """Create a protein interaction."""
    return DatabaseService.create_protein_interaction(
        uniprot_id_a, uniprot_id_b, interaction_type, score, source
    )


def get_protein_interactions(uniprot_id: str) -> List[ProteinInteraction]:
    """Get interactions for a protein."""
    return DatabaseService.get_protein_interactions(uniprot_id)


def delete_protein_interactions(uniprot_id: str) -> bool:
    """Delete all interactions for a protein."""
    return DatabaseService.delete_protein_interactions(uniprot_id)


def add_log(evaluation_id: int, message: str, level: str = 'info') -> bool:
    """Add a log entry to an evaluation."""
    return DatabaseService.add_log(evaluation_id, message, level)


def add_batch_log(batch_id: int, message: str, level: str = 'info') -> bool:
    """Add a log entry to a batch evaluation."""
    return DatabaseService.add_batch_log(batch_id, message, level)
