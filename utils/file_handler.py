# -*- coding: utf-8 -*-

import json
import os
import logging
from typing import List, Dict, Any


def save_data_to_json(data_to_save: Any, output_path: str):
    """
    将数据（列表或字典）以JSON格式保存到指定文件。
    会自动创建不存在的目录。
    """
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
        logging.info(f"数据成功保存至: '{output_path}'")
    except Exception as e:
        logging.error(f"写入JSON文件 '{output_path}' 时发生错误: {e}", exc_info=True)