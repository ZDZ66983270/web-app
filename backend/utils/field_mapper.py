"""
字段名称映射工具 (Field Mapper)
==================================

用途：
- 在 YAML 标准字段名与数据库字段名之间进行转换
- 支持通用企业财报模板的字段别名处理
- 确保向后兼容性

作者: Antigravity
日期: 2026-02-02
"""

from typing import Dict, Optional
import yaml
import os

class FieldMapper:
    """
    字段名称映射工具
    
    功能：
    1. YAML 标准名 ↔ 数据库字段名 双向映射
    2. 自动加载 generic_fundamentals_core.yaml 配置
    3. 支持字段别名和状态查询
    """
    
    # 硬编码的核心映射（作为 fallback）
    YAML_TO_DB_CORE = {
        "net_income_attributable_to_common_ttm": "net_income_common_ttm",
        "eps_ttm": "eps",
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化字段映射器
        
        Args:
            config_path: YAML 配置文件路径，默认为 backend/config/generic_fundamentals_core.yaml
        """
        if config_path is None:
            # 自动定位配置文件
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, '..', 'config', 'generic_fundamentals_core.yaml')
        
        self.config_path = config_path
        self.yaml_to_db: Dict[str, str] = {}
        self.db_to_yaml: Dict[str, str] = {}
        self.field_metadata: Dict[str, Dict] = {}
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """从 YAML 文件加载字段映射配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
                # 解析字段映射
                if 'fields' in config:
                    for field in config['fields']:
                        yaml_name = field.get('name')
                        db_field = field.get('db_field', yaml_name)
                        
                        if yaml_name:
                            self.yaml_to_db[yaml_name] = db_field
                            self.db_to_yaml[db_field] = yaml_name
                            self.field_metadata[yaml_name] = field
                
                print(f"✅ Loaded {len(self.yaml_to_db)} field mappings from {self.config_path}")
            else:
                print(f"⚠️ Config file not found: {self.config_path}, using core mappings only")
                self.yaml_to_db = self.YAML_TO_DB_CORE.copy()
                self.db_to_yaml = {v: k for k, v in self.YAML_TO_DB_CORE.items()}
        
        except Exception as e:
            print(f"⚠️ Failed to load config: {e}, using core mappings only")
            self.yaml_to_db = self.YAML_TO_DB_CORE.copy()
            self.db_to_yaml = {v: k for k, v in self.YAML_TO_DB_CORE.items()}
    
    def to_db_field(self, yaml_field: str) -> str:
        """
        YAML 标准字段名 → 数据库字段名
        
        Args:
            yaml_field: YAML 模板中的字段名
        
        Returns:
            数据库字段名（如果没有映射则返回原字段名）
        
        Example:
            >>> mapper.to_db_field("net_income_attributable_to_common_ttm")
            'net_income_common_ttm'
        """
        return self.yaml_to_db.get(yaml_field, yaml_field)
    
    def to_yaml_field(self, db_field: str) -> str:
        """
        数据库字段名 → YAML 标准字段名
        
        Args:
            db_field: 数据库中的字段名
        
        Returns:
            YAML 标准字段名（如果没有映射则返回原字段名）
        
        Example:
            >>> mapper.to_yaml_field("net_income_common_ttm")
            'net_income_attributable_to_common_ttm'
        """
        return self.db_to_yaml.get(db_field, db_field)
    
    def map_dict_to_db(self, yaml_data: Dict) -> Dict:
        """
        将整个字典的键从 YAML 名映射到数据库字段名
        
        Args:
            yaml_data: 使用 YAML 标准字段名的字典
        
        Returns:
            使用数据库字段名的字典
        
        Example:
            >>> data = {"eps_ttm": 1.5, "revenue_ttm": 1000000}
            >>> mapper.map_dict_to_db(data)
            {'eps': 1.5, 'revenue_ttm': 1000000}
        """
        return {
            self.to_db_field(k): v 
            for k, v in yaml_data.items()
        }
    
    def map_dict_to_yaml(self, db_data: Dict) -> Dict:
        """
        将整个字典的键从数据库字段名映射到 YAML 标准名
        
        Args:
            db_data: 使用数据库字段名的字典
        
        Returns:
            使用 YAML 标准字段名的字典
        """
        return {
            self.to_yaml_field(k): v 
            for k, v in db_data.items()
        }
    
    def get_field_info(self, yaml_field: str) -> Optional[Dict]:
        """
        获取字段的元数据信息
        
        Args:
            yaml_field: YAML 标准字段名
        
        Returns:
            字段元数据（包括 label_zh, description, category, required 等）
        """
        return self.field_metadata.get(yaml_field)
    
    def is_required(self, yaml_field: str) -> bool:
        """
        检查字段是否为必需字段
        
        Args:
            yaml_field: YAML 标准字段名
        
        Returns:
            是否为必需字段
        """
        info = self.get_field_info(yaml_field)
        return info.get('required', False) if info else False
    
    def get_field_status(self, yaml_field: str) -> str:
        """
        获取字段的对齐状态
        
        Args:
            yaml_field: YAML 标准字段名
        
        Returns:
            'aligned', 'aliased', 'missing' 等状态
        """
        info = self.get_field_info(yaml_field)
        return info.get('status', 'unknown') if info else 'unknown'
    
    def list_aliased_fields(self) -> Dict[str, str]:
        """
        列出所有需要别名处理的字段
        
        Returns:
            {yaml_name: db_field} 的字典，仅包含 status='aliased' 的字段
        """
        aliased = {}
        for yaml_name, metadata in self.field_metadata.items():
            if metadata.get('status') == 'aliased':
                aliased[yaml_name] = metadata.get('db_field')
        return aliased
    
    def list_required_fields(self) -> list:
        """
        列出所有必需字段
        
        Returns:
            必需字段的 YAML 标准名列表
        """
        return [
            name for name, metadata in self.field_metadata.items()
            if metadata.get('required', False)
        ]


# 全局单例实例
_global_mapper = None

def get_field_mapper() -> FieldMapper:
    """
    获取全局 FieldMapper 单例实例
    
    Returns:
        FieldMapper 实例
    """
    global _global_mapper
    if _global_mapper is None:
        _global_mapper = FieldMapper()
    return _global_mapper


# 便捷函数
def to_db_field(yaml_field: str) -> str:
    """便捷函数：YAML 字段名 → 数据库字段名"""
    return get_field_mapper().to_db_field(yaml_field)

def to_yaml_field(db_field: str) -> str:
    """便捷函数：数据库字段名 → YAML 字段名"""
    return get_field_mapper().to_yaml_field(db_field)

def map_dict_to_db(yaml_data: Dict) -> Dict:
    """便捷函数：字典键映射到数据库字段名"""
    return get_field_mapper().map_dict_to_db(yaml_data)


if __name__ == "__main__":
    # 测试代码
    mapper = FieldMapper()
    
    print("\n=== Field Mapper Test ===")
    print(f"Total mappings loaded: {len(mapper.yaml_to_db)}")
    
    print("\n--- Aliased Fields ---")
    for yaml_name, db_name in mapper.list_aliased_fields().items():
        print(f"  {yaml_name} → {db_name}")
    
    print("\n--- Required Fields ---")
    for field in mapper.list_required_fields():
        print(f"  ✓ {field}")
    
    print("\n--- Mapping Test ---")
    test_data = {
        "eps_ttm": 1.5,
        "net_income_attributable_to_common_ttm": 1000000,
        "revenue_ttm": 5000000
    }
    print(f"YAML data: {test_data}")
    db_data = mapper.map_dict_to_db(test_data)
    print(f"DB data: {db_data}")
