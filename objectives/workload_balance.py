# -*- coding: utf-8 -*-

import logging
from typing import List

# 引入 OR-Tools 的核心模型库和我们定义的数据结构
from ortools.sat.python import cp_model
from core.process_data import APSInputData, _get_efficiency_for_order
from core.variable_registry import VariableDict

# 定义一个缩放因子，将百分比转换为更高精度的整数。
# 例如，85.7% -> 857。这有助于求解器处理。
SCALING_FACTOR = 1000


def add_workload_balance_objective(
        model: cp_model.CpModel,
        data: APSInputData,
        variables: VariableDict
) -> cp_model.LinearExpr:
    """
    添加“工厂负荷相关”的目标项。
    目标是最小化所有【已使用】工厂周期中，最大负载率和最小负载率的差值。

    Args:
        model (cp_model.CpModel): OR-Tools CP-SAT 的模型实例。
        data (APSInputData): 包含了所有预处理后数据的容器。
        variables (VariableDict): 包含了所有决策变量的嵌套字典。

    Returns:
        cp_model.LinearExpr: 一个代表了综合“负荷相关成本”的线性表达式。
    """
    logging.info("开始添加“工厂负荷均衡”目标项 (排除0负载)...")

    # 1. 创建全局的最大/最小负载率（已缩放）辅助变量
    # 范围从 0 到 SCALING_FACTOR (即 0% 到 100%)，可以适当放大范围以允许超载
    max_load_ratio_scaled = model.NewIntVar(0, SCALING_FACTOR * 2, f"max_load_ratio_scaled_x{SCALING_FACTOR}")
    min_load_ratio_scaled = model.NewIntVar(0, SCALING_FACTOR * 2, f"min_load_ratio_scaled_x{SCALING_FACTOR}")

    # 确保min总是小于等于max，这在处理空集时能保证模型的稳定性
    model.Add(min_load_ratio_scaled <= max_load_ratio_scaled)

    # 遍历每一个工厂和每一个周期，建立关联约束
    for factory in data.factories:
        for period_start_date, total_capacity in data.factory_total_capacity_by_period[factory.factory_id].items():

            # 如果一个周期的总产能为0，则跳过，避免除以0的错误
            if total_capacity == 0:
                continue

            # --- 计算当前(工厂,周期)的总工作量表达式 ---
            total_workload_expr_list = []
            for order in data.orders:
                # 检查是否存在对应的决策变量
                if (order.order_id in variables and
                        factory.factory_id in variables[order.order_id] and
                        period_start_date in variables[order.order_id][factory.factory_id]):
                    # 计算该订单在该工厂经效率调整后的总工作量
                    efficiency = _get_efficiency_for_order(order, factory)
                    base_workload = data.order_total_base_workload[order.order_id]
                    actual_workload = int(base_workload / efficiency)

                    # 获取决策变量
                    var = variables[order.order_id][factory.factory_id][period_start_date]
                    total_workload_expr_list.append(actual_workload * var)

            # 如果没有任何订单可能在该周期生产，则跳过
            if not total_workload_expr_list:
                continue

            total_workload_expr = sum(total_workload_expr_list)

            # --- 创建“周期被使用”的指示变量 ---
            is_used_fp = model.NewBoolVar(f"is_used_{factory.factory_id}_{period_start_date}")

            # 链接指示变量与工作量：如果总工作量>0，则 is_used_fp 必须为1
            model.Add(total_workload_expr > 0).OnlyEnforceIf(is_used_fp)
            # 链接指示变量与工作量：如果总工作量=0，则 is_used_fp 必须为0
            model.Add(total_workload_expr == 0).OnlyEnforceIf(is_used_fp.Not())

            # --- 添加 Minimax 约束 ---
            # 约束1: max_load_ratio_scaled >= (total_workload_expr / total_capacity) * SCALING_FACTOR
            model.Add(max_load_ratio_scaled * int(total_capacity) >= total_workload_expr * SCALING_FACTOR)

            # 约束2: min_load_ratio_scaled <= (total_workload_expr / total_capacity) * SCALING_FACTOR
            model.Add(min_load_ratio_scaled * int(total_capacity) <= total_workload_expr * SCALING_FACTOR).OnlyEnforceIf(is_used_fp)

    # --- 在函数内部组合两个子目标 ---
    # 子目标B1: 最小化差异 (均衡)
    imbalance_cost = max_load_ratio_scaled - min_load_ratio_scaled
    # 子目标B2: 最小化最大值 (削峰)
    max_load_cost = max_load_ratio_scaled

    # 将两个子目标以50/50的比例组合成最终的“不均衡成本”
    combined_balance_cost = 0.5 * imbalance_cost + 0.5 * max_load_cost

    logging.info("“工厂负荷均衡”目标项添加完成。")
    return combined_balance_cost