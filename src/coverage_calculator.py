"""
PDB sequence coverage calculator.
Calculates sequence coverage from PDB structures.
"""

import logging
from typing import Dict, List, Any, Set, Tuple

import requests
from utils.api_utils import http_session, retry_with_backoff

logger = logging.getLogger(__name__)


class CoverageCalculator:
    """Calculator for PDB sequence coverage."""

    def __init__(self):
        self.session = http_session

    def calculate_coverage(
        self,
        pdb_data: Dict,
        protein_length: int,
        target_uniprot_id: str = None
    ) -> Dict[str, Any]:
        """
        Calculate sequence coverage from PDB structures.

        Args:
            pdb_data: PDB data with structures
            protein_length: Total protein sequence length
            target_uniprot_id: Target UniProt ID for mapping

        Returns:
            Coverage information dictionary
        """
        if not pdb_data or not protein_length:
            return {
                'coverage_percent': 0.0,
                'covered_residues': 0,
                'total_residues': protein_length,
                'structure_coverages': []
            }

        covered_regions: Set[int] = set()
        structure_coverages = []

        # Get PDB to UniProt mapping
        pdb_ids = [s.get('pdb_id', '') for s in pdb_data.get('structures', [])]
        mapping = self._fetch_pdb_uniprot_mapping(pdb_ids) if pdb_ids else {}

        for struct in pdb_data.get('structures', []):
            pdb_id = struct.get('pdb_id', '')
            struct_coverage = {
                'pdb_id': pdb_id,
                'chains': [],
                'covered_residues': 0
            }

            # Get mapping for this PDB
            pdb_mapping = mapping.get(pdb_id, {})
            uniprot_mappings = pdb_mapping.get('uniprot_mappings', [])

            # Filter mappings for target UniProt ID
            if target_uniprot_id and uniprot_mappings:
                target_mappings = [
                    m for m in uniprot_mappings
                    if m.get('uniprot_id', '').upper() == target_uniprot_id.upper()
                ]
            else:
                target_mappings = uniprot_mappings

            # If no specific mapping found, assume full coverage
            if not target_mappings:
                # Add all residues as covered
                for i in range(1, protein_length + 1):
                    covered_regions.add(i)
                struct_coverage['covered_residues'] = protein_length
            else:
                # Add covered residues from mappings
                for mapping_entry in target_mappings:
                    start = mapping_entry.get('start', 1)
                    end = mapping_entry.get('end', protein_length)

                    for i in range(start, end + 1):
                        if 1 <= i <= protein_length:
                            covered_regions.add(i)

                    struct_coverage['chains'].append({
                        'chain_id': mapping_entry.get('chain_id', ''),
                        'uniprot_id': mapping_entry.get('uniprot_id', ''),
                        'start': start,
                        'end': end
                    })

                struct_coverage['covered_residues'] = len([
                    i for i in covered_regions
                    if any(
                        m.get('start', 1) <= i <= m.get('end', protein_length)
                        for m in target_mappings
                    )
                ])

            structure_coverages.append(struct_coverage)

        coverage_count = len(covered_regions)
        coverage_percent = (coverage_count / protein_length * 100) if protein_length > 0 else 0

        return {
            'coverage_percent': round(coverage_percent, 2),
            'covered_residues': coverage_count,
            'total_residues': protein_length,
            'structure_coverages': structure_coverages
        }

    @retry_with_backoff(max_retries=2, initial_delay=1.0)
    def _fetch_pdb_uniprot_mapping(self, pdb_ids: List[str]) -> Dict[str, Dict]:
        """
        Fetch PDB to UniProt residue mapping.

        Args:
            pdb_ids: List of PDB IDs

        Returns:
            Dictionary mapping PDB IDs to their UniProt mappings
        """
        if not pdb_ids:
            return {}

        result = {}

        # Process in batches
        batch_size = 100
        for i in range(0, len(pdb_ids), batch_size):
            batch = pdb_ids[i:i + batch_size]

            try:
                # Use RCSB mapping API
                url = "https://data.rcsb.org/rest/v1/core/entry/"

                for pdb_id in batch:
                    try:
                        # Get polymer entity info
                        entity_url = f"{url}{pdb_id}"
                        response = self.session.get(entity_url, timeout=30)

                        if response.status_code == 200:
                            data = response.json()
                            mappings = self._extract_mappings(data, pdb_id)
                            result[pdb_id] = mappings

                    except Exception as e:
                        logger.warning(f"Failed to get mapping for {pdb_id}: {e}")
                        result[pdb_id] = {'uniprot_mappings': []}

            except Exception as e:
                logger.error(f"Failed to fetch PDB-UniProt mapping: {e}")

        return result

    def _extract_mappings(self, data: Dict, pdb_id: str) -> Dict:
        """Extract UniProt mappings from PDB data."""
        mappings = []

        try:
            # Try to get polymer entity data
            entities = data.get('rcsb_polymer_entity_container_identifiers', {})
            if entities:
                auth_asym_ids = entities.get('auth_asym_ids', [])

                for chain_id in auth_asym_ids:
                    mappings.append({
                        'chain_id': chain_id,
                        'uniprot_id': '',
                        'start': 1,
                        'end': 0
                    })

            # Try to get reference sequence info
            ref_sequences = data.get('entity_src_gen', [])
            for ref in ref_sequences:
                if isinstance(ref, dict):
                    pdbx_db_accession = ref.get('pdbx_db_accession', '')
                    if pdbx_db_accession:
                        # Update mapping with UniProt ID
                        for m in mappings:
                            if not m['uniprot_id']:
                                m['uniprot_id'] = pdbx_db_accession

        except Exception as e:
            logger.warning(f"Failed to extract mappings for {pdb_id}: {e}")

        return {'uniprot_mappings': mappings}


def calculate_pdb_coverage(
    pdb_data: Dict,
    protein_length: int,
    target_uniprot_id: str = None
) -> Dict[str, Any]:
    """
    Convenience function to calculate PDB sequence coverage.

    Args:
        pdb_data: PDB data with structures
        protein_length: Total protein sequence length
        target_uniprot_id: Target UniProt ID

    Returns:
        Coverage information dictionary
    """
    calculator = CoverageCalculator()
    return calculator.calculate_coverage(pdb_data, protein_length, target_uniprot_id)
