"""
Chain-level protein interaction analysis module.
Analyzes direct physical interactions between proteins based on PDB structure interfaces.
"""

import logging
import threading
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from sqlalchemy.orm import joinedload

from src.database import get_session
from src.multi_target_models import MultiTargetJob, Target

logger = logging.getLogger(__name__)

PDBE_API_BASE = "https://www.ebi.ac.uk/pdbe/api"
UNIPROT_API_BASE = "https://rest.uniprot.org/uniprotkb"
API_TIMEOUT = 10

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2  # seconds
RETRY_BACKOFF_FACTOR = 2
RATE_LIMIT_DELAY = 10  # seconds to wait on 429 rate limit

# Parallel processing configuration
MAX_WORKERS = 4  # Number of concurrent PDB requests (reduced to avoid rate limiting)


def _make_request_with_retry(url: str, timeout: int = API_TIMEOUT) -> Optional[requests.Response]:
    """Make HTTP request with exponential backoff retry.

    Args:
        url: The URL to request
        timeout: Request timeout in seconds

    Returns:
        Response object or None if all retries fail
    """
    import time
    delay = INITIAL_RETRY_DELAY
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return response
            # Handle rate limiting specifically with longer delay
            if response.status_code == 429:
                wait_time = RATE_LIMIT_DELAY
                logger.warning(f"Rate limited (429) for {url}. Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                last_error = "HTTP 429 Rate Limited"
                continue
            # Retry on non-success status codes (except 404 which means not found)
            if response.status_code == 404:
                return response
            last_error = f"HTTP {response.status_code}"
        except requests.exceptions.Timeout:
            last_error = "Request timeout"
        except requests.exceptions.RequestException as e:
            last_error = str(e)

        if attempt < MAX_RETRIES - 1:
            logger.warning(f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {last_error}. Retrying in {delay}s...")
            time.sleep(delay)
            delay *= RETRY_BACKOFF_FACTOR

    logger.warning(f"Request to {url} failed after {MAX_RETRIES} attempts: {last_error}")
    return None


@dataclass
class ChainInfo:
    """Information about a protein chain."""
    pdb_id: str
    chain_id: str
    entity_id: str
    uniprot_id: Optional[str] = None
    gene_name: Optional[str] = None
    protein_name: Optional[str] = None
    polymer_type: str = "Polypeptide"
    sequence: str = ""
    length: int = 0
    organism: str = ""


class ChainInteractionAnalyzer:
    """Analyzes chain-level interactions from PDB structures using PDBe interfaces API."""

    def __init__(self):
        self.interface_cache: Dict[str, Dict[str, List[str]]] = {}
        self.uniprot_gene_cache: Dict[str, List[str]] = {}
        self._cache_lock = threading.Lock()  # Lock for thread-safe cache access

    def _get_uniprot_gene_names(self, uniprot_id: str) -> List[str]:
        """Get gene names for a UniProt ID from UniProt API."""
        if uniprot_id in self.uniprot_gene_cache:
            return self.uniprot_gene_cache[uniprot_id]

        try:
            url = f"{UNIPROT_API_BASE}/{uniprot_id}.json"
            response = requests.get(url, timeout=API_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                genes = []
                for gene in data.get('genes', []):
                    gene_name = gene.get('geneName', {}).get('value')
                    if gene_name:
                        genes.append(gene_name)
                    # Also add synonyms
                    for syn in gene.get('synonyms', []):
                        syn_name = syn.get('value')
                        if syn_name:
                            genes.append(syn_name)
                    # Add ORF names (e.g., AD-006 for CRBN)
                    for orf in gene.get('orfNames', []):
                        orf_name = orf.get('value')
                        if orf_name:
                            genes.append(orf_name)
                self.uniprot_gene_cache[uniprot_id] = genes
                return genes
        except Exception as e:
            logger.warning(f"Failed to get gene names for {uniprot_id}: {e}")

        self.uniprot_gene_cache[uniprot_id] = []
        return []

    def _match_uniprot_by_gene(self, entity_gene: str, input_uniprot_ids: List[str]) -> Optional[str]:
        """Match a gene name from PDB to an input UniProt ID.

        Tries multiple strategies:
        1. Exact match with canonical gene names
        2. Match with gene name synonyms (from cached UniProt data)
        3. UniProt search API fallback for unknown synonyms
        """
        if not entity_gene:
            return None

        entity_gene_lower = entity_gene.lower()
        input_set = set(input_uniprot_ids)

        for uniprot_id in input_uniprot_ids:
            gene_names = self._get_uniprot_gene_names(uniprot_id)
            for gene in gene_names:
                if gene.lower() == entity_gene_lower:
                    return uniprot_id

        # Fallback: Search UniProt API for the gene name
        matched = self._search_uniprot_by_gene(entity_gene, input_set)
        if matched:
            return matched

        return None

    def _search_uniprot_by_gene(self, gene_name: str, input_uniprot_ids: Set[str]) -> Optional[str]:
        """Search UniProt for a gene name and check if result matches input IDs.

        This handles cases where PDB uses gene names not in UniProt synonyms
        (e.g., AD-006 for CRBN/Q96SW2).
        """
        cache_key = f"search_{gene_name.lower()}"
        if cache_key in self.uniprot_gene_cache:
            result = self.uniprot_gene_cache[cache_key]
            if result in input_uniprot_ids:
                return result
            return None

        try:
            # Search UniProt by gene name
            search_url = f"{UNIPROT_API_BASE}/search"
            params = {
                'query': f'gene:{gene_name}',
                'format': 'json',
                'fields': ['accession', 'gene_name'],
                'size': 10
            }
            response = requests.get(search_url, params=params, timeout=API_TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])

                for entry in results:
                    accession = entry.get('accession', '')
                    if accession in input_uniprot_ids:
                        # Cache the mapping
                        self.uniprot_gene_cache[cache_key] = accession
                        logger.info(f"Gene search: '{gene_name}' matched to {accession}")
                        return accession

                # Cache negative result
                self.uniprot_gene_cache[cache_key] = None

        except Exception as e:
            logger.warning(f"UniProt gene search failed for '{gene_name}': {e}")
            self.uniprot_gene_cache[cache_key] = None

        return None

    def _get_interfaces_for_pdb(
        self,
        pdb_id: str,
        input_uniprot_ids: List[str] = None
    ) -> Optional[Dict[str, List[str]]]:
        """
        Get interface information for a PDB entry.

        Args:
            pdb_id: The PDB ID
            input_uniprot_ids: List of input UniProt IDs for gene matching

        Returns: Dict[source_uniprot, list of partner UniProt IDs] or None if API fails.
        """
        cache_key = f"{pdb_id}_interfaces"

        # Thread-safe cache check
        with self._cache_lock:
            if cache_key in self.interface_cache:
                return self.interface_cache[cache_key]

        interfaces: Dict[str, List[str]] = defaultdict(list)

        try:
            # Get all molecules - WITH RETRY
            molecules_url = f"{PDBE_API_BASE}/pdb/entry/molecules/{pdb_id.lower()}"
            response = _make_request_with_retry(molecules_url)

            if response is None or response.status_code != 200:
                with self._cache_lock:
                    self.interface_cache[cache_key] = None
                return None

            molecules_data = response.json()
            pdb_lower = pdb_id.lower()

            if pdb_lower not in molecules_data:
                with self._cache_lock:
                    self.interface_cache[cache_key] = None
                return None

            molecules = molecules_data[pdb_lower]

            # Build entity -> gene mapping and filter to only protein entities (Polypeptide)
            # Skip non-protein entities like ligands, water, ions to reduce API calls
            entity_to_gene: Dict[str, str] = {}
            protein_entities: Set[str] = set()  # Only process protein entities

            for mol in molecules:
                entity_id = str(mol.get('entity_id', ''))
                if not entity_id:
                    continue

                # Filter: only process protein entities (Polypeptide)
                # Skip bound molecules, ligands, water, ions, etc.
                # Note: API returns 'molecule_type' field (e.g., "polypeptide(L)" or "bound")
                molecule_type = mol.get('molecule_type', '')
                if 'polypeptide' not in molecule_type.lower():
                    logger.debug(f"PDB {pdb_id}: skipping non-protein entity {entity_id} ({molecule_type})")
                    continue

                protein_entities.add(entity_id)

                genes = mol.get('gene_name', [])
                if genes:
                    entity_to_gene[entity_id] = genes[0]

            # If no protein entities found, skip this PDB entirely
            if not protein_entities:
                logger.debug(f"PDB {pdb_id}: no protein entities found, skipping")
                with self._cache_lock:
                    self.interface_cache[cache_key] = None
                return None

            logger.info(f"PDB {pdb_id}: processing {len(protein_entities)} protein entities out of {len(molecules)} total entities")

            # Get interface data for ONLY protein entities (skip bound molecules)
            for entity_id in protein_entities:

                interface_url = f"{PDBE_API_BASE}/pdb/entry/interfaces/{pdb_id.lower()}/{entity_id}"

                try:
                    iface_response = _make_request_with_retry(interface_url)

                    if iface_response and iface_response.status_code == 200:
                        iface_data = iface_response.json()
                        pdb_key = pdb_id.lower()

                        if pdb_key in iface_data:
                            iface_root = iface_data[pdb_key]
                            data_list = iface_root.get('data', [])
                            iface_sequence = iface_root.get('sequence', '')

                            # Get source UniProt ID by matching gene name
                            source_uniprot = None
                            entity_gene = entity_to_gene.get(entity_id, '')

                            if entity_gene and input_uniprot_ids:
                                source_uniprot = self._match_uniprot_by_gene(entity_gene, input_uniprot_ids)

                            if not source_uniprot:
                                source_uniprot = entity_gene if entity_gene else entity_id

                            for item in data_list:
                                # The accession in interface data is the PARTNER's UniProt
                                interacting_uniprot = item.get('accession')
                                if interacting_uniprot and interacting_uniprot != source_uniprot:
                                    interfaces[source_uniprot].append(interacting_uniprot)

                except Exception as e:
                    pass  # Skip failed entity interfaces

            # Return the interfaces dict keyed by source UniProt
            # Return empty dict {} for PDBs with no interfaces (not a failure)
            # Return None only for actual API errors
            result = dict(interfaces) if interfaces or len(interfaces) > 0 else {}
            with self._cache_lock:
                self.interface_cache[cache_key] = result
            return result

        except Exception as e:
            logger.warning(f"Failed to get interface data for {pdb_id}: {e}")
            with self._cache_lock:
                self.interface_cache[cache_key] = None
            return None

    def analyze_job_interactions(
        self,
        job_id: int,
        input_uniprot_ids: List[str],
        progress_callback=None
    ) -> Dict[str, Any]:
        """Analyze all interactions for a job.

        Args:
            job_id: The job ID
            input_uniprot_ids: List of UniProt IDs to analyze
            progress_callback: Optional callback(current_pdb, total_pdbs, current_idx) for progress updates
        """
        logger.info(f"Analyzing chain interactions for job {job_id}")

        # Deduplicate input UniProt IDs to avoid duplicate interactions
        input_uniprot_ids = list(dict.fromkeys(input_uniprot_ids))
        logger.info(f"Deduplicated input IDs: {input_uniprot_ids}")

        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return self._empty_result()

            # Use joinedload to eager load evaluation relationship
            targets = session.query(Target).options(joinedload(Target.evaluation)).filter_by(job_id=job_id).all()

            # Collect chains and PDB structures from evaluations
            all_chains: Dict[str, Dict[str, ChainInfo]] = defaultdict(dict)
            pdb_structures: Dict[str, Dict] = {}

            logger.info(f"Chain analysis: found {len(targets)} targets for job {job_id}")

            for target in targets:
                if not target.evaluation:
                    logger.warning(f"Target {target.uniprot_id} has no evaluation")
                    continue
                if not target.evaluation.pdb_data:
                    logger.warning(f"Target {target.uniprot_id} evaluation has no pdb_data")
                    continue

                uniprot_id = target.uniprot_id
                structures = target.evaluation.pdb_data.get('structures', [])

                for struct in structures:  # Process all available PDBs
                    pdb_id = struct.get('pdb_id', '')
                    if not pdb_id:
                        continue

                    if pdb_id not in pdb_structures:
                        pdb_structures[pdb_id] = struct

                    entity_list = struct.get('entity_list', [])
                    for ent in entity_list:
                        chain_id = ent.get('chain', '')
                        entity_id = str(ent.get('entity_id', ''))
                        if not chain_id or not entity_id:
                            continue

                        chain_info = ChainInfo(
                            pdb_id=pdb_id,
                            chain_id=chain_id,
                            entity_id=entity_id,
                            uniprot_id=uniprot_id,
                            gene_name=ent.get('gene_name', ''),
                            protein_name=ent.get('molecule_name', ''),
                            polymer_type=ent.get('polymer_type', 'Polypeptide'),
                            sequence=ent.get('sequence', ''),
                            length=ent.get('length', 0),
                            organism=ent.get('organism', '')
                        )

                        all_chains[uniprot_id][pdb_id] = chain_info

            logger.info(f"Collected {len(pdb_structures)} PDB structures")

            # Get interface data from PDBe API with parallel processing
            input_set = set(input_uniprot_ids)
            direct_graph: Dict[str, Set[str]] = defaultdict(set)
            interaction_pdbs: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
            api_used = False
            failed_pdbs: Set[str] = set()
            pdb_list = list(pdb_structures.keys())
            total_pdbs = len(pdb_list)

            # Thread-safe lock for cache access
            cache_lock = threading.Lock()

            def process_single_pdb(pdb_id: str) -> Tuple[str, Optional[Dict[str, List[str]]], bool]:
                """Process a single PDB and return (pdb_id, interfaces, success)"""
                try:
                    interfaces = self._get_interfaces_for_pdb(pdb_id, input_uniprot_ids)
                    return (pdb_id, interfaces, interfaces is not None)
                except Exception as e:
                    logger.warning(f"Error processing PDB {pdb_id}: {e}")
                    return (pdb_id, None, False)

            # Process PDBs in parallel
            completed_count = [0]  # Use list for mutable closure
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # Submit all tasks
                future_to_pdb = {
                    executor.submit(process_single_pdb, pdb_id): pdb_id
                    for pdb_id in pdb_list
                }

                # Process results as they complete
                for future in as_completed(future_to_pdb):
                    pdb_id, interfaces, success = future.result()

                    # Call progress callback
                    completed_count[0] += 1
                    if progress_callback:
                        try:
                            progress_callback(pdb_id, total_pdbs, completed_count[0] - 1)
                        except Exception as e:
                            logger.warning(f"Progress callback error: {e}")

                    if not success:
                        failed_pdbs.add(pdb_id)
                        continue

                    if interfaces:
                        api_used = True

                    # Process interfaces in a thread-safe manner
                    with cache_lock:
                        for uniprot_id in input_uniprot_ids:
                            if uniprot_id not in interfaces:
                                continue

                            interacting = interfaces.get(uniprot_id, [])
                            for inter_uniprot in interacting:
                                if inter_uniprot in input_set and inter_uniprot != uniprot_id:
                                    direct_graph[uniprot_id].add(inter_uniprot)
                                    direct_graph[inter_uniprot].add(uniprot_id)
                                    pair = tuple(sorted([uniprot_id, inter_uniprot]))
                                    interaction_pdbs[pair].add(pdb_id)

            # Classify interactions
            direct_interactions = []
            indirect_interactions = []

            for i, uniprot_a in enumerate(input_uniprot_ids):
                for uniprot_b in input_uniprot_ids[i+1:]:
                    neighbors_a = direct_graph.get(uniprot_a, set())
                    pair = tuple(sorted([uniprot_a, uniprot_b]))
                    pdb_ids_for_pair = list(interaction_pdbs.get(pair, set()))

                    if uniprot_b in neighbors_a:
                        # Direct interaction
                        direct_interactions.append({
                            'source_uniprot': uniprot_a,
                            'target_uniprot': uniprot_b,
                            'interaction_type': 'direct',
                            'pdb_ids': pdb_ids_for_pair,
                            'score': 1.0,
                            'is_confirmed': True,
                            'mediator_uniprot': None
                        })
                    else:
                        # Check for indirect (mediated) interaction
                        mediator = None
                        for mediator_candidate in neighbors_a:
                            neighbors_c = direct_graph.get(mediator_candidate, set())
                            if uniprot_b in neighbors_c:
                                mediator = mediator_candidate
                                break

                        if mediator:
                            indirect_interactions.append({
                                'source_uniprot': uniprot_a,
                                'target_uniprot': uniprot_b,
                                'interaction_type': 'indirect',
                                'pdb_ids': pdb_ids_for_pair,
                                'score': 0.5,
                                'is_confirmed': False,
                                'mediator_uniprot': mediator
                            })

            # Build nodes
            nodes = []
            for uniprot_id in input_uniprot_ids:
                chains_data = all_chains.get(uniprot_id, {})
                chain = list(chains_data.values())[0] if chains_data else None

                nodes.append({
                    'id': uniprot_id,
                    'label': chain.gene_name if chain and chain.gene_name else uniprot_id,
                    'gene_name': chain.gene_name if chain else '',
                    'protein_name': chain.protein_name if chain else '',
                    'is_input': True,
                    'pdb_count': len(chains_data),
                    'organism': chain.organism if chain else '',
                    'connections': len(direct_graph.get(uniprot_id, set()))
                })

            result = {
                'nodes': nodes,
                'direct_interactions': direct_interactions,
                'indirect_interactions': indirect_interactions,
                'all_interactions': direct_interactions + indirect_interactions,
                'chain_interactions': [],
                'pdb_structures': list(pdb_structures.keys()),
                'interface_count': sum(len(v) for v in direct_graph.values()) // 2,
                'api_used': api_used,
                'failed_pdbs': list(failed_pdbs)
            }

            logger.info(f"Chain analysis: {len(nodes)} nodes, {len(direct_interactions)} direct, {len(indirect_interactions)} indirect")

            # Save to database
            self._save_to_job(job_id, result)

            return result

        finally:
            session.close()

    def _save_to_job(self, job_id: int, analysis_result: Dict[str, Any]):
        """Save chain interaction analysis to database job."""
        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if job:
                job.chain_interaction_analysis = analysis_result
                session.commit()
                logger.info(f"Saved chain interaction analysis to job {job_id}")
        except Exception as e:
            logger.warning(f"Failed to save chain interaction analysis to job {job_id}: {e}")
            session.rollback()
        finally:
            session.close()

    def _empty_result(self) -> Dict[str, Any]:
        return {
            'nodes': [],
            'direct_interactions': [],
            'indirect_interactions': [],
            'all_interactions': [],
            'chain_interactions': [],
            'pdb_structures': [],
            'interface_count': 0,
            'api_used': False,
            'failed_pdbs': []
        }

    def retry_failed_pdbs(
        self,
        job_id: int,
        input_uniprot_ids: List[str],
        failed_pdb_ids: List[str],
        progress_callback=None
    ) -> Dict[str, Any]:
        """Retry analysis for specific PDB IDs that previously failed.

        Args:
            job_id: The job ID
            input_uniprot_ids: List of input UniProt IDs
            failed_pdb_ids: List of PDB IDs to retry
            progress_callback: Optional callback for progress updates

        Returns:
            Updated analysis result with retry info
        """
        logger.info(f"Retrying {len(failed_pdb_ids)} failed PDBs for job {job_id}")

        # Clear cache for failed PDBs to force re-fetch
        for pdb_id in failed_pdb_ids:
            cache_key = f"{pdb_id}_interfaces"
            if cache_key in self.interface_cache:
                del self.interface_cache[cache_key]

        # Re-run analysis with cleared cache
        return self.analyze_job_interactions(job_id, input_uniprot_ids, progress_callback)


def analyze_chain_interactions(
    job_id: int,
    input_uniprot_ids: List[str],
    progress_callback=None
) -> Dict[str, Any]:
    """Analyze chain interactions for a job.

    Args:
        job_id: The job ID
        input_uniprot_ids: List of UniProt IDs to analyze
        progress_callback: Optional callback(current_pdb, total_pdbs, current_idx) for progress updates

    Returns:
        Analysis result dict
    """
    analyzer = ChainInteractionAnalyzer()
    return analyzer.analyze_job_interactions(job_id, input_uniprot_ids, progress_callback)


def retry_chain_interactions(
    job_id: int,
    input_uniprot_ids: List[str],
    failed_pdb_ids: List[str],
    progress_callback=None
) -> Dict[str, Any]:
    """Retry chain interaction analysis for specific PDBs.

    Args:
        job_id: The job ID
        input_uniprot_ids: List of input UniProt IDs
        failed_pdb_ids: List of PDB IDs to retry
        progress_callback: Optional callback for progress updates

    Returns:
        Updated analysis result
    """
    analyzer = ChainInteractionAnalyzer()
    return analyzer.retry_failed_pdbs(job_id, input_uniprot_ids, failed_pdb_ids, progress_callback)
