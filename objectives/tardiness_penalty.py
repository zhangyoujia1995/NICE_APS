# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from typing import List

# 引入 OR-Tools 的核心模型库和我们定义的数据结构
from ortools.sat.python import cp_model
from core.process_data import APSInputData
from core.variable_registry import VariableDict


def add_tardiness_penalty_objective(
        model: cp_model.CpModel,
        data: APSInputData,
        variables: VariableDict
) -> cp_model.LinearExpr:
    """
    添加“最小化延误订单数量”的目标项。

    Args:
        model (cp_model.CpModel): OR-Tools CP-SAT 的模型实例。
        data (APSInputData): 包含了所有预处理后数据的容器。
        variables (VariableDict): 包含了所有决策变量的嵌套字典。

    Returns:
        cp_model.LinearExpr: 一个代表了“延误订单总数”的线性表达式，
                             将作为最终目标函数的一部分。
    """
    logging.info("开始添加“最小化延误订单数量”目标项...")

    # 用于收集所有订单的“是否延误”指示变量
    tardiness_indicators: List[cp_model.IntVar] = []

    # 为了快速查询周期的结束日期，我们先创建一个映射
    # key: factory_id, value: {period_start_date: period_end_date}
    period_end_date_map = {
        f.factory_id: {p.start_date: p.end_date for p in f.capacity_periods}
        for f in data.factories
    }

    # 遍历每一个订单
    for order in data.orders:
        order_id = order.order_id

        # 1. 为当前订单创建一个布尔型“指示变量”
        #    如果订单延误，该变量为1，否则为0。
        is_tardy_var = model.NewBoolVar(f"is_tardy_{order_id}")
        tardiness_indicators.append(is_tardy_var)

        # 将订单的交付日期字符串转换为 date 对象
        due_date_obj = datetime.strptime(order.due_date, '%Y-%m-%d').date()

        # 2. 建立指示变量与决策变量之间的逻辑链接
        # 遍历该订单所有可能的分配方案
        if order_id in variables:
            for factory_id, period_vars in variables[order_id].items():
                for period_start_date, assignment_var in period_vars.items():
                    # 获取该周期的结束日期（即计划完成日期）
                    period_end_date_str = period_end_date_map[factory_id][period_start_date]
                    planned_completion_date = datetime.strptime(period_end_date_str, '%Y-%m-%d').date()

                    # 如果这个分配方案会导致延误
                    if planned_completion_date > due_date_obj:
                        # 添加约束: is_tardy_var >= assignment_var
                        # 含义：如果这个会导致延误的方案被选中(assignment_var=1),
                        #       那么 is_tardy_var 就必须大于等于1，即被强制为1。
                        model.Add(is_tardy_var >= assignment_var)

    logging.info("“最小化延误订单数量”目标项添加完成。")

    # 3. 返回所有指示变量的总和
    #    求解器在最小化这个总和时，就会尽可能地让每个 is_tardy_var 为0，
    #    从而达到减少延误订单数量的目的。
    return sum(tardiness_indicators)