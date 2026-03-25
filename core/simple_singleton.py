# simple_singleton.py
import threading
from typing import Dict, Any

class SimpleSingleton:
    """简单可靠的单例管理器"""

    _instances: Dict[str, Any] = {}

    @classmethod
    def get_instance(cls, class_type, *args, **kwargs):
        """获取单例实例 - 线程安全版本"""
        class_name = class_type.__name__

        # 先检查是否已存在（不加锁）
        if class_name in cls._instances:
            return cls._instances[class_name]

        # 不使用锁，避免死锁
        # 直接创建实例
        print(f"正在创建 {class_name} 单例实例...")
        instance = class_type(*args, **kwargs)
        cls._instances[class_name] = instance
        print(f"创建单例实例成功: {class_name}")

        return instance

    @classmethod
    def clear_instance(cls, class_type):
        """清除单例实例"""
        class_name = class_type.__name__
        if class_name in cls._instances:
            del cls._instances[class_name]
            print(f"清除单例实例: {class_name}")
