# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any

# 引入 OR-Tools 的核心模型库和我们定义的数据结构
from ortools.sat.python import cp_model
from core.process_data import APSInputData
from core.variable_registry import VariableDict

# 动态导入所有单个的目标函数模块
from .tardiness_penalty import add_tardiness_penalty_objective
# 修正：同时导入 workload_balance 的主函数和它定义的 SCALING_FACTOR 常量
from .workload_balance import add_workload_balance_objective, SCALING_FACTOR


def set_combined_objective(
        model: cp_model.CpModel,
        data: APSInputData,
        variables: VariableDict
):
    """
    设置模型的最终组合优化目标。
    该函数会调用所有单个的目标模块，获取它们的目标项，
    然后根据配置的权重进行加权求和，并设置为模型要最小化的总目标。
    """
    logging.info("开始组合所有优化目标...")

    # 1. 从各自的模块中获取独立的、未加权的目标项（成本项）
    tardiness_term = add_tardiness_penalty_objective(model, data, variables)
    balance_term = add_workload_balance_objective(model, data, variables)

    # 2. 从配置文件中获取各个目标的权重
    weights = data.settings.get('objective_weights', {})
    w_tardy = weights.get('tardiness', 1.0)
    w_balance = weights.get('workload_balance', 1.0)
    logging.info(f"目标权重 - 延误惩罚: {w_tardy}, 负载均衡: {w_balance}")

    # 3. 对目标项进行加权和缩放，构建最终的整数线性目标函数
    total_objective_terms = []
    total_orders = len(data.orders)

    if w_tardy > 0:
        # 这确保了两个目标的量级始终是关联和同步的
        total_objective_terms.append(int(w_tardy) * tardiness_term * SCALING_FACTOR)

    if w_balance > 0:
        total_objective_terms.append(int(w_balance) * balance_term * total_orders)

    # 4. 将加权后的所有目标项求和，并设置为模型要最小化的目标
    if total_objective_terms:
        model.Minimize(sum(total_objective_terms))
        logging.info("组合优化目标设置完成。")
    else:
        logging.warning("没有任何有效的目标被添加到模型中。")