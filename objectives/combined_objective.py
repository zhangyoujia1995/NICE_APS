# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any

# 引入 OR-Tools 的核心模型库和我们定义的数据结构
from ortools.sat.python import cp_model
from core.process_data import APSInputData
from core.variable_registry import VariableDict

# 动态导入所有单个的目标函数模块
from .tardiness_penalty import add_tardiness_penalty_objective
from .just_in_time import add_jit_deviation_objective
from .workload_balance import add_workload_balance_objective, SCALING_FACTOR


def set_combined_objective(
        model: cp_model.CpModel,
        data: APSInputData,
        variables: VariableDict
):
    """
    设置模型的最终组合优化目标。
    将每个目标项明确转换为[0,1]范围的比率，然后进行加权求和。
    该函数会调用所有单个的目标模块，获取它们的目标项，
    然后根据配置的权重进行加权求和，并设置为模型要最小化的总目标。
    """
    logging.info("开始组合所有优化目标...")

    # 1. 从配置文件中获取各个目标的权重
    weights = data.settings.get('objective_weights', {})
    w_tardy = weights.get('tardiness', 0)
    w_jit = weights.get('jit_deviation', 0.0)
    w_balance = weights.get('workload_balance', 0)
    logging.info(f"目标权重 - 延误率: {w_tardy}, JIT偏差: {w_jit}, 负载均衡: {w_balance}")

    total_objective_terms = []
    total_orders = len(data.orders)
    if total_orders == 0:
        logging.warning("订单总数为0，无法设置目标。")
        return

    # 2. 根据权重，条件化地调用目标模块，并将结果转换为[0,1]范围的比率

    # a. 处理延误目标项
    if w_tardy > 0:
        logging.info("延误惩罚权重 > 0，激活该目标项。")
        tardiness_term = add_tardiness_penalty_objective(model, data, variables)
        if tardiness_term is not None:
            # 延误订单数 / 总订单数 -> [0,1]的延误率，获得相关系数
            tardiness_to_percentage_factor = 1 / total_orders

            objective_tardy = w_tardy * tardiness_term * tardiness_to_percentage_factor
            total_objective_terms.append(objective_tardy)

    # b. 处理交期偏差
    if w_jit > 0:
        logging.info("JIT偏差权重 > 0，激活该目标项。")
        jit_term = add_jit_deviation_objective(model, data, variables)
        if jit_term is not None:
            # 从配置中读取JIT参数
            jit_config = data.settings.get("jit_objective_config", {})
            allowed_deviation = jit_config.get("allowed_deviation_days", 30)  # 默认为30

            # 总偏差天数 / (总订单数*允许偏差天数) -> [0,1]的偏差率，获得相关系数
            jit_days_to_percentage_factor = 1 / (allowed_deviation * total_orders)

            objective_jit = w_jit * jit_term * jit_days_to_percentage_factor
            total_objective_terms.append(objective_jit)

    # c. 处理负载均衡目标项
    if w_balance > 0:
        logging.info("负载均衡权重 > 0，激活该目标项。")
        balance_term = add_workload_balance_objective(model, data, variables)
        if balance_term is not None:
            # 不均衡成本(0-SCALING_FACTOR) / SCALING_FACTOR -> [0,1]的不均衡率，获得相关系数
            workload_to_percentage_factor = 1 / SCALING_FACTOR

            objective_balance = w_balance * balance_term * workload_to_percentage_factor
            total_objective_terms.append(objective_balance)

    # 3. 将加权后的所有目标项求和，并设置为模型要最小化的目标
    if total_objective_terms:
        model.Minimize(sum(total_objective_terms))
        logging.info("组合优化目标设置完成。")
    else:
        logging.warning("没有任何有效的目标被添加到模型中。")