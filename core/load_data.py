# -*- coding: utf-8 -*-

import json
import logging  # 引入日志模块
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# -----------------------------------------------------------------------------
# 1. 定义数据类 (Data Classes)
# -----------------------------------------------------------------------------

@dataclass
class ProductionEfficiency:
    min_quantity: int
    max_quantity: int
    efficiency: float


@dataclass
class CapacityPeriod:
    start_date: str
    end_date: str
    capacity_by_process: Dict[str, int]


@dataclass
class Factory:
    factory_id: str
    region: str
    production_efficiencies: Dict[str, List[ProductionEfficiency]]
    capacity_periods: List[CapacityPeriod]


@dataclass
class Order:
    order_id: str
    customer: str
    product_type: str
    style: str
    quantity: int
    due_date: str
    material_purchasing_lead_time: int
    material_transportation_to_region_lead_time: Dict[str, int]
    production_lead_time: int
    total_process_capacity: Dict[str, int]
    eligible_factories: List[str]
    order_type: int # 1 代表正式单 (Firm Order), 0 代表预测单 (Forecast Order)
    # Optional 表示这个字段是可选的，可以不存在或为None
    fixed_assignment: Optional[Dict[str, str]] = None


# -----------------------------------------------------------------------------
# 2. 主函数 (Main Function)
#    使用 logging 模块记录信息和错误。
# -----------------------------------------------------------------------------

def load_and_structure_data(settings: Dict[str, Any]) -> (List[Factory], List[Order]):
    """
    从JSON文件中加载工厂和订单数据，并将其转换为结构化的数据类对象列表。

    Args:
        settings (Dict[str, Any]): 从 settings.json 加载的配置字典。

    Returns:
        tuple: 一个包含两个列表的元组 (factories_list, orders_list)。
               第一个列表是 Factory 对象的列表，第二个是 Order 对象的列表。

    Raises:
        FileNotFoundError: 如果配置文件中指定的数据文件路径不正确。
        json.JSONDecodeError: 如果JSON文件格式有误。
    """
    # 在实际应用中，logging.basicConfig 通常在主入口文件 (main.py) 中配置一次即可。
    # 此处为方便模块独立测试，进行简单配置。
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # 从配置中获取数据文件路径
    factory_data_path = settings['data_paths']['factory_data_path']
    order_data_path = settings['data_paths']['order_data_path']

    logging.info("开始加载数据...")

    # --- 加载并结构化工厂数据 ---
    try:
        with open(factory_data_path, 'r', encoding='utf-8') as f:
            raw_factories = json.load(f)

        factories_list: List[Factory] = []
        for factory_data in raw_factories:
            efficiencies_structured = {
                prod_type: [ProductionEfficiency(**eff) for eff in eff_list]
                for prod_type, eff_list in factory_data["production_efficiencies"].items()
            }
            capacities_structured = [CapacityPeriod(**cap) for cap in factory_data["capacity_periods"]]

            factories_list.append(Factory(
                factory_id=factory_data["factory_id"],
                region=factory_data["region"],
                production_efficiencies=efficiencies_structured,
                capacity_periods=capacities_structured
            ))
        logging.info(f"成功加载 {len(factories_list)} 个工厂数据。")

    except FileNotFoundError:
        # 对于错误信息，使用 logging.error 更为合适
        logging.error(f"工厂数据文件未找到，请检查路径配置: {factory_data_path}")
        raise
    except json.JSONDecodeError:
        logging.error(f"工厂数据文件 {factory_data_path} JSON格式无效。")
        raise
    except Exception as e:
        logging.error(f"加载工厂数据时发生未知错误: {e}")
        raise

    # --- 加载并结构化订单数据 ---
    try:
        with open(order_data_path, 'r', encoding='utf-8') as f:
            raw_orders = json.load(f)

        orders_list: List[Order] = [Order(**order_data) for order_data in raw_orders]
        logging.info(f"成功加载 {len(orders_list)} 个订单数据。")

    except FileNotFoundError:
        logging.error(f"订单数据文件未找到，请检查路径配置: {order_data_path}")
        raise
    except json.JSONDecodeError:
        logging.error(f"订单数据文件 {order_data_path} JSON格式无效。")
        raise
    except Exception as e:
        logging.error(f"加载订单数据时发生未知错误: {e}")
        raise

    logging.info("数据加载并结构化完成。")
    return factories_list, orders_list