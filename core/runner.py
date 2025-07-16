# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any
from pprint import pprint
from dataclasses import asdict

# 引入所有核心组件
from .load_data import load_and_structure_data
from .process_data import process_data
from .variable_registry import create_variables
from .solver import SATSolver
from .store_result import process_and_log_results

# --- 引入所有约束和目标模块 ---
# 约束
from constraints.order_unique_assign import add_order_unique_assign_constraint
from constraints.capacity import add_capacity_constraint
from constraints.material_lead_time import add_material_lead_time_constraint
# 目标
from objectives.combined_objective import set_combined_objective

# --- 创建约束映射表 ---
# key: settings.json中 active_constraints 列表里的字符串
# value: 对应的要执行的函数
CONSTRAINT_MAP = {
    "order_unique_assign": add_order_unique_assign_constraint,
    "capacity": add_capacity_constraint,
    "material_lead_time": add_material_lead_time_constraint
}


class APSRunner:
    """
    APS系统的核心流程执行器。
    负责按顺序调用数据处理、模型构建和求解等所有模块。
    """

    def __init__(self, settings: Dict[str, Any]):
        """
        初始化执行器。
        Args:
            settings (Dict[str, Any]): 从 settings.json 加载的配置字典。
        """
        self.settings = settings
        logging.info("APSRunner 已初始化。")

    def run(self):
        """
        执行端到端的APS计算流程。
        """
        logging.info("APS 核心流程开始执行...")

        # --- 1. 数据管道 ---
        factories, orders = load_and_structure_data(self.settings)
        aps_input_data = process_data(factories, orders, self.settings)

        # --- 2. 求解器初始化与变量创建 ---
        sat_solver = SATSolver(self.settings)
        model = sat_solver.get_model()
        variables = create_variables(model, aps_input_data)

        # --- 3. 动态添加约束 ---
        logging.info("=" * 20 + " 添加约束 " + "=" * 20)
        active_constraints = self.settings.get('active_constraints', [])
        logging.info(f"激活的约束列表: {active_constraints}")

        for constraint_name in active_constraints:
            constraint_func = CONSTRAINT_MAP.get(constraint_name)
            if constraint_func:
                # 调用映射表中对应的函数，传入所需参数
                constraint_func(model, aps_input_data, variables)
            else:
                logging.warning(f"配置中请求的约束 '{constraint_name}' 没有找到对应的实现模块，已跳过。")

        # --- 4. 添加组合优化目标 ---
        logging.info("=" * 20 + " 添加优化目标 " + "=" * 20)
        # 直接调用组合目标函数，它会内部处理所有子目标
        set_combined_objective(model, aps_input_data, variables)

        # --- 5. 求解 ---
        logging.info("=" * 20 + " 开始求解 " + "=" * 20)
        solver_instance = sat_solver.solve()

        # --- 6. 存储结果 (未来步骤) ---
        logging.info("=" * 20 + " 处理并存储结果 " + "=" * 20)
        # 此处将调用 core/store_result.py
        if solver_instance.StatusName() in ('OPTIMAL', 'FEASIBLE'):
            logging.info("模型有解，下一步将处理结果。")
            process_and_log_results(solver_instance, aps_input_data, variables)
        else:
            logging.info("模型无解或求解失败，无需处理结果。")

        logging.info("APS 核心流程执行完毕。")