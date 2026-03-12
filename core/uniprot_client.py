# uniprot_client.py - UniProt API 客户端（完全修复版 - 支持多实体查询）
import requests, logging, json, time, re, hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field, asdict
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

@dataclass
class UniProtEntry:
    """UniProt 条目信息"""
    uniprot_id: str
    entry_name: str
    protein_name: str
    gene_names: List[str]
    organism: str
    organism_id: int
    function: Optional[str] = None
    subcellular_location: Optional[List[str]] = None
    sequence_length: Optional[int] = None
    mass: Optional[float] = None
    pdb_ids: List[str] = field(default_factory=list)
    go_annotations: Optional[List[Dict]] = None
    keywords: Optional[List[str]] = None
    references: Optional[List[Dict]] = None
    created_at: Optional[str] = None
    last_updated: Optional[str] = None

@dataclass
class ProteinTarget:
    """标准化的蛋白质靶点信息"""
    uniprot_id: str
    protein_name: str
    gene_names: List[str]
    organism: str
    structure_ids: List[str]  # PDB/EMDB IDs
    preferred_structure_id: Optional[str] = None
    confidence_score: float = 1.0
    evidence_sources: List[str] = field(default_factory=list)
    metadata_json: Optional[str] = None
    created_at: Optional[str] = None
    last_updated: Optional[str] = None

