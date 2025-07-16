# -*- coding: utf-8 -*-

import logging
import datetime as dt
from typing import Dict

# 引入 OR-Tools 的核心模型库
from ortools.sat.python import cp_model

# 引入我们预处理好的数据容器
from .process_data import APSInputData

# 定义变量字典的类型别名，方便代码阅读
# 结构: {order_id: {factory_id: {period_start_date: variable}}}
VariableDict = Dict[str, Dict[str, Dict[str, cp_model.IntVar]]]


def create_variables(model: cp_model.CpModel, data: APSInputData) -> VariableDict:
    """
    为所有有效assignments创建决策变量。

    一个 "assignment" 是一个 (订单, 工厂, 生产周期) 的组合。

    Args:
        model (cp_model.CpModel): OR-Tools CP-SAT 的模型实例。
        data (APSInputData): 包含了所有预处理后数据的容器。

    Returns:
        VariableDict: 一个嵌套的字典，存储了所有创建的决策变量，
                      结构为 {order_id: {factory_id: {period_start_date: variable}}}。
    """
    logging.info("开始创建决策变量...")

    # 初始化用于存储变量的嵌套字典
    x: VariableDict = {o.order_id: {} for o in data.orders}

    total_vars_created = 0

    # --- 遍历所有订单 ---
    for order in data.orders:
        order_id = order.order_id

        # --- 遍历该订单所有可生产的工厂 ---
        # 优化点1: 只在订单的“可生产工厂”列表中进行遍历，大大减少无效组合
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