# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from typing import Optional, List, Tuple

from ortools.sat.python import cp_model
from core.process_data import APSInputData
from core.variable_registry import VariableDict


def add_jit_deviation_objective(
        model: cp_model.CpModel,
        data: APSInputData,
        variables: VariableDict
) -> Optional[cp_model.LinearExpr]:
    """
    创建并返回“Just-in-Time”偏差的组合目标项。
    内部采用固定的0.4/0.6比例来加权“提前”与“延误”天数。

    Args:
        model (cp_model.CpModel): OR-Tools CP-SAT 的模型实例。
        data (APSInputData): 包含了所有预处理后数据的容器。
        variables (VariableDict): 包含了所有决策变量的嵌套字典。

    Returns:
        Optional[cp_model.LinearExpr]:
            一个代表了综合“JIT偏差成本”的线性表达式。
            如果所有订单都无法排产，则可能返回None。
    """
    logging.info("开始添加“JIT偏差”组合目标项 (采用0.3/0.7内置权重)...")

    # 从配置中读取JIT参数
    jit_config = data.settings.get("jit_objective_config", {})
    allowed_deviation = jit_config.get("allowed_deviation_days", 30)  # 默认为30

    earliness_vars = []
    tardiness_vars = []

    # 为了进行日期运算，我们需要一个较长的规划期作为变量上限, 假设最长不会超过1年
    horizon = 365

    # 步骤1：预先计算所有周期的结束日期（以距离base_date的天数表示）
    # 这样做可以避免在循环中反复进行日期转换，提高效率
    period_end_days_map = {}
    for factory in data.factories:
        period_end_days_map[factory.factory_id] = {
            p.start_date: (datetime.strptime(p.end_date, '%Y-%m-%d').date() - data.base_date).days
            for p in factory.capacity_periods
        }

    for order in data.orders:
        order_id = order.order_id

        # 步骤2：为每个订单创建提前/延误天数的辅助变量
        earliness_var = model.NewIntVar(0, horizon, f"earliness_days_{order_id}")
        tardiness_var = model.NewIntVar(0, horizon, f"tardiness_days_{order_id}")
        earliness_vars.append(earliness_var)
        tardiness_vars.append(tardiness_var)

        # 步骤3：构建“计划完成日期”的线性表达式
        completion_date_expr_terms = []
        if order_id in variables:
            for factory_id, period_vars in variables[order_id].items():
                for period_start, var in period_vars.items():
                    completion_days = period_end_days_map[factory_id][period_start]
                    completion_date_expr_terms.append(completion_days * var)

        if not completion_date_expr_terms:
            # 如果订单没有任何可分配的选项，则其偏差为0
            model.Add(earliness_var == 0)
            model.Add(tardiness_var == 0)
            continue

        planned_completion_days = sum(completion_date_expr_terms)

        # 将交付日期也转换为相对于 base_date 的天数
        due_date_days = (datetime.strptime(order.due_date, '%Y-%m-%d').date() - data.base_date).days

        # 步骤4：添加核心约束，将变量与日期关联起来
        model.Add(planned_completion_days - due_date_days == tardiness_var - earliness_var)

    # 步骤5：将提前和延误天数按固定比例组合
    total_earliness = sum(earliness_vars)
    total_tardiness = sum(tardiness_vars)

    # 采用0.3/0.7的内置比例组合成最终的“JIT偏差成本”
    # CP-SAT的线性表达式支持浮点数系数
    combined_jit_cost = 0.3 * total_earliness + 0.7 * total_tardiness

    # 总偏差天数 / (总订单数*允许偏差天数) -> [0,1]的偏差率，获得相关系数
    total_orders = len(data.orders)
    jit_days_to_percentage_factor = 1 / (allowed_deviation * total_orders)

    jit_rate_expr = combined_jit_cost * jit_days_to_percentage_factor

    logging.info("“JIT偏差”组合目标项添加完成。")

    return jit_rate_expr