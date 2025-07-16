# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from typing import Dict, Any, Optional

# 引入 OR-Tools 的核心模型库
from ortools.sat.python import cp_model

# 引入我们预处理好的数据容器
from .process_data import APSInputData

# 定义变量字典的类型别名，方便代码阅读
# 结构: {order_id: {factory_id: {period_start_date: variable}}}
VariableDict = Dict[str, Dict[str, Dict[str, cp_model.IntVar]]]

def find_snapped_period_start_date(
    locked_date_str: str,
    factories_to_check: list,
) -> Optional[str]:
    """
    辅助函数：根据一个给定的日期，查找它所属周期的官方开始日期。
    """
    try:
        locked_date_obj = datetime.strptime(locked_date_str, '%Y-%m-%d').date()
    except ValueError:
        logging.error(f"锁定的日期 '{locked_date_str}' 格式无效，应为 YYYY-MM-DD。")
        return None

    for factory in factories_to_check:
        for period in factory.capacity_periods:
            start_date_obj = datetime.strptime(period.start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(period.end_date, '%Y-%m-%d').date()
            if start_date_obj <= locked_date_obj <= end_date_obj:
                logging.info(f"日期 '{locked_date_str}' 已自动吸附到周期 '{period.start_date}'。")
                return period.start_date
    return None

def create_variables(model: cp_model.CpModel, data: APSInputData) -> VariableDict:
    """
    为所有分配方案创建决策变量，并处理锁单逻辑。
    - 对于普通订单，为所有合格工厂的全部周期创建变量。
    - 对于锁定订单，根据锁定条件智能创建变量或施加约束。

    Args:
        model (cp_model.CpModel): OR-Tools CP-SAT 的模型实例。
        data (APSInputData): 包含了所有预处理后数据的容器。

    Returns:
        VariableDict: 一个嵌套的字典，存储了所有创建的决策变量。
    """
    logging.info("开始创建决策变量...")

    # 初始化用于存储变量的嵌套字典
    x: VariableDict = {o.order_id: {} for o in data.orders}

    total_vars_created = 0

    # --- 遍历所有订单 ---
    for order in data.orders:
        order_id = order.order_id
        x[order_id] = {}

        # 检查订单是否有锁定分配
        if order.fixed_assignment:
            logging.info(f"订单 '{order_id}' 存在锁定分配: {order.fixed_assignment}")
            locked_factory_id = order.fixed_assignment.get('factory_id')
            user_locked_date = order.fixed_assignment.get('period_start_date')

            final_locked_period_start = None
            # --- 验证锁定的周期开始日期是否有效 ---
            if user_locked_date:
                factories_to_check = [data.factory_map[locked_factory_id]] if locked_factory_id else [
                    data.factory_map[fid] for fid in order.eligible_factories if fid in data.factory_map]
                snapped_date = find_snapped_period_start_date(user_locked_date, factories_to_check)

                if not snapped_date:
                    logging.error(
                        f"订单 '{order_id}' 锁定的日期 '{user_locked_date}' 不在任何合格工厂的有效产能周期内。"
                        f"此订单将无法按锁定要求排程，已跳过。"
                    )
                    continue
                final_locked_period_start = snapped_date

            # 根据锁定条件确定需要遍历的工厂和周期范围
            factories_to_search = [data.factory_map[locked_factory_id]] if locked_factory_id else [
                data.factory_map[fid] for fid in order.eligible_factories if fid in data.factory_map]

            for factory in factories_to_search:
                factory_id = factory.factory_id
                x[order_id][factory_id] = {}

                periods_to_search = [p for p in factory.capacity_periods if
                                     p.start_date == final_locked_period_start] if final_locked_period_start else factory.capacity_periods

                for period in periods_to_search:
                    var_name = f"x_{order_id}_{factory_id}_{period.start_date}"
                    variable = model.NewBoolVar(var_name)
                    x[order_id][factory_id][period.start_date] = variable
                    total_vars_created += 1

                    if locked_factory_id and final_locked_period_start:
                        model.Add(variable == 1)
                        logging.info(
                            f"  └── 已将订单 '{order_id}' 硬性约束至 工厂='{locked_factory_id}', 周期='{final_locked_period_start}'")

        else:
            # --- 对于未锁定的订单 ---
            # --- 遍历该订单所有可生产的工厂 ---
            for factory_id in order.eligible_factories:
                if factory_id not in data.factory_map:
                    logging.warning(f"订单 {order_id} 的可生产工厂 {factory_id} 不在工厂数据中，已跳过。")
                    continue

                factory = data.factory_map[factory_id]
                x[order_id][factory_id] = {}

                # --- 遍历该工厂的所有生产周期 ---
                for period in factory.capacity_periods:
                    # --- 创建布尔决策变量 ---
                    # 变量名为 x_订单ID_工厂ID_周期开始日期，方便调试
                    var_name = f"x_{order_id}_{factory_id}_{period.start_date}"
                    x[order_id][factory_id][period.start_date] = model.NewBoolVar(var_name)
                    total_vars_created += 1

    logging.info(f"决策变量创建完成。总共创建了 {total_vars_created} 个变量。")
    return x