# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any

# 引入 OR-Tools 的核心模型库和我们定义的数据结构
from ortools.sat.python import cp_model
from core.process_data import APSInputData
from core.variable_registry import VariableDict


def add_order_unique_assign_constraint(
        model: cp_model.CpModel,
        data: APSInputData,
        variables: VariableDict
):
    """
    添加“订单唯一分配”约束。
    确保每个订单在所有可能的工厂和周期中，只被分配一次。

    Args:
        model (cp_model.CpModel): OR-Tools CP-SAT 的模型实例。
        data (APSInputData): 包含了所有预处理后数据的容器。
        variables (VariableDict): 包含了所有决策变量的嵌套字典。
    """
    logging.info("开始添加“订单唯一分配”约束...")

    # 遍历每一个订单
    for order in data.orders:
        order_id = order.order_id

        # 创建一个列表，用于收集与当前订单相关的所有决策变量
        all_assignments_for_order = []

        # 检查该订单是否有对应的变量（可能因为无合格工厂等原因而没有）
        if order_id in variables:
            # 遍历所有可能的工厂
            for factory_id in variables[order_id]:
                # 遍历所有可能的周期
                for period_start_date in variables[order_id][factory_id]:
                    # 将该 (订单, 工厂, 周期) 组合对应的变量添加到列表中
                    all_assignments_for_order.append(
                        variables[order_id][factory_id][period_start_date]
                    )

        # 添加核心约束：
        # 如果这个订单有任何可能的分配方案（即列表不为空）
        # 那么它所有可能的分配变量的总和必须等于1。
        # 这意味着在所有可能性中，它必须被精确地选中一次。
        if all_assignments_for_order:
            model.AddExactlyOne(all_assignments_for_order)
        else:
            # 这是一个警告，说明某个订单因为某些原因（如没有合格工厂）完全无法被排产
            logging.warning(f"订单 {order_id} 没有任何有效的生产分配选项，无法为其添加唯一分配约束。")

    logging.info("“订单唯一分配”约束添加完成。")