class UniProtAPIClient:
    """UniProt API 客户端（完全修复版）"""
    
    def __init__(self, timeout: int = 30, cache_dir: str = "uniprot_cache", max_workers: int = 10):
        self.base_url = "http://rest.uniprot.org"
        self.search_url = f"{self.base_url}/uniprotkb/search"
        self.stream_url = f"{self.base_url}/uniprotkb/stream"
        self.timeout = timeout
        self.max_workers = max_workers
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CryoAgent/1.0 (literature analysis tool)",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
    
    def _get_cache_key(self, query: str) -> str:
        """生成缓存键"""
        return hashlib.md5(query.encode()).hexdigest()
    
    def _get_cache_path(self, query: str) -> Path:
        """获取缓存文件路径"""
        cache_key = self._get_cache_key(query)
        return self.cache_dir / f"{cache_key}.json"
    
    def _get_cached(self, query: str) -> Optional[Dict]:
        """从缓存获取数据"""
        cache_path = self._get_cache_path(query)
        
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 检查缓存是否过期（24小时）
                cached_time = data.get('cached_at', 0)
                if time.time() - cached_time < 86400:
                    return data.get('data')
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"读取缓存失败 {query}: {e}")
        
        return None
    
    def _save_cache(self, query: str, data: Dict) -> bool:
        """保存缓存"""
        try:
            cache_path = self._get_cache_path(query)
            cache_data = {
                'data': data,
                'query': query,
                'cached_at': time.time(),
                'cached_date': datetime.now().isoformat()
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            return True
        except (OSError, ValueError, TypeError) as e:
            logger.error(f"保存缓存失败 {query}: {e}")
            return False
    
    def get_by_uniprot_id(self, uniprot_id: str) -> Optional[UniProtEntry]:
        """通过UniProt ID获取详细信息（完全修复版）"""
        try:
            # 检查缓存
            cache_query = f"uniprot_{uniprot_id}"
            cached = self._get_cached(cache_query)
            if cached:
                return UniProtEntry(**cached)
            
            logger.info(f"获取UniProt条目: {uniprot_id}")
            
            # 方法1：使用新API
            url = f"{self.base_url}/uniprotkb/{uniprot_id}"
            
            # 最简单的请求，先获取所有数据
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_uniprot_response(data, uniprot_id)
            elif response.status_code == 404:
                logger.warning(f"UniProt条目不存在: {uniprot_id}")
                return None
            else:
                logger.error(f"获取UniProt条目失败 {uniprot_id}: {response.status_code}")
                logger.error(f"响应内容: {response.text[:500]}")
                
                # 方法2：尝试使用旧版API
                return self._get_by_uniprot_id_fallback(uniprot_id)
                
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.error(f"获取UniProt条目异常: {e}")
            return None
    
    def _parse_uniprot_response(self, data: Dict, uniprot_id: str) -> Optional[UniProtEntry]:
        """解析UniProt API响应"""
        try:
            # 提取基本信息
            uniprot_id = data.get("primaryAccession", uniprot_id)
            entry_name = data.get("uniProtkbId", "")
            
            # 提取蛋白质名称
            protein_name = ""
            protein_desc = data.get("proteinDescription", {})
            if protein_desc:
                rec_name = protein_desc.get("recommendedName", {})
                if rec_name:
                    full_name = rec_name.get("fullName", {})
                    if isinstance(full_name, dict):
                        protein_name = full_name.get("value", "")
            
            # 提取基因名称
            gene_names = []
            genes = data.get("genes", [])
            for gene in genes:
                gene_name = gene.get("geneName", {})
                if isinstance(gene_name, dict):
                    gene_names.append(gene_name.get("value", ""))
                elif isinstance(gene_name, str):
                    gene_names.append(gene_name)
            
            # 提取生物体信息
            organism = ""
            organism_id = 0
            org_data = data.get("organism", {})
            if isinstance(org_data, dict):
                organism = org_data.get("scientificName", "")
                organism_id = org_data.get("taxonId", 0)
            
            # 提取功能描述
            function = None
            comments = data.get("comments", [])
            for comment in comments:
                if comment.get("commentType") == "FUNCTION":
                    texts = comment.get("texts", [])
                    if texts:
                        first_text = texts[0]
                        if isinstance(first_text, dict):
                            function = first_text.get("value", "")
                        else:
                            function = str(first_text)
                    break
            
            # 提取PDB IDs
            pdb_ids = []
            cross_refs = data.get("uniProtKBCrossReferences", [])
            for xref in cross_refs:
                if xref.get("database") == "PDB":
                    pdb_id = xref.get("id", "")
                    if pdb_id:
                        pdb_ids.append(pdb_id.upper())
            
            # 提取序列信息
            sequence_length = None
            mass = None
            seq_data = data.get("sequence", {})
            if isinstance(seq_data, dict):
                sequence_length = seq_data.get("length")
                mass = seq_data.get("molWeight")
            
            # 提取亚细胞定位
            subcellular_location = []
            for comment in comments:
                if comment.get("commentType") == "SUBCELLULAR_LOCATION":
                    locations = comment.get("locations", [])
                    for loc in locations:
                        location = loc.get("location", {})
                        if isinstance(location, dict):
                            subcellular_location.append(location.get("value", ""))
            
            # 提取关键词
            keywords = []
            for keyword in data.get("keywords", []):
                keyword_name = keyword.get("name", "")
                if keyword_name:
                    keywords.append(keyword_name)
            
            # 创建条目
            entry = UniProtEntry(
                uniprot_id=uniprot_id,
                entry_name=entry_name,
                protein_name=protein_name,
                gene_names=gene_names,
                organism=organism,
                organism_id=organism_id,
                function=function,
                subcellular_location=subcellular_location,
                sequence_length=sequence_length,
                mass=mass,
                pdb_ids=pdb_ids,
                keywords=keywords,
                last_updated=datetime.now().isoformat()
            )
            
            # 保存到缓存
            self._save_cache(f"uniprot_{uniprot_id}", asdict(entry))
            
            logger.info(f"UniProt条目获取成功: {uniprot_id}")
            return entry
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"解析UniProt响应失败: {e}")
            return None
    
    def _get_by_uniprot_id_fallback(self, uniprot_id: str) -> Optional[UniProtEntry]:
        """备用的UniProt获取方法"""
        try:
            # 尝试旧版API格式
            url = f"https://www.uniprot.org/uniprot/{uniprot_id}.json"
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                # 旧版API格式不同，需要不同的解析
                entry = self._parse_old_uniprot_format(data, uniprot_id)
                if entry:
                    logger.info(f"通过旧版API获取UniProt条目成功: {uniprot_id}")
                    return entry
            
            return None
            
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.error(f"备用UniProt获取失败: {e}")
            return None
    
    def _parse_old_uniprot_format(self, data: Dict, uniprot_id: str) -> Optional[UniProtEntry]:
        """解析旧版UniProt API格式"""
        try:
            # 旧版格式可能有不同的结构
            protein_name = ""
            if "protein" in data and "recommendedName" in data["protein"]:
                name_data = data["protein"]["recommendedName"]
                if "fullName" in name_data and "value" in name_data["fullName"]:
                    protein_name = name_data["fullName"]["value"]
            
            # 提取基因名称
            gene_names = []
            if "gene" in data:
                gene_data = data["gene"]
                if isinstance(gene_data, list):
                    for gene in gene_data:
                        if "name" in gene and "value" in gene["name"]:
                            gene_names.append(gene["name"]["value"])
            
            # 提取生物体
            organism = ""
            organism_id = 0
            if "organism" in data:
                org_data = data["organism"]
                if "scientificName" in org_data:
                    organism = org_data["scientificName"]
                if "taxonId" in org_data:
                    organism_id = org_data["taxonId"]
            
            # 提取PDB IDs
            pdb_ids = []
            if "dbReferences" in data:
                for ref in data["dbReferences"]:
                    if ref.get("type") == "PDB":
                        pdb_id = ref.get("id", "")
                        if pdb_id:
                            pdb_ids.append(pdb_id.upper())
            
            entry = UniProtEntry(
                uniprot_id=uniprot_id,
                entry_name=data.get("id", ""),
                protein_name=protein_name,
                gene_names=gene_names,
                organism=organism,
                organism_id=organism_id,
                pdb_ids=pdb_ids,
                last_updated=datetime.now().isoformat()
            )
            
            return entry
            
        except (KeyError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"解析旧版UniProt格式失败: {e}")
            return None
    
    def get_by_pdb_id(self, pdb_id: str) -> List[UniProtEntry]:
        """通过PDB ID获取相关的UniProt条目"""
        try:
            cache_query = f"pdb_to_uniprot_{pdb_id}"
            cached = self._get_cached(cache_query)
            if cached:
                return [UniProtEntry(**item) for item in cached]
            
            logger.info(f"通过PDB ID查找UniProt条目: {pdb_id}")
            
            # 方法1：使用PDB交叉引用搜索
            params = {
                "query": f"(xref:pdb-{pdb_id.lower()})",
                "format": "json",
                "size": 50,
                "fields": "accession,id,protein_name,gene_names,organism_name,organism_id,length,mass,cc_function,cc_subcellular_location,xref_pdb"
            }
            
            response = self.session.get(self.search_url, params=params, timeout=self.timeout)
            
            entries = []
            
            if response.status_code == 200:
                data = response.json()
                
                for item in data.get("results", []):
                    # 提取PDB IDs
                    pdb_ids_for_entry = []
                    for xref in item.get("uniProtKBCrossReferences", []):
                        if xref.get("database") == "PDB":
                            pdb_id_from_xref = xref.get("id")
                            if pdb_id_from_xref:
                                pdb_ids_for_entry.append(pdb_id_from_xref.upper())
                    
                    # 检查这个条目是否包含我们要找的PDB
                    if pdb_id.upper() in pdb_ids_for_entry or pdb_id.lower() in [p.lower() for p in pdb_ids_for_entry]:
                        # 获取完整条目信息
                        full_entry = self.get_by_uniprot_id(item.get("primaryAccession", ""))
                        if full_entry:
                            entries.append(full_entry)
            
            # 方法2：如果方法1没找到，使用PDB API
            if not entries:
                entries = self._get_uniprot_from_pdb_api_enhanced(pdb_id)
            
            # 保存到缓存
            if entries:
                self._save_cache(cache_query, [asdict(e) for e in entries])
            
            logger.info(f"通过PDB {pdb_id} 找到 {len(entries)} 个UniProt条目")
            return entries
            
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.error(f"通过PDB ID查找异常: {e}")
            return []
    
    def _get_uniprot_from_pdb_api_enhanced(self, pdb_id: str) -> List[UniProtEntry]:
        """通过PDB API获取UniProt映射 - 增强版，查询所有实体"""
        try:
            logger.info(f"通过PDBe API获取UniProt映射: {pdb_id}")
            
            # 使用PDBe API获取UniProt映射
            mapping_data = self._fetch_pdbe_endpoint(f"mappings/uniprot/{pdb_id.lower()}")
            
            if not mapping_data:
                logger.warning(f"PDBe API Uniprot映射请求失败")
                return []
            
            entries = []
            
            # 提取UniProt ID
            uniprot_ids = self._extract_uniprot_ids(mapping_data, pdb_id)
            logger.info(f"从PDBe API提取到 {len(uniprot_ids)} 个UniProt ID: {uniprot_ids}")
            
            # 并行获取所有UniProt条目
            entries = self._batch_get_uniprot_entries(uniprot_ids, pdb_id)
            
            return entries
            
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.error(f"通过PDBe API获取UniProt映射失败: {e}")
            return []

    def _fetch_pdbe_endpoint(self, endpoint: str, use_custom_timeout: int = None) -> Optional[Dict]:
        """获取PDBe API数据"""
        try:
            url = f"https://www.ebi.ac.uk/pdbe/api/pdb/{endpoint}"
            headers = {
                "User-Agent": "CryoAgent/1.0",
                "Accept": "application/json"
            }
            
            timeout = use_custom_timeout if use_custom_timeout else self.timeout
            response = requests.get(url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.debug(f"PDBe API请求失败 {endpoint}: {response.status_code}")
                return None
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.debug(f"PDBe API请求异常 {endpoint}: {e}")
            return None

    def _extract_uniprot_ids(self, mapping_data: Dict, pdb_id: str) -> List[str]:
        """从PDBe映射数据中提取UniProt IDs"""
        uniprot_ids = set()
        
        if not mapping_data or pdb_id.lower() not in mapping_data:
            return []
        
        pdb_data = mapping_data.get(pdb_id.lower(), {})
        
        # 提取所有UniProt IDs
        for chain_id, chain_data in pdb_data.items():
            for segment in chain_data.get("segments", []):
                if "uniprot_accession" in segment:
                    uniprot_id = segment["uniprot_accession"]
                    if uniprot_id:
                        uniprot_ids.add(uniprot_id)
        
        return list(uniprot_ids)

    def _query_entity_details(self, pdb_id: str, entity_id: str) -> List[str]:
        """查询单个实体详情并提取UniProt ID"""
        try:
            headers = {
                "User-Agent": "CryoAgent/1.0",
                "Accept": "application/json"
            }
            
            # 查询单个聚合物实体的详细信息
            entity_url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id.lower()}/{entity_id}"
            entity_response = requests.get(entity_url, headers=headers, timeout=10)
            
            if entity_response.status_code == 200:
                entity_data = entity_response.json()
                return self._extract_uniprot_from_entity(entity_data)
            else:
                logger.debug(f"查询实体 {entity_id} 失败: {entity_response.status_code}")
                return []
                
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.debug(f"查询实体 {entity_id} 异常: {e}")
            return []
    
    def _batch_get_uniprot_entries(self, uniprot_ids: List[str], pdb_id: str) -> List[UniProtEntry]:
        """批量获取UniProt条目"""
        entries = []
        
        # 使用线程池并行获取
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_uniprot = {}
            for uniprot_id in uniprot_ids:
                future = executor.submit(self.get_by_uniprot_id, uniprot_id)
                future_to_uniprot[future] = uniprot_id
            
            for future in as_completed(future_to_uniprot):
                uniprot_id = future_to_uniprot[future]
                try:
                    entry = future.result()
                    if entry:
                        # 确保这个PDB在条目的PDB列表中
                        if pdb_id.upper() not in entry.pdb_ids:
                            entry.pdb_ids.append(pdb_id.upper())
                        entries.append(entry)
                except (requests.RequestException, ValueError, TypeError) as e:
                    logger.debug(f"获取UniProt条目 {uniprot_id} 失败: {e}")
        
        return entries
    
    def _extract_uniprot_from_entity(self, entity_data: Dict) -> List[str]:
        """从聚合物实体数据中提取UniProt ID"""
        uniprot_ids = set()
        
        # 方法1：从rcsb_polymer_entity_align获取
        if 'rcsb_polymer_entity_align' in entity_data:
            for align in entity_data['rcsb_polymer_entity_align']:
                if align.get('reference_database_name') == 'UniProt':
                    accession = align.get('reference_database_accession')
                    if accession:
                        uniprot_ids.add(accession)
        
        # 方法2：从rcsb_polymer_entity_container_identifiers获取
        if 'rcsb_polymer_entity_container_identifiers' in entity_data:
            identifiers = entity_data['rcsb_polymer_entity_container_identifiers']
            if 'uniprot_ids' in identifiers:
                for uniprot_id in identifiers['uniprot_ids']:
                    if uniprot_id:
                        uniprot_ids.add(uniprot_id)
        
        # 方法3：从rcsb_entity_source_organism获取
        if 'rcsb_entity_source_organism' in entity_data:
            for organism in entity_data['rcsb_entity_source_organism']:
                if 'uniprot_accession' in organism:
                    uniprot_id = organism['uniprot_accession']
                    if uniprot_id:
                        uniprot_ids.add(uniprot_id)
        
        return list(uniprot_ids)
    
    def _try_alternative_methods(self, data: Dict, pdb_id: str) -> List[UniProtEntry]:
        """尝试其他方法获取UniProt映射"""
        entries = []
        
        # 方法B：从rcsb_struct_ref获取（结构引用）
        if 'rcsb_struct_ref' in data:
            for ref in data['rcsb_struct_ref']:
                if 'db_name' in ref and ref['db_name'] == 'UNP' and 'db_accession' in ref:
                    uniprot_id = ref['db_accession']
                    if uniprot_id:
                        try:
                            entry = self.get_by_uniprot_id(uniprot_id)
                            if entry and pdb_id.upper() not in entry.pdb_ids:
                                entry.pdb_ids.append(pdb_id.upper())
                                entries.append(entry)
                        except (requests.RequestException, ValueError, TypeError) as e:
                            logger.debug(f"获取UniProt条目 {uniprot_id} 失败: {e}")
        
        # 方法C：从标题中提取蛋白质名称
        if not entries:
            title = data.get("struct", {}).get("title", "")
            if title:
                protein_names = self._extract_protein_names_from_title(title)
                for protein_name in protein_names:
                    if len(protein_name) > 3:
                        search_results = self.search_by_protein_name(protein_name, limit=3)
                        for result in search_results:
                            entry = self.get_by_uniprot_id(result["uniprot_id"])
                            if entry and entry.uniprot_id not in [e.uniprot_id for e in entries]:
                                if pdb_id.upper() not in entry.pdb_ids:
                                    entry.pdb_ids.append(pdb_id.upper())
                                entries.append(entry)
        
        return entries
    
    def search_by_protein_name(self, protein_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """通过蛋白质名称搜索"""
        try:
            # 检查缓存
            cache_query = f"search_{protein_name}_{limit}"
            cached = self._get_cached(cache_query)
            if cached:
                return cached
            
            logger.info(f"搜索UniProt蛋白质: {protein_name}")
            
            # 构建搜索参数 - 修复查询语法
            query = f'name:"{protein_name}" OR gene:"{protein_name}"'
            params = {
                "query": query,
                "format": "json",
                "size": limit,
                "fields": "accession,id,protein_name,gene_names,organism_name,organism_id"
            }
            
            response = self.session.get(self.search_url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for item in data.get("results", []):
                    # 提取基因名称
                    gene_names = []
                    for gene in item.get("genes", []):
                        gene_name = gene.get("geneName", {})
                        if isinstance(gene_name, dict):
                            gene_names.append(gene_name.get("value", ""))
                        else:
                            gene_names.append(str(gene_name))
                    
                    # 提取蛋白质名称
                    protein_name_val = ""
                    protein_desc = item.get("proteinDescription", {})
                    if protein_desc:
                        rec_name = protein_desc.get("recommendedName", {})
                        if rec_name:
                            full_name = rec_name.get("fullName", {})
                            if isinstance(full_name, dict):
                                protein_name_val = full_name.get("value", "")
                    
                    result = {
                        "uniprot_id": item.get("primaryAccession", ""),
                        "entry_name": item.get("uniProtkbId", ""),
                        "protein_name": protein_name_val,
                        "gene_names": gene_names,
                        "organism": item.get("organism", {}).get("scientificName", ""),
                        "organism_id": item.get("organism", {}).get("taxonId", 0),
                        "score": item.get("score", 0)
                    }
                    results.append(result)
                
                # 保存缓存
                self._save_cache(cache_query, results)
                
                logger.info(f"UniProt搜索完成: {protein_name} -> {len(results)} 个结果")
                return results
            else:
                logger.error(f"UniProt搜索失败: {response.status_code}")
                logger.error(f"响应: {response.text[:200]}")
                return []
                
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.error(f"UniProt搜索异常: {e}")
            return []
    
    def _extract_protein_names_from_title(self, title: str) -> List[str]:
        """从标题中提取蛋白质名称"""
        if not title:
            return []
        
        protein_names = []
        
        import re
        
        # 查找大写字母开头的蛋白质名称
        uppercase_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', title)
        
        for word in uppercase_words:
            # 排除常见非蛋白质词汇
            exclude_words = ["In", "Of", "The", "And", "Structure", "Mouse", "Human", 
                           "Reveals", "Insights", "Into", "Situ", "Cryo", "EM", 
                           "Central", "Apparatus", "Sperm", "Axoneme"]
            if word not in exclude_words and len(word) > 3:
                protein_names.append(word)
        
        # 查找常见的蛋白质模式
        protein_patterns = [
            r'([A-Z]{3,}[0-9]{0,3}[A-Z]{0,3})',  # 如EGFR, GPR158
            r'([A-Z]+[0-9]+[A-Z]*)',  # 如p53, Akt1
        ]
        
        for pattern in protein_patterns:
            matches = re.findall(pattern, title)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if len(match) >= 2:
                    protein_names.append(match)
        
        # 去重
        return list(set(protein_names))
    
    def _get_pdb_info(self, pdb_id: str) -> Optional[Dict]:
        """获取PDB结构基本信息"""
        try:
            url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id.lower()}"
            headers = {
                "User-Agent": "CryoAgent/1.0",
                "Accept": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            return None
        except (requests.RequestException, requests.Timeout, requests.ConnectionError) as e:
            logger.debug(f"获取PDB信息失败 {pdb_id}: {e}")
            return None

class UniProtNormalizer:
    """UniProt标准化器"""
    
    def __init__(self, client: UniProtAPIClient = None):
        self.client = client or UniProtAPIClient()
        
        # 常见蛋白质的标准化映射
        self.protein_aliases = {
            # GPCR家族
            "GPR158": ["GPR158", "ADGRL4", "G protein-coupled receptor 158"],
            "GPR179": ["GPR179", "ADGRL3", "G protein-coupled receptor 179"],
            "GPCR": ["G protein-coupled receptor"],
            "EGFR": ["EGFR", "ERBB1", "HER1", "Epidermal growth factor receptor"],
            "HER2": ["HER2", "ERBB2", "Neu", "Human epidermal growth factor receptor 2"],
            "PDGFR": ["PDGFR", "PDGFRA", "PDGFRB", "Platelet-derived growth factor receptor"],
            "VEGFR": ["VEGFR", "FLT1", "KDR", "FLT4", "Vascular endothelial growth factor receptor"],
            
            # 常见结构蛋白
            "actin": ["ACTB", "ACTG1", "Actin"],
            "tubulin": ["TUBB", "TUBA1A", "Tubulin"],
            "myosin": ["MYH", "Myosin heavy chain"],
            "collagen": ["COL1A1", "COL2A1", "Collagen"],
            
            # 膜蛋白
            "aquaporin": ["AQP1", "AQP2", "Aquaporin"],
            "ATPase": ["ATP1A1", "ATP2A2", "ATP synthase"],
            "ion channel": ["SCN1A", "KCNH2", "CACNA1C"]
        }
    
    def normalize_protein_name(self, protein_name: str) -> List[str]:
        """标准化蛋白质名称"""
        protein_name = protein_name.strip().upper()
        
        # 检查是否是已知别名
        normalized_names = []
        
        for standard_name, aliases in self.protein_aliases.items():
            for alias in aliases:
                if alias.upper() == protein_name or alias.upper() in protein_name:
                    normalized_names.append(standard_name)
        
        # 如果没找到，返回原始名称
        if not normalized_names:
            normalized_names = [protein_name]
        
        return list(set(normalized_names))
    
    def extract_protein_names_from_text(self, text: str) -> List[str]:
        """从文本中提取蛋白质名称"""
        # 简单的正则表达式匹配
        protein_patterns = [
            r'\b([A-Z]{2,}[0-9]{3,}[A-Z0-9]*)\b',  # 如GPR158, EGFR1
            r'\b([A-Z]{3,}[0-9]{3,})\b',  # 如GPR158
            r'\b([A-Z]{2,}[0-9]{4,})\b',  # 如GPR1580
            r'\b(GPR|GPCR|EGFR|HER|PDGFR|VEGFR|FGFR|IGF|TGF)[0-9]+\b',  # 常见蛋白质家族
            r'\b([A-Z]+[0-9]+[A-Z]*)\b',  # 通用模式
        ]
        
        protein_names = set()
        
        for pattern in protein_patterns:
            matches = re.findall(pattern, text.upper())
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                
                if match and len(match) >= 4:
                    # 过滤常见非蛋白质词汇
                    exclude_words = ['PROTEIN', 'STRUCTURE', 'PDB', 'EMDB', 'WHAT', 'HOW', 
                                   'MANY', 'RESOLUTION', 'QUESTION', 'ABOUT', 'THIS', 'THAT']
                    
                    if not any(exclude_word in match for exclude_word in exclude_words):
                        # 标准化名称
                        normalized = self.normalize_protein_name(match)
                        protein_names.update(normalized)
        
        return list(protein_names)
    
    def find_best_uniprot_match(self, protein_name: str, organism: str = None) -> Optional[Dict[str, Any]]:
        """找到最佳的UniProt匹配"""
        # 首先尝试通过蛋白质名称搜索
        results = self.client.search_by_protein_name(protein_name, limit=5)
        
        if not results:
            # 尝试通过基因名称搜索
            if organism:
                results = self.client.search_by_protein_name(f"{protein_name} {organism}", limit=5)
        
        if not results:
            return None
        
        # 根据评分选择最佳匹配
        best_match = max(results, key=lambda x: x.get('score', 0))
        
        # 获取详细信息
        uniprot_entry = self.client.get_by_uniprot_id(best_match['uniprot_id'])
        
        if uniprot_entry:
            return {
                'uniprot_id': uniprot_entry.uniprot_id,
                'protein_name': uniprot_entry.protein_name,
                'gene_names': uniprot_entry.gene_names,
                'organism': uniprot_entry.organism,
                'function': uniprot_entry.function,
                'structure_ids': uniprot_entry.pdb_ids,
                'confidence': best_match.get('score', 0) / 100,
                'source': 'uniprot_search'
            }
        
        return None



# ---------- 全局实例 ----------
_uniprot_client = None
_uniprot_normalizer = None

def get_uniprot_client() -> UniProtAPIClient:
    """获取UniProt客户端实例"""
    global _uniprot_client
    if _uniprot_client is None:
        _uniprot_client = UniProtAPIClient()
    return _uniprot_client

def get_uniprot_normalizer() -> UniProtNormalizer:
    """获取UniProt标准化器实例"""
    global _uniprot_normalizer
    if _uniprot_normalizer is None:
        client = get_uniprot_client()
        _uniprot_normalizer = UniProtNormalizer(client)
    return _uniprot_normalizer

# ---------- 使用示例 ----------
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 测试UniProt客户端
    client = get_uniprot_client()
    normalizer = get_uniprot_normalizer()
    
    # 测试UniProt ID获取
    print("测试UniProt条目获取:")
    test_ids = ["P04637", "P00533", "P00720", "P0DTC2", "Q5T848"]
    
    for uniprot_id in test_ids:
        print(f"\n查询 {uniprot_id}:")
        entry = client.get_by_uniprot_id(uniprot_id)
        if entry:
            print(f"✅ 成功: {entry.protein_name}")
            print(f"   基因: {entry.gene_names}")
            print(f"   物种: {entry.organism}")
            if entry.function:
                print(f"   功能: {entry.function[:100]}...")
            print(f"   PDBs: {entry.pdb_ids[:5]}")
        else:
            print(f"❌ 未找到")
    
    # 测试PDB到UniProt映射
    print("\n\n测试PDB到UniProt映射:")
    test_pdbs = ["7EWL", "6VSB", "5T1A", "9IJJ", "9MD3", "1AON"]
    
    for pdb_id in test_pdbs:
        print(f"\n查询PDB {pdb_id}:")
        entries = client.get_by_pdb_id(pdb_id)
        if entries:
            print(f"✅ 找到 {len(entries)} 个条目")
            # 显示前5个条目
            for i, entry in enumerate(entries[:5]):
                print(f"  {i+1}. {entry.uniprot_id}: {entry.protein_name}")
                print(f"     基因: {entry.gene_names}")
                print(f"     物种: {entry.organism}")
            if len(entries) > 5:
                print(f"  ... 还有 {len(entries)-5} 个条目")
        else:
            print(f"❌ 未找到")
    
    print("\n✅ UniProt客户端测试完成")