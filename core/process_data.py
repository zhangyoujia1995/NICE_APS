# -*- coding: utf-8 -*-

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Dict, Any, Set

# 从同级目录的 load_data 模块中导入我们定义的数据类
from .load_data import Factory, Order, CapacityPeriod, ProductionEfficiency


# -----------------------------------------------------------------------------
# 1. 定义预处理后的数据容器
#    这个 dataclass 将作为所有预处理后数据的统一容器，传递给后续模块。
# -----------------------------------------------------------------------------

@dataclass
class APSInputData:
    """
    一个容器，用于存放所有经过预处理、可直接用于构建优化模型的数据。
    """
    # 基础数据
    factories: List[Factory]
    orders: List[Order]
    settings: Dict[str, Any]

    # 方便查询的映射表 (Maps)
    factory_map: Dict[str, Factory] = field(default_factory=dict)  # factory_id -> Factory 对象
    order_map: Dict[str, Order] = field(default_factory=dict)  # order_id -> Order 对象

    # 派生和计算出的数据
    base_date: date = None  # 从 settings 中解析出的基准日期对象
    all_processes: Set[str] = field(default_factory=set)  # 数据中出现的所有不重复的工序名称集合

    # 为"负载均衡"目标预先计算的总量
    # key: order_id, value: 订单不考虑效率的标准总工作量
    order_total_base_workload: Dict[str, float] = field(default_factory=dict)
    # key: factory_id, value: {周期开始日期: 周期总产能}
    factory_total_capacity_by_period: Dict[str, Dict[str, float]] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# 2. 辅助函数
# -----------------------------------------------------------------------------

def _get_efficiency_for_order(order: Order, factory: Factory) -> float:
    """
    根据订单的品类和数量，查询其在特定工厂的生产效率。

    Args:
        order (Order): 订单对象。
        factory (Factory): 工厂对象。

    Returns:
        float: 生产效率值。如果找不到匹配的效率区间，则返回1.0作为默认值。
    """
    # 检查该工厂是否有该产品品类的效率定义
    if order.product_type not in factory.production_efficiencies:
        logging.warning(
            f"工厂 {factory.factory_id} 未找到产品品类 '{order.product_type}' 的效率定义，将使用默认效率 1.0。")
        return 1.0

    # 寻找订单数量所在的效率区间
    efficiency_tiers = factory.production_efficiencies[order.product_type]
    for tier in efficiency_tiers:
        if tier.min_quantity <= order.quantity <= tier.max_quantity:
            return tier.efficiency

    logging.warning(f"订单 {order.order_id} (数量: {order.quantity}) 在工厂 {factory.factory_id} "
                    f"未找到匹配的数量效率区间，将使用默认效率 1.0。")
    return 1.0


# -----------------------------------------------------------------------------
# 3. 主函数
# -----------------------------------------------------------------------------

def process_data(factories: List[Factory], orders: List[Order], settings: Dict[str, Any]) -> APSInputData:
    """
    对加载的数据进行预处理，包括创建查询映射、转换日期、计算聚合值等。

    Args:
        factories (List[Factory]): 从 load_data.py 加载的工厂对象列表。
        orders (List[Order]): 从 load_data.py 加载的订单对象列表。
        settings (Dict[str, Any]): 全局配置字典。

    Returns:
        APSInputData: 一个包含了所有预处理后数据的实例。
    """
    logging.info("开始预处理数据...")

    # 1. 初始化数据容器
    aps_input = APSInputData(
        factories=factories,
        orders=orders,
        settings=settings,
        factory_map={f.factory_id: f for f in factories},
        order_map={o.order_id: o for o in orders}
    )

    # 2. 处理日期
    base_date_str = settings['run_config']['base_date']
    aps_input.base_date = datetime.strptime(base_date_str, '%Y-%m-%d').date()
    logging.info(f"计算基准日期 (base_date) 设置为: {aps_input.base_date}")

    # 3. 收集所有工序 & 计算聚合数据用于负载均衡
    all_procs: Set[str] = set()

    # 3.1 遍历工厂计算总产能, 并收集工序
    for factory in aps_input.factories:
        aps_input.factory_total_capacity_by_period[factory.factory_id] = {}
        for period in factory.capacity_periods:
            total_capacity = sum(period.capacity_by_process.values())
            aps_input.factory_total_capacity_by_period[factory.factory_id][period.start_date] = total_capacity
            # 将该周期的所有工序名称加入到集合中
            all_procs.update(period.capacity_by_process.keys())

    # 3.2 遍历订单计算总工作量, 并收集工序
    for order in aps_input.orders:
        total_workload = sum(order.total_process_capacity.values())
        aps_input.order_total_base_workload[order.order_id] = total_workload
        # 将该订单的所有工序名称加入到集合中
        all_procs.update(order.total_process_capacity.keys())

    aps_input.all_processes = all_procs
    logging.info(f"收据数据中所有不重复的工序为: {aps_input.all_processes}")

    # 4. 可以在此添加更多的预处理逻辑...
    #    例如: 验证订单的可生产工厂是否存在于工厂列表中等。

    logging.info("数据预处理完成。")
    return aps_input