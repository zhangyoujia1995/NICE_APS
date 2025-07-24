# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from typing import List, Optional

# 引入 OR-Tools 的核心模型库和我们定义的数据结构
from ortools.sat.python import cp_model
from core.process_data import APSInputData
from core.variable_registry import VariableDict


def add_tardiness_penalty_objective(
        model: cp_model.CpModel,
        data: APSInputData,
        variables: VariableDict
) -> Optional[cp_model.LinearExpr]:
    """
    添加“最小化延误订单数量”的目标项。
    区分正式订单和预测订单，并施加不同权重。

    Args:
        model (cp_model.CpModel): OR-Tools CP-SAT 的模型实例。
        data (APSInputData): 包含了所有预处理后数据的容器。
        variables (VariableDict): 包含了所有决策变量的嵌套字典。

    Returns:
        Optional[cp_model.LinearExpr]: 一个代表了“延误订单总数”的线性表达式，
                             将作为最终目标函数的一部分。
    """
    logging.info("开始添加“最小化延误订单数量”目标项...")

    # 从配置中读取对不同订单类型的整数惩罚
    config = data.settings.get("tardiness_objective_config", {})
    firm_tardy_weight = config.get("firm_tardy_weight", 0.7)
    forecast_tardy_weight = config.get("forecast_tardy_weight", 0.3)

    # 预处理：分类统计订单总数，用于计算分母
    total_firm_orders = 0
    total_forecast_orders = 0
    for order in data.orders:
        if order.order_type == 1:
            total_firm_orders += 1
        else:
            total_forecast_orders += 1

    # 创建指示变量并分类
    firm_tardy_vars = []
    forecast_tardy_vars = []
    period_end_date_map = {
        f.factory_id: {p.start_date: p.end_date for p in f.capacity_periods}
        for f in data.factories
    }

    for order in data.orders:
        # 假设 order_type 字段存在
        if not hasattr(order, 'order_type'):
            logging.warning(f"订单 {order.order_id} 缺少 'order_type' 字段，将按默认类型处理。")

        is_tardy_var = model.NewBoolVar(f"is_tardy_{order.order_id}")

        # 根据订单类型，将指示变量放入不同的列表
        if getattr(order, 'order_type', 1) == 1:  # 默认为正式单
            firm_tardy_vars.append(is_tardy_var)
        else:
            forecast_tardy_vars.append(is_tardy_var)

        due_date_obj = datetime.strptime(order.due_date, '%Y-%m-%d').date()
        if order.order_id in variables:
            for factory_id, period_vars in variables[order.order_id].items():
                for period_start, var in period_vars.items():
                    end_date = datetime.strptime(period_end_date_map[factory_id][period_start], '%Y-%m-%d').date()
                    if end_date > due_date_obj:
                        model.Add(is_tardy_var >= var)

    # 计算最终的加权延误率表达式
    # 采用0.3/0.7的内置比例组合成最终的“延误率”
    tardiness_rate_terms = []

    # --- 对 total_firm_orders > 0 的判断 ---
    if total_firm_orders > 0:
        firm_tardy_percentage_factor = 1 / total_firm_orders
        firm_tardy_rate = firm_tardy_percentage_factor * sum(firm_tardy_vars)
        tardiness_rate_terms.append(firm_tardy_weight * firm_tardy_rate)

    # --- 对 total_forecast_orders > 0 的判断 ---
    if total_forecast_orders > 0:
        forecast_tardy_percentage_factor = 1 / total_forecast_orders
        forecast_tardy_rate = forecast_tardy_percentage_factor * sum(forecast_tardy_vars)
        tardiness_rate_terms.append(forecast_tardy_weight * forecast_tardy_rate)

    if not tardiness_rate_terms:
        logging.info("没有需要计算延误率的订单类型。")
        return None

    tardiness_rate_expr = sum(tardiness_rate_terms)

    logging.info("“最小化延误订单数量”目标项添加完成。")

    return tardiness_rate_expr