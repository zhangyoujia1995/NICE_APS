# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any

# 引入 OR-Tools 的核心模型库和我们定义的数据结构
from ortools.sat.python import cp_model
from core.process_data import APSInputData, _get_efficiency_for_order
from core.variable_registry import VariableDict


def add_capacity_constraint(
        model: cp_model.CpModel,
        data: APSInputData,
        variables: VariableDict
):
    """
    添加多维度的“产能约束”。
    确保对每个工厂、每个周期、每个工序，分配的总工作量不超过其可用产能。

    Args:
        model (cp_model.CpModel): OR-Tools CP-SAT 的模型实例。
        data (APSInputData): 包含了所有预处理后数据的容器。
        variables (VariableDict): 包含了所有决策变量的嵌套字典。
    """
    logging.info("开始添加“产能”约束...")

    # 第一层循环：遍历所有工厂
    for factory in data.factories:

        # 第二层循环：遍历该工厂的所有生产周期
        for period in factory.capacity_periods:

            # 第三层循环：遍历该周期内定义的每一道工序及其产能
            # 这是实现“多维产能约束”的关键
            for process_name, process_capacity in period.capacity_by_process.items():

                # 用于收集所有可能消耗当前这道工序产能的“（工作量 * 变量）”项
                total_consumed_for_process = []

                # 遍历所有订单，计算它们对当前这道工序的产能消耗
                for order in data.orders:

                    # 检查1：该订单是否需要消耗当前这道工序的产能？
                    if process_name not in order.total_process_capacity:
                        continue  # 如果不需要，则直接跳到下一个订单

                    # 检查2：该(订单,工厂,周期)组合是否存在决策变量？
                    # 如果不存在，说明它在变量创建阶段已被过滤掉（如不满足前置时间），无需再考虑
                    if (order.order_id not in variables or
                            factory.factory_id not in variables[order.order_id] or
                            period.start_date not in variables[order.order_id][factory.factory_id]):
                        continue

                    # --- 动态计算实际工作量 ---
                    # 1. 获取该订单对该工序的标准消耗
                    base_workload = order.total_process_capacity[process_name]

                    # 2. 获取该订单在该工厂的生产效率
                    efficiency = _get_efficiency_for_order(order, factory)

                    # 3. 计算效率调整后的实际工作量
                    # CP-SAT 求解器推荐使用整数，因此我们进行取整
                    actual_workload = int(base_workload / efficiency)

                    # 4. 获取对应的决策变量
                    var = variables[order.order_id][factory.factory_id][period.start_date]

                    # 5. 将“工作量 * 变量”这一项加入到总消耗列表中
                    total_consumed_for_process.append(actual_workload * var)

                # --- 添加核心约束 ---
                # 如果有任何订单可能消耗该工序的产能
                if total_consumed_for_process:
                    # 将所有消耗项求和，并约束其必须小于等于该工序的总产能
                    model.Add(sum(total_consumed_for_process) <= process_capacity)

    logging.info("“产能”约束添加完成。